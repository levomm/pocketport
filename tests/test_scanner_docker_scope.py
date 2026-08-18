from pathlib import Path

from pocketport.scanner import scan


def test_dockerfile_linux_assumptions_are_build_scoped(tmp_path: Path):
    dockerfile = tmp_path / "app" / "server" / "Dockerfile"
    dockerfile.parent.mkdir(parents=True)
    dockerfile.write_text(
        "FROM golang:1.23\nRUN apt-get update && apt-get install -y gcc\n",
        encoding="utf-8",
    )

    report = scan(tmp_path)

    findings = [
        finding
        for finding in report.findings
        if finding.path == "app/server/Dockerfile"
        and finding.kind == "linux-assumption"
    ]
    assert findings
    assert all(finding.scope == "build" for finding in findings)
