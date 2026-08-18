from __future__ import annotations

from io import BytesIO
from pathlib import Path
import tarfile

import pytest

from pocketport import live_scan
from pocketport.live_scan import LiveScanError, _extract_archive, normalize_public_github_url, scan_public_github


def _write_tar(path: Path, members: list[tuple[str, bytes]]) -> None:
    with tarfile.open(path, "w:gz") as tar:
        for name, content in members:
            info = tarfile.TarInfo(name=name)
            info.size = len(content)
            tar.addfile(info, BytesIO(content))


def test_normalize_public_github_url_accepts_only_repository_urls():
    repo = normalize_public_github_url("https://github.com/deepseek-ai/deepseek-harness.git")
    assert repo.slug == "deepseek-ai/deepseek-harness"
    assert repo.url == "https://github.com/deepseek-ai/deepseek-harness"


@pytest.mark.parametrize(
    "value",
    [
        "http://github.com/a/b",
        "https://gitlab.com/a/b",
        "https://github.com/a/b/issues/1",
        "https://user:pass@github.com/a/b",
        "https://github.com:443/a/b",
        "https://github.com/a/b?ref=main",
        "https://github.com/a/b#readme",
        "https://github.com/../b",
    ],
)
def test_normalize_public_github_url_rejects_non_public_repo_shapes(value):
    with pytest.raises(LiveScanError):
        normalize_public_github_url(value)


def test_extract_archive_strips_github_root_and_ignores_symlinks(tmp_path):
    archive = tmp_path / "repo.tar.gz"
    with tarfile.open(archive, "w:gz") as tar:
        content = b'{"name":"demo"}'
        info = tarfile.TarInfo("owner-repo-sha/package.json")
        info.size = len(content)
        tar.addfile(info, BytesIO(content))

        link = tarfile.TarInfo("owner-repo-sha/escape")
        link.type = tarfile.SYMTYPE
        link.linkname = "/etc/passwd"
        tar.addfile(link)

    root = _extract_archive(archive, tmp_path / "out")
    assert (root / "package.json").read_bytes() == b'{"name":"demo"}'
    assert not (root / "escape").exists()


def test_extract_archive_rejects_parent_traversal(tmp_path):
    archive = tmp_path / "repo.tar.gz"
    _write_tar(archive, [("owner-repo-sha/../../escape.txt", b"nope")])

    with pytest.raises(LiveScanError, match="unsafe path"):
        _extract_archive(archive, tmp_path / "out")
    assert not (tmp_path / "escape.txt").exists()


def test_extract_archive_enforces_file_limit(tmp_path):
    archive = tmp_path / "repo.tar.gz"
    _write_tar(
        archive,
        [
            ("owner-repo-sha/a.txt", b"a"),
            ("owner-repo-sha/b.txt", b"b"),
        ],
    )

    with pytest.raises(LiveScanError) as exc:
        _extract_archive(archive, tmp_path / "out", max_files=1)
    assert exc.value.code == "repository_too_large"


def test_scan_public_github_uses_real_scanner_contract(monkeypatch, tmp_path):
    archive = tmp_path / "fixture.tar.gz"
    _write_tar(
        archive,
        [
            (
                "owner-repo-sha/package.json",
                b'{"name":"demo","dependencies":{"node-pty":"1.0.0"}}',
            ),
            ("owner-repo-sha/src/index.js", b'console.log("hello")'),
        ],
    )

    def fake_download(repo, destination, **kwargs):
        destination.write_bytes(archive.read_bytes())

    monkeypatch.setattr(live_scan, "_download_archive", fake_download)
    payload = scan_public_github("https://github.com/example/demo")

    assert payload["path"] == "example/demo"
    assert payload["repository"] == "https://github.com/example/demo"
    assert payload["stack"] == ["node"]
    assert isinstance(payload["score"], int)
    assert payload["strategy"] in {"native", "hybrid", "proot"}
    assert any(item["kind"] == "node-native" for item in payload["findings"])
