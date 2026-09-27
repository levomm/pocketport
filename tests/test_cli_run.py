from __future__ import annotations

from types import SimpleNamespace

import pocketport.cli as cli


def _args(*parts: str):
    return SimpleNamespace(command_args=list(parts))


def test_run_github_url_prepares_without_executing_outside_termux(monkeypatch, capsys):
    monkeypatch.setenv("PREFIX", "/usr")
    monkeypatch.setattr(cli, "prepare_public_github", lambda repository: {
        "repository": repository,
        "repo_root": "/tmp/workspace/repo",
        "installer": "/tmp/workspace/repo/termux-install.sh",
        "runner": "/tmp/workspace/repo/termux-run.sh",
        "patch": {"changes": []},
        "execution_plan": {
            "status": "ready",
            "method": "source",
            "component": {"strategy": "native"},
        },
    })

    called = []
    monkeypatch.setattr(cli.subprocess, "run", lambda *args, **kwargs: called.append((args, kwargs)))

    result = cli.cmd_run(_args("https://github.com/example/demo"))

    assert result == 0
    assert called == []
    output = capsys.readouterr().out
    assert "prepared successfully" in output
    assert "termux-install.sh" in output


def test_run_github_url_requires_approval_in_noninteractive_termux(monkeypatch, capsys):
    monkeypatch.setenv("PREFIX", "/data/data/com.termux/files/usr")
    monkeypatch.setattr(cli, "prepare_public_github", lambda repository: {
        "repository": repository,
        "repo_root": "/tmp/workspace/repo",
        "installer": "/tmp/workspace/repo/termux-install.sh",
        "runner": "/tmp/workspace/repo/termux-run.sh",
        "patch": {"changes": [{"rule": "demo"}]},
        "execution_plan": {
            "status": "ready",
            "method": "source",
            "component": {"strategy": "native"},
        },
    })
    monkeypatch.setattr(cli.sys.stdin, "isatty", lambda: False)

    called = []
    monkeypatch.setattr(cli.subprocess, "run", lambda *args, **kwargs: called.append((args, kwargs)))

    result = cli.cmd_run(_args("https://github.com/example/demo"))

    assert result == 4
    assert called == []
    assert "without interactive approval" in capsys.readouterr().err


def test_run_github_url_yes_executes_installer_then_runner(monkeypatch):
    monkeypatch.setenv("PREFIX", "/data/data/com.termux/files/usr")
    monkeypatch.setattr(cli, "prepare_public_github", lambda repository: {
        "repository": repository,
        "repo_root": "/tmp/workspace/repo",
        "installer": "/tmp/workspace/repo/termux-install.sh",
        "runner": "/tmp/workspace/repo/termux-run.sh",
        "patch": {"changes": []},
        "execution_plan": {
            "status": "ready",
            "method": "source",
            "component": {"strategy": "native"},
        },
    })

    calls = []

    class Result:
        def __init__(self, code=0):
            self.returncode = code

    def fake_run(args, cwd=None, check=False):
        calls.append((args, cwd, check))
        return Result(0)

    monkeypatch.setattr(cli.subprocess, "run", fake_run)

    result = cli.cmd_run(_args("--yes", "https://github.com/example/demo"))

    assert result == 0
    assert calls == [
        (["/tmp/workspace/repo/termux-install.sh"], "/tmp/workspace/repo", False),
        (["/tmp/workspace/repo/termux-run.sh"], "/tmp/workspace/repo", False),
    ]


def test_run_command_mode_stays_backward_compatible(monkeypatch):
    monkeypatch.setenv("PREFIX", "/data/data/com.termux/files/usr")
    seen = []
    monkeypatch.setattr(cli, "run_compat", lambda command: seen.append(command) or 17)

    result = cli.cmd_run(_args("--", "node", "app.js"))

    assert result == 17
    assert seen == [["node", "app.js"]]
