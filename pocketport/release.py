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
    "i686": "x86",
    "i386": "x86",
}


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


def _asset_score(name: str, arch: str) -> tuple[int, list[str]]:
    n = name.lower()
    reasons: list[str] = []
    score = 0

    if arch == "aarch64":
        if "aarch64" in n:
            score += 70
            reasons.append("aarch64")
        elif "arm64" in n:
            score += 65
            reasons.append("arm64")
        elif re.search(r"(^|[-_.])armv?8($|[-_.])", n):
            score += 55
            reasons.append("armv8")
        elif any(x in n for x in ("x86_64", "amd64", "i386", "i686")):
            score -= 100
            reasons.append("wrong-arch")

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
    if any(x in n for x in ("windows", "win64", "darwin", "macos", "osx")):
        score -= 100
        reasons.append("wrong-os")
    if any(x in n for x in ("source", "src")):
        score -= 35
        reasons.append("source")
    if any(x in n for x in (".sha256", ".sha512", ".sig", ".asc", "checksums")):
        score -= 80
        reasons.append("metadata")

    return score, reasons


def select_asset(assets: list[dict], arch: str | None = None) -> AssetChoice | None:
    arch = normalize_arch(arch)
    choices: list[AssetChoice] = []
    for asset in assets:
        name = str(asset.get("name", ""))
        url = str(asset.get("browser_download_url", asset.get("url", "")))
        if not name or not url:
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
        "User-Agent": "PocketPort/0.2",
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
