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


def test_x86_only_shell_is_flagged(tmp_path: Path):
    (tmp_path / "install.sh").write_text("URL=https://example/x86_64/tool.tar.gz\n")
    report = scan(tmp_path)
    assert any(f.kind == "architecture" for f in report.findings)


def test_nested_workspace_node_native_dependency_is_detected(tmp_path: Path):
    workspace = tmp_path / "packages" / "terminal"
    workspace.mkdir(parents=True)
    (tmp_path / "package.json").write_text('{"workspaces":["packages/*"]}\n', encoding="utf-8")
    (workspace / "package.json").write_text(
        '{"dependencies":{"node-pty":"^1.0.0"}}\n', encoding="utf-8"
    )

    report = scan(tmp_path)

    assert "node" in report.stack
    assert any(
        f.kind == "node-native"
        and "node-pty" in f.detail
        and f.path == "packages/terminal/package.json"
        and f.scope == "runtime"
        for f in report.findings
    )


def test_nested_cargo_workspace_is_included_in_stack(tmp_path: Path):
    (tmp_path / "package.json").write_text('{"name":"mono"}\n', encoding="utf-8")
    native = tmp_path / "native" / "helper"
    native.mkdir(parents=True)
    (native / "Cargo.toml").write_text('[package]\nname="helper"\nversion="0.1.0"\n', encoding="utf-8")

    report = scan(tmp_path)

    assert "node" in report.stack
    assert "rust" in report.stack


def test_ignored_test_workspace_does_not_affect_stack_or_findings(tmp_path: Path):
    (tmp_path / "package.json").write_text('{"name":"app"}\n', encoding="utf-8")
    ignored = tmp_path / "tests" / "fixture"
    ignored.mkdir(parents=True)
    (ignored / "Cargo.toml").write_text('[package]\nname="fixture"\nversion="0.1.0"\n', encoding="utf-8")
    (ignored / "package.json").write_text(
        '{"dependencies":{"node-pty":"^1.0.0"}}\n', encoding="utf-8"
    )

    report = scan(tmp_path)

    assert "rust" not in report.stack
    assert not any("node-pty" in f.detail for f in report.findings)


def test_ci_only_linux_assumptions_do_not_lower_runtime_score(tmp_path: Path):
    (tmp_path / "package.json").write_text('{"name":"app"}\n', encoding="utf-8")
    workflow = tmp_path / ".github" / "workflows"
    workflow.mkdir(parents=True)
    (workflow / "ci.yml").write_text(
        "steps:\n  - run: sudo apt-get install glibc-tools && echo x86_64\n",
        encoding="utf-8",
    )

    report = scan(tmp_path)

    ci_findings = [f for f in report.findings if f.path == ".github/workflows/ci.yml"]
    assert ci_findings
    assert all(f.scope == "ci" for f in ci_findings)
    assert report.strategy == "native"
    assert report.score == 100


def test_lockfile_assumptions_are_metadata_not_runtime_penalties(tmp_path: Path):
    (tmp_path / "package.json").write_text('{"name":"app"}\n', encoding="utf-8")
    (tmp_path / "pnpm-lock.yaml").write_text(
        "notes: glibc ld-linux x86_64 apt-get\n",
        encoding="utf-8",
    )

    report = scan(tmp_path)

    lock_findings = [f for f in report.findings if f.path == "pnpm-lock.yaml"]
    assert lock_findings
    assert all(f.scope == "metadata" for f in lock_findings)
    assert report.strategy == "native"
    assert report.score == 100


def test_dev_native_dependency_is_visible_but_lightweight(tmp_path: Path):
    (tmp_path / "package.json").write_text(
        '{"name":"app","devDependencies":{"playwright":"^1.0.0","node-pty":"^1.0.0"}}\n',
        encoding="utf-8",
    )

    report = scan(tmp_path)

    risky = [f for f in report.findings if f.kind == "node-native"]
    assert len(risky) == 2
    assert all(f.scope == "dev" for f in risky)
    assert report.strategy == "native"
    assert report.score >= 98


def test_runtime_native_dependency_risks_do_not_force_hybrid_by_count(tmp_path: Path):
    (tmp_path / "package.json").write_text(
        '{"name":"app","dependencies":{'
        '"playwright":"^1.0.0","node-pty":"^1.0.0","sharp":"^1.0.0"}}\n',
        encoding="utf-8",
    )

    report = scan(tmp_path)

    assert report.strategy == "native"
    assert report.score == 91


def test_build_script_linux_assumption_is_scoped_as_build(tmp_path: Path):
    (tmp_path / "package.json").write_text('{"name":"app"}\n', encoding="utf-8")
    (tmp_path / "build-native.sh").write_text("apt-get install clang\n", encoding="utf-8")

    report = scan(tmp_path)

    finding = next(f for f in report.findings if f.kind == "linux-assumption")
    assert finding.scope == "build"
    assert report.strategy == "native"
    assert report.score >= 97
