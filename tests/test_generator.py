import json

from pocketport.generator import render_install_script
from pocketport.scanner import ScanReport


def test_pnpm_repo_uses_declared_package_manager(tmp_path):
    (tmp_path / "package.json").write_text(
        json.dumps({"packageManager": "pnpm@11.7.0"}),
        encoding="utf-8",
    )
    (tmp_path / "pnpm-lock.yaml").write_text("lockfileVersion: '9.0'\n", encoding="utf-8")

    report = ScanReport(
        path=str(tmp_path),
        stack=["node"],
        score=100,
        strategy="native",
        findings=[],
    )

    script = render_install_script(report, tmp_path)

    assert "npm install -g pnpm@11.7.0" in script
    assert "pnpm install --frozen-lockfile" in script
    assert "else npm install" not in script
