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
    original = "#!/bin/bash\nsudo git --version\n"
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


def test_node_import_argument_is_joined_for_termux_wrapper(tmp_path: Path):
    p = tmp_path / "package.json"
    p.write_text(json.dumps({
        "name": "demo",
        "scripts": {"dev": "node --import tsx/esm apps/cli/src/bin.ts web"},
    }))

    patch_repo(tmp_path)
    data = json.loads(p.read_text())

    assert data["scripts"]["dev"] == "node --import=tsx/esm apps/cli/src/bin.ts web"


def test_node_require_argument_is_joined_for_termux_wrapper(tmp_path: Path):
    p = tmp_path / "package.json"
    p.write_text(json.dumps({
        "name": "demo",
        "scripts": {"dev": "node --require tsx/cjs scripts/dev.cjs"},
    }))

    patch_repo(tmp_path)
    data = json.loads(p.read_text())

    assert data["scripts"]["dev"] == "node --require=tsx/cjs scripts/dev.cjs"


def test_tsx_script_launcher_uses_node_import_hook(tmp_path: Path):
    p = tmp_path / "package.json"
    p.write_text(json.dumps({
        "name": "demo",
        "devDependencies": {"tsx": "^4.0.0"},
        "scripts": {"build": "tsx scripts/build.ts --profile official"},
    }))

    patch_repo(tmp_path)
    data = json.loads(p.read_text())

    assert data["scripts"]["build"] == "node --import=tsx/esm scripts/build.ts --profile official"


def test_tsdown_uses_tsx_config_loader_when_available(tmp_path: Path):
    p = tmp_path / "package.json"
    p.write_text(json.dumps({
        "name": "demo",
        "devDependencies": {"tsx": "^4.0.0", "tsdown": "^0.22.0"},
        "scripts": {
            "build": "tsc -b tsconfig.host.json && tsdown --env.DSH_BUILD_FACE host"
        },
    }))

    patch_repo(tmp_path)
    data = json.loads(p.read_text())

    assert data["scripts"]["build"] == (
        "tsc -b tsconfig.host.json && tsdown --config-loader tsx --env.DSH_BUILD_FACE host"
    )


def test_tsdown_existing_config_loader_is_preserved(tmp_path: Path):
    p = tmp_path / "package.json"
    original = "tsdown --config-loader unrun --env.FACE host"
    p.write_text(json.dumps({
        "name": "demo",
        "devDependencies": {"tsx": "^4.0.0", "tsdown": "^0.22.0"},
        "scripts": {"build": original},
    }))

    report = patch_repo(tmp_path)
    data = json.loads(p.read_text())

    assert data["scripts"]["build"] == original
    assert not report.files_changed


def test_tsdown_is_not_rewritten_without_tsx_dependency(tmp_path: Path):
    p = tmp_path / "package.json"
    original = "tsdown --env.FACE host"
    p.write_text(json.dumps({
        "name": "demo",
        "devDependencies": {"tsdown": "^0.22.0"},
        "scripts": {"build": original},
    }))

    report = patch_repo(tmp_path)
    data = json.loads(p.read_text())

    assert data["scripts"]["build"] == original
    assert not report.files_changed


def test_complex_apt_line_is_not_rewritten(tmp_path: Path):
    script = tmp_path / "x.sh"
    original = "sudo apt-get install foo && echo done\n"
    script.write_text(original)

    report = patch_repo(tmp_path)

    assert script.read_text() == original
    assert not report.files_changed


def test_chained_update_is_not_rewritten(tmp_path: Path):
    script = tmp_path / "x.sh"
    original = "apt-get update && apt-get install -y curl\n"
    script.write_text(original)

    report = patch_repo(tmp_path)

    assert script.read_text() == original
    assert not report.files_changed


def test_sudo_inside_quoted_data_is_not_removed(tmp_path: Path):
    script = tmp_path / "x.sh"
    original = 'grep "sudo " input.txt\n'
    script.write_text(original)

    report = patch_repo(tmp_path)

    assert script.read_text() == original
    assert not report.files_changed


def test_sudo_options_are_left_untouched(tmp_path: Path):
    script = tmp_path / "x.sh"
    original = "sudo -E env FOO=bar command\n"
    script.write_text(original)

    report = patch_repo(tmp_path)

    assert script.read_text() == original
    assert not report.files_changed


def test_sudo_comment_is_left_untouched(tmp_path: Path):
    script = tmp_path / "x.sh"
    original = "sudo # explanation\n"
    script.write_text(original)

    report = patch_repo(tmp_path)

    assert script.read_text() == original
    assert not report.files_changed


def test_sudo_redirection_is_left_untouched(tmp_path: Path):
    script = tmp_path / "x.sh"
    original = "sudo > /tmp/log\n"
    script.write_text(original)

    report = patch_repo(tmp_path)

    assert script.read_text() == original
    assert not report.files_changed


def test_sudo_shell_only_dot_builtin_is_left_untouched(tmp_path: Path):
    script = tmp_path / "x.sh"
    original = "sudo . ./env.sh\n"
    script.write_text(original)

    report = patch_repo(tmp_path)

    assert script.read_text() == original
    assert not report.files_changed


def test_sudo_double_bracket_builtin_is_left_untouched(tmp_path: Path):
    script = tmp_path / "x.sh"
    original = "sudo [[ -e file ]]\n"
    script.write_text(original)

    report = patch_repo(tmp_path)

    assert script.read_text() == original
    assert not report.files_changed


def test_sudo_named_shell_builtin_is_left_untouched(tmp_path: Path):
    script = tmp_path / "x.sh"
    original = "sudo source ./env.sh\n"
    script.write_text(original)

    report = patch_repo(tmp_path)

    assert script.read_text() == original
    assert not report.files_changed


def test_sudo_colon_builtin_is_left_untouched(tmp_path: Path):
    script = tmp_path / "x.sh"
    original = "sudo :\n"
    script.write_text(original)

    report = patch_repo(tmp_path)

    assert script.read_text() == original
    assert not report.files_changed


def test_sudo_unknown_command_is_left_untouched(tmp_path: Path):
    script = tmp_path / "x.sh"
    original = "sudo custom-project-command --flag\n"
    script.write_text(original)

    report = patch_repo(tmp_path)

    assert script.read_text() == original
    assert not report.files_changed


def test_standalone_sudo_is_left_untouched(tmp_path: Path):
    script = tmp_path / "x.sh"
    original = "sudo\n"
    script.write_text(original)

    report = patch_repo(tmp_path)

    assert script.read_text() == original
    assert not report.files_changed


def test_package_json_standalone_sudo_is_left_untouched(tmp_path: Path):
    p = tmp_path / "package.json"
    p.write_text(json.dumps({
        "name": "demo",
        "scripts": {"check": "sudo"},
    }))

    report = patch_repo(tmp_path)
    data = json.loads(p.read_text())

    assert data["scripts"]["check"] == "sudo"
    assert not report.files_changed


def test_sudo_removal_preserves_line_endings(tmp_path: Path):
    script = tmp_path / "x.sh"
    script.write_text("sudo git status\ngit --version\n")

    patch_repo(tmp_path)

    assert script.read_text() == "git status\ngit --version\n"


def test_sudo_executable_path_is_stripped(tmp_path: Path):
    script = tmp_path / "x.sh"
    script.write_text("sudo ./install-helper --check\n")

    patch_repo(tmp_path)

    assert script.read_text() == "./install-helper --check\n"


def test_make_recipe_control_prefix_sudo_is_patched(tmp_path: Path):
    makefile = tmp_path / "Makefile"
    makefile.write_text("check:\n\t@sudo git --version\n\t-sudo git status\n")

    patch_repo(tmp_path)

    assert makefile.read_text() == "check:\n\t@git --version\n\t-git status\n"


def test_make_recipe_spaced_control_prefixes_are_patched(tmp_path: Path):
    makefile = tmp_path / "Makefile"
    makefile.write_text("check:\n\t@ -sudo git --version\n\t+ @ sudo git status\n")

    patch_repo(tmp_path)

    assert makefile.read_text() == "check:\n\t@ -git --version\n\t+ @ git status\n"


def test_make_recipe_control_prefix_package_manager_is_patched(tmp_path: Path):
    makefile = tmp_path / "Makefile"
    makefile.write_text("deps:\n\t+sudo apt-get update\n")

    patch_repo(tmp_path)

    assert makefile.read_text() == "deps:\n\t+pkg update -y\n"


def test_shebang_arguments_are_preserved(tmp_path: Path):
    script = tmp_path / "x.sh"
    script.write_text("#!/bin/bash -e\necho ok\n")

    patch_repo(tmp_path)

    assert script.read_text().startswith(
        "#!/data/data/com.termux/files/usr/bin/bash -e\n"
    )


def test_package_option_with_value_is_not_rewritten(tmp_path: Path):
    script = tmp_path / "x.sh"
    original = "apt-get install -t bookworm curl\n"
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
