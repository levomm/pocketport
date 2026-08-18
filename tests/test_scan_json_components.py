import json
from types import SimpleNamespace

from pocketport.cli import cmd_scan


def test_scan_json_includes_component_assessments(tmp_path, capsys):
    cli_dir = tmp_path / "app" / "cli"
    cli_dir.mkdir(parents=True)
    (cli_dir / "go.mod").write_text("module example.com/demo\n", encoding="utf-8")

    result = cmd_scan(SimpleNamespace(target=str(tmp_path), json=True))

    assert result == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["strategy"] == "native"
    assert payload["components"] == [
        {
            "name": "cli",
            "role": "client",
            "path": "app/cli",
            "stack": ["go"],
            "score": 100,
            "strategy": "native",
        }
    ]


def test_scan_json_omits_components_when_none_exist(tmp_path, capsys):
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname="demo"\nversion="0.1"\n', encoding="utf-8"
    )

    result = cmd_scan(SimpleNamespace(target=str(tmp_path), json=True))

    assert result == 0
    payload = json.loads(capsys.readouterr().out)
    assert "components" not in payload
