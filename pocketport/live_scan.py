from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path, PurePosixPath
import re
import shutil
import tarfile
import tempfile
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlparse
from urllib.request import Request, urlopen

from .components import assess_components
from .entrypoints import enrich_workspace_entrypoint
from .execution import build_execution_plan
from .semantics import semantic_scan


MAX_ARCHIVE_BYTES = 64 * 1024 * 1024
MAX_UNPACKED_BYTES = 128 * 1024 * 1024
MAX_FILES = 25_000
DOWNLOAD_TIMEOUT = 20

_OWNER_RE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})$")
_REPO_RE = re.compile(r"^[A-Za-z0-9._-]{1,100}$")


@dataclass(frozen=True)
class GitHubRepo:
    owner: str
    repo: str

    @property
    def slug(self) -> str:
        return f"{self.owner}/{self.repo}"

    @property
    def url(self) -> str:
        return f"https://github.com/{self.owner}/{self.repo}"


class LiveScanError(RuntimeError):
    def __init__(self, message: str, *, code: str, status: int = 400):
        super().__init__(message)
        self.code = code
        self.status = status


def normalize_public_github_url(value: str) -> GitHubRepo:
    if not isinstance(value, str) or not value.strip():
        raise LiveScanError("repository must be a GitHub URL", code="invalid_repository")

    raw = value.strip()
    parsed = urlparse(raw)
    if parsed.scheme != "https" or parsed.hostname != "github.com":
        raise LiveScanError(
            "only https://github.com/owner/repo URLs are accepted",
            code="invalid_repository",
        )
    if parsed.username or parsed.password or parsed.port or parsed.query or parsed.fragment:
        raise LiveScanError("repository URL contains unsupported fields", code="invalid_repository")

    parts = [part for part in parsed.path.split("/") if part]
    if len(parts) != 2:
        raise LiveScanError("repository URL must point to one repository", code="invalid_repository")

    owner, repo = parts
    if repo.endswith(".git"):
        repo = repo[:-4]
    if not _OWNER_RE.fullmatch(owner) or not _REPO_RE.fullmatch(repo) or repo in {".", ".."}:
        raise LiveScanError("repository owner or name is invalid", code="invalid_repository")
    return GitHubRepo(owner=owner, repo=repo)


def _download_archive(
    repo: GitHubRepo,
    destination: Path,
    *,
    max_bytes: int = MAX_ARCHIVE_BYTES,
    timeout: int = DOWNLOAD_TIMEOUT,
) -> None:
    endpoint = f"https://api.github.com/repos/{quote(repo.owner)}/{quote(repo.repo)}/tarball"
    request = Request(
        endpoint,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "PocketPort-Live-Scanner/0.3",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )

    try:
        response = urlopen(request, timeout=timeout)
    except HTTPError as exc:
        if exc.code == 404:
            raise LiveScanError("public repository was not found", code="repository_not_found", status=404) from exc
        if exc.code in {403, 429}:
            raise LiveScanError("GitHub temporarily refused the archive request", code="github_rate_limited", status=503) from exc
        raise LiveScanError("GitHub archive request failed", code="github_error", status=502) from exc
    except (URLError, TimeoutError) as exc:
        raise LiveScanError("GitHub archive request timed out", code="github_unreachable", status=504) from exc

    with response:
        final = urlparse(response.geturl())
        if final.scheme != "https" or final.hostname not in {"api.github.com", "codeload.github.com"}:
            raise LiveScanError("GitHub archive redirected to an unexpected host", code="unsafe_redirect", status=502)

        length = response.headers.get("Content-Length")
        if length:
            try:
                if int(length) > max_bytes:
                    raise LiveScanError("repository archive is too large for live scanning", code="repository_too_large", status=413)
            except ValueError:
                pass

        total = 0
        with destination.open("wb") as output:
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                if total > max_bytes:
                    raise LiveScanError("repository archive is too large for live scanning", code="repository_too_large", status=413)
                output.write(chunk)


def _safe_member_path(name: str) -> Path | None:
    pure = PurePosixPath(name)
    if pure.is_absolute() or ".." in pure.parts:
        raise LiveScanError("repository archive contains an unsafe path", code="invalid_archive", status=502)
    parts = [part for part in pure.parts if part not in {"", "."}]
    if len(parts) <= 1:
        return None
    return Path(*parts[1:])


def _extract_archive(
    archive: Path,
    destination: Path,
    *,
    max_files: int = MAX_FILES,
    max_unpacked_bytes: int = MAX_UNPACKED_BYTES,
) -> Path:
    files = 0
    total_size = 0
    destination.mkdir(parents=True, exist_ok=True)

    try:
        tar = tarfile.open(archive, mode="r:gz")
    except (tarfile.TarError, OSError) as exc:
        raise LiveScanError("GitHub returned an invalid repository archive", code="invalid_archive", status=502) from exc

    with tar:
        for member in tar:
            relative = _safe_member_path(member.name)
            if relative is None:
                continue

            target = destination / relative
            if member.isdir():
                target.mkdir(parents=True, exist_ok=True)
                continue

            if not member.isfile():
                continue

            files += 1
            total_size += max(0, member.size)
            if files > max_files:
                raise LiveScanError("repository contains too many files for live scanning", code="repository_too_large", status=413)
            if total_size > max_unpacked_bytes:
                raise LiveScanError("repository expands beyond the live scan size limit", code="repository_too_large", status=413)

            target.parent.mkdir(parents=True, exist_ok=True)
            source = tar.extractfile(member)
            if source is None:
                continue
            with source, target.open("wb") as output:
                shutil.copyfileobj(source, output, length=1024 * 1024)

    return destination


def scan_public_github(repository: str) -> dict:
    repo = normalize_public_github_url(repository)
    with tempfile.TemporaryDirectory(prefix="pocketport-live-") as tmp:
        temp = Path(tmp)
        archive = temp / "repo.tar.gz"
        root = temp / "repo"
        _download_archive(repo, archive)
        _extract_archive(archive, root)

        report, artifact = semantic_scan(root)
        payload = report.to_dict()
        payload["artifact"] = artifact.to_dict()
        components = assess_components(root, report.findings)
        if components:
            payload["components"] = [asdict(component) for component in components]
        plan = enrich_workspace_entrypoint(build_execution_plan(report, root), root)
        payload["execution_plan"] = plan.to_dict()

        payload["path"] = repo.slug
        payload["repository"] = repo.url
        return payload
