from pathlib import Path
from pocketport.scanner import scan


def test_clean_python_repo_is_native(tmp_path: Path):
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname="demo"\nversion="0.1"\n', encoding="utf-8"
    )
    report = scan(tmp_path)
    assert "python" in report.stack
    assert report.strategy == "native"
    assert report.score >= 90


def test_cuda_repo_is_not_native(tmp_path: Path):
    (tmp_path / "Dockerfile").write_text(
        "FROM nvidia/cuda:12.0.0-base\nRUN nvidia-smi\n", encoding="utf-8"
    )
    report = scan(tmp_path)
    assert report.strategy in {"hybrid", "proot"}
    assert report.score < 80


def test_systemd_is_flagged(tmp_path: Path):
    (tmp_path / "install.sh").write_text(
        "#!/bin/sh\nsudo systemctl enable demo\n", encoding="utf-8"
    )
    report = scan(tmp_path)
    assert any(f.detail == "systemd service control" for f in report.findings)


def test_docs_do_not_create_false_blockers(tmp_path: Path):
    (tmp_path / "README.md").write_text(
        "This documentation discusses systemctl, CUDA and glibc.", encoding="utf-8"
    )
    report = scan(tmp_path)
    assert report.strategy == "native"
    assert report.score == 100


def test_python_risky_dependency_is_detected(tmp_path: Path):
    (tmp_path / "requirements.txt").write_text("llama-cpp-python==0.3.0\n", encoding="utf-8")
    report = scan(tmp_path)
    assert any("llama-cpp-python" in f.detail for f in report.findings)
