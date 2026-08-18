from __future__ import annotations

from dataclasses import dataclass, asdict
import json
import os
import platform
import re
import urllib.error
import urllib.request

ARCH_ALIASES = {
    "aarch64": "aarch64",
    "arm64": "aarch64",
    "armv8": "aarch64",
    "x86_64": "x86_64",
    "amd64": "x86_64",
    "x64": "x86_64",
    "i386": "x86",
    "i486": "x86",
    "i586": "x86",
    "i686": "x86",
    "x86": "x86",
}

ARCH_PATTERNS = {
    "aarch64": (
        r"(^|[-_.])aarch64($|[-_.])",
        r"(^|[-_.])arm64($|[-_.])",
        r"(^|[-_.])armv?8($|[-_.])",
    ),
    "x86_64": (
        r"(^|[-_.])x86[_-]64($|[-_.])",
        r"(^|[-_.])amd64($|[-_.])",
        r"(^|[-_.])x64($|[-_.])",
    ),
    "x86": (
        r"(^|[-_.])i[3-6]86($|[-_.])",
        r"(^|[-_.])x86(?![_-]64)(?=$|[-_.])",
    ),
}

METADATA_SUFFIX = re.compile(
    r"(?:\.(?:sha1|sha224|sha256|sha384|sha512|md5|b2)(?:\.txt)?|\.(?:sig|minisig|asc))$",
    re.IGNORECASE,
)
METADATA_TRAILER = re.compile(
    r"(?:^|[-_.])(?:checksums?|(?:sha(?:1|224|256|384|512)|md5|b2)sums?)(?:\.(?:txt|json))?$",
    re.IGNORECASE,
)
FOREIGN_OS_COMPONENT = re.compile(
    r"(?:^|[-_.])(?:"
    r"windows|win(?:32|64)?|mingw(?:32|64)?|cygwin|msys2?|msvc|"
    r"darwin(?:32|64|amd64|arm64)?|macosx?|osx|"
    r"freebsd|openbsd|netbsd|dragonfly|solaris|illumos|aix"
    r")(?=$|[-_.])",
    re.IGNORECASE,
)
SOURCE_COMPONENT = re.compile(
    r"(?:^|[-_.])(?:sources?|srcs?)(?=$|[-_.])",
    re.IGNORECASE,
)
SOURCE_ARCHIVE_SUFFIXES = (
    ".tar", ".tar.gz", ".tgz", ".tar.xz", ".tar.bz2", ".tar.zst", ".zip",
)


@dataclass
class AssetChoice:
    name: str
    url: str
    score: int
    reason: list[str]

    def to_dict(self) -> dict:
        return asdict(self)


def normalize_arch(machine: str | None = None) -> str:
    machine = (machine or platform.machine()).lower()
    return ARCH_ALIASES.get(machine, machine)


def _repo_slug(value: str) -> str:
    value = value.strip().removesuffix(".git")
    if value.startswith("https://github.com/"):
        value = value[len("https://github.com/"):]
    if value.startswith("git@github.com:"):
        value = value[len("git@github.com:"):]
    value = value.strip("/")
    if len(value.split("/")) != 2:
        raise ValueError("repo must be owner/name or a GitHub repository URL")
    return value


def _has_arch(name: str, arch: str) -> bool:
    return any(re.search(pattern, name) for pattern in ARCH_PATTERNS.get(arch, ()))


def _present_arches(name: str) -> set[str]:
    return {arch for arch in ARCH_PATTERNS if _has_arch(name, arch)}


def _is_metadata_asset(name: str) -> bool:
    n = name.lower()
    return bool(METADATA_SUFFIX.search(n) or METADATA_TRAILER.search(n))


def _is_wrong_os(name: str) -> bool:
    n = name.lower()
    return bool(
        FOREIGN_OS_COMPONENT.search(n)
        or n.endswith((".exe", ".msi", ".dmg"))
    )


def _is_source_archive(name: str) -> bool:
    n = name.lower()
    return bool(
        SOURCE_COMPONENT.search(n)
        and n.endswith(SOURCE_ARCHIVE_SUFFIXES)
    )


def _arch_compatible(name: str, arch: str) -> bool:
    present = _present_arches(name.lower())
    if not present:
        return True
    if arch not in ARCH_PATTERNS:
        return False
    return arch in present


def _asset_score(name: str, arch: str) -> tuple[int, list[str]]:
    n = name.lower()
    reasons: list[str] = []
    score = 0

    present_arches = _present_arches(n)
    if arch in present_arches:
        score += 70
        reasons.append(arch)

    if "android" in n or "termux" in n:
        score += 35
        reasons.append("android")
    elif "linux" in n:
        score += 20
        reasons.append("linux")

    if any(n.endswith(ext) for ext in (".tar.gz", ".tgz", ".tar.xz", ".zip")):
        score += 8
        reasons.append("archive")
    if n.endswith(".deb"):
        score -= 8
        reasons.append("deb")
    if SOURCE_COMPONENT.search(n):
        score -= 35
        reasons.append("source")

    return score, reasons


def select_asset(assets: list[dict], arch: str | None = None) -> AssetChoice | None:
    arch = normalize_arch(arch)
    choices: list[AssetChoice] = []
    for asset in assets:
        name = str(asset.get("name", ""))
        url = str(asset.get("browser_download_url", asset.get("url", "")))
        if not name or not url:
            continue
        if (
            _is_metadata_asset(name)
            or _is_wrong_os(name)
            or _is_source_archive(name)
            or not _arch_compatible(name, arch)
        ):
            continue
        score, reasons = _asset_score(name, arch)
        choices.append(AssetChoice(name=name, url=url, score=score, reason=reasons))

    if not choices:
        return None
    choices.sort(key=lambda x: (x.score, x.name), reverse=True)
    return choices[0] if choices[0].score > 0 else None


def fetch_release(repo: str, tag: str = "latest") -> dict:
    slug = _repo_slug(repo)
    if tag == "latest":
        url = f"https://api.github.com/repos/{slug}/releases/latest"
    else:
        url = f"https://api.github.com/repos/{slug}/releases/tags/{tag}"

    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "PocketPort/0.2.1",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"

    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"GitHub release lookup failed: HTTP {exc.code}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"GitHub release lookup failed: {exc.reason}") from exc


def choose_release_asset(repo: str, tag: str = "latest", arch: str | None = None) -> AssetChoice | None:
    release = fetch_release(repo, tag)
    return select_asset(release.get("assets", []), arch)
