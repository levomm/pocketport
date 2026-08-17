import json
from pathlib import Path
from pocketport.patcher import patch_repo


def test_shell_patches_safe_commands(tmp_path: Path):
    script = tmp_path / "install.sh"
    script.write_text(
        "#!/bin/bash\n"
        "sudo apt-get update\n"
        "sudo apt-get install -y build-essential python3 libssl-dev git\n"
        "xdg-open https://example.com\n",
        encoding="utf-8",
    )

    report = patch_repo(tmp_path)
    text = script.read_text("utf-8")

    assert text.startswith("#!/data/data/com.termux/files/usr/bin/bash\n")
    assert "pkg update -y" in text
    assert "pkg install -y clang make pkg-config python openssl git" in text
    assert "termux-open https://example.com" in text
    assert "sudo " not in text
    assert len(report.changes) >= 4


def test_dry_run_does_not_write(tmp_path: Path):
    script = tmp_path / "x.sh"
    original = "#!/bin/bash\nsudo echo hi\n"
    script.write_text(original)

    report = patch_repo(tmp_path, dry_run=True)

    assert report.files_changed == ["x.sh"]
    assert script.read_text() == original
    assert not (tmp_path / ".pocketport").exists()


def test_package_json_scripts_are_patched(tmp_path: Path):
    p = tmp_path / "package.json"
    p.write_text(json.dumps({
        "name": "demo",
        "scripts": {"open": "sudo xdg-open http://localhost:3000"},
    }))

    report = patch_repo(tmp_path)
    data = json.loads(p.read_text())

    assert data["scripts"]["open"] == "termux-open http://localhost:3000"
    assert "package.json" in report.files_changed


def test_complex_apt_line_is_not_rewritten(tmp_path: Path):
    script = tmp_path / "x.sh"
    original = "sudo apt-get install foo && echo done\n"
    script.write_text(original)

    report = patch_repo(tmp_path)

    assert script.read_text() == original
    assert not report.files_changed


def test_patched_termux_shebang_is_not_flagged_again(tmp_path: Path):
    from pocketport.scanner import scan

    script = tmp_path / "x.sh"
    script.write_text("#!/bin/bash\necho ok\n")
    patch_repo(tmp_path)
    report = scan(tmp_path)

    assert not any(f.kind == "patchable" and "bash path" in f.detail for f in report.findings)
