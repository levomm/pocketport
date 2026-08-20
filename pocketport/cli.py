from __future__ import annotations

import argparse
from dataclasses import asdict
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tempfile

from .components import assess_components
from .doctor import inspect_runtime_capabilities
from .execution import build_execution_plan
from .scanner import scan
from .semantics import ArtifactProfile, semantic_scan
from .generator import write_generated
from .patcher import patch_repo
from .release import choose_release_asset, normalize_arch
from .runtime import run_compat


def _clone(url: str, dest: Path) -> Path:
    if not shutil.which("git"):
        raise SystemExit("git is required")
    subprocess.run(["git", "clone", "--depth", "1", url, str(dest)], check=True)
    return dest


def _resolve_target(target: str):
    p = Path(target).expanduser()
    if p.exists():
        return p.resolve(), None
    if target.startswith(("https://github.com/", "git@github.com:")):
        td = tempfile.TemporaryDirectory(prefix="pocketport-")
        path = Path(td.name) / "repo"
        _clone(target, path)
        return path, td
    raise SystemExit(f"Target does not exist and is not a GitHub URL: {target}")


def _print_report(report, artifact: ArtifactProfile) -> None:
    root = Path(report.path)
    print(f"PocketPort score: {report.score}/100")
    print(f"Strategy: {report.strategy}")
    print(f"Type: {artifact.type}")
    print(f"Stack: {', '.join(report.stack)}")
    if artifact.requirements:
        print("Requirements:")
        for requirement in artifact.requirements:
            print(f"- {requirement}")

    components = assess_components(root, report.findings)
    if components:
        print("Components:")
        for component in components[:12]:
            stack = ", ".join(component.stack)
            print(f"- {component.name:12} [{component.role}] {component.strategy} {component.score}/100 | {stack} [{component.path}]")

    plan = build_execution_plan(report, root)
    print("Execution plan:")
    print(f"- {plan.status} | {plan.method} | {plan.component.name} [{plan.component.path}] | {plan.component.strategy}")
    for command in plan.install:
        print(f"- install: {command}")
    if plan.run:
        print(f"- run: {plan.run[0]}")
    elif artifact.runnable:
        print("- run: unresolved")
    else:
        print("- run: not applicable")

    if report.findings:
        print("")
        for f in report.findings[:50]:
            loc = f" [{f.path}]" if f.path else ""
            print(f"- {f.severity.upper():6} [{f.scope}] {f.kind}: {f.detail}{loc}")
    else:
        print("No obvious Termux blockers found.")


def _json_report(report, artifact: ArtifactProfile) -> dict:
    root = Path(report.path)
    payload = report.to_dict()
    payload["artifact"] = artifact.to_dict()
    components = assess_components(root, report.findings)
    if components:
        payload["components"] = [asdict(component) for component in components]
    payload["execution_plan"] = build_execution_plan(report, root).to_dict()
    return payload


def cmd_scan(args) -> int:
    root, td = _resolve_target(args.target)
    try:
        report, artifact = semantic_scan(root)
        if args.json:
            print(json.dumps(_json_report(report, artifact), indent=2))
        else:
            _print_report(report, artifact)
        return 0
    finally:
        if td:
            td.cleanup()


def cmd_patch(args) -> int:
    root = Path(args.path).expanduser().resolve()
    before = scan(root)
    report = patch_repo(root, dry_run=args.dry_run, backup=args.backup)
    print(f"Patch mode: {'dry-run' if args.dry_run else 'write'}")
    print(f"Files changed: {len(report.files_changed)}")
    print(f"Changes: {len(report.changes)}")
    for change in report.changes[:50]:
        print(f"- {change.path}: {change.rule}")
        if args.verbose:
            print(f"    - {change.before}")
            print(f"    + {change.after}")
    for warning in report.warnings:
        print(f"! {warning}")
    if not args.dry_run:
        after = scan(root)
        print(f"Score: {before.score}/100 -> {after.score}/100")
        print(f"Strategy: {before.strategy} -> {after.strategy}")
    return 0


def cmd_generate(args) -> int:
    root = Path(args.path).expanduser().resolve()
    report = scan(root)
    script = write_generated(report, root)
    print(f"Wrote {script}")
    print(f"Strategy: {report.strategy} | score={report.score}/100")
    return 0


def cmd_prepare(args) -> int:
    root = Path(args.path).expanduser().resolve()
    before = scan(root)
    patch = patch_repo(root, dry_run=False, backup=args.backup)
    after = scan(root)
    script = write_generated(after, root)
    print(f"Patched {len(patch.files_changed)} files ({len(patch.changes)} changes)")
    print(f"Score: {before.score}/100 -> {after.score}/100")
    print(f"Strategy: {before.strategy} -> {after.strategy}")
    print(f"Wrote {script}")
    return 0


def cmd_run(args) -> int:
    command = list(args.command_args)
    if command and command[0] == "--":
        command = command[1:]
    if not command:
        print("Usage: pocketport run -- <command> [args...]", file=sys.stderr)
        return 2
    if "com.termux" in os.environ.get("PREFIX", ""):
        print("[PocketPort] Termux runtime compatibility enabled")
    return run_compat(command)


def cmd_asset(args) -> int:
    arch = normalize_arch(args.arch)
    try:
        choice = choose_release_asset(args.repo, tag=args.tag, arch=arch)
    except (RuntimeError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(f"Architecture: {arch}")
    if choice is None:
        print("No suitable release asset found.")
        return 2
    if args.json:
        print(json.dumps(choice.to_dict(), indent=2))
    else:
        print(f"Asset: {choice.name}")
        print(f"Score: {choice.score}")
        print(f"URL: {choice.url}")
        print(f"Why: {', '.join(choice.reason)}")
    return 0


def cmd_doctor(args) -> int:
    prefix = os.environ.get("PREFIX", "")
    termux = "com.termux" in prefix
    machine = platform.machine()
    print(f"Termux: {'yes' if termux else 'no'}")
    print(f"Python: {sys.version.split()[0]}")
    print(f"Machine: {machine}")
    print(f"PocketPort arch: {normalize_arch(machine)}")
    print(f"Platform: {platform.platform()}")
    for cmd in ["git", "python", "node", "npm", "clang", "cmake", "rustc", "cargo", "go", "proot-distro"]:
        print(f"{cmd:13} {'ok' if shutil.which(cmd) else 'missing'}")
    if termux:
        print("PREFIX:", prefix)
    print("\nRuntime capabilities:")
    for capability in inspect_runtime_capabilities():
        detail = f" - {capability.detail}" if capability.detail else ""
        print(f"{capability.name:22} {capability.status}{detail}")
    return 0


def build_parser():
    p = argparse.ArgumentParser(prog="pocketport", description="Make desktop-first GitHub projects less hostile to Android/Termux.")
    sub = p.add_subparsers(dest="command", required=True)

    s = sub.add_parser("scan", help="scan a local repo or GitHub URL")
    s.add_argument("target")
    s.add_argument("--json", action="store_true")
    s.set_defaults(func=cmd_scan)

    patch = sub.add_parser("patch", help="safely auto-patch a local repo for Termux")
    patch.add_argument("path", nargs="?", default=".")
    patch.add_argument("--dry-run", action="store_true")
    patch.add_argument("--backup", action="store_true")
    patch.add_argument("-v", "--verbose", action="store_true")
    patch.set_defaults(func=cmd_patch)

    prep = sub.add_parser("prepare", help="patch, rescan and generate a Termux installer")
    prep.add_argument("path", nargs="?", default=".")
    prep.add_argument("--backup", action="store_true")
    prep.set_defaults(func=cmd_prepare)

    run = sub.add_parser("run", help="run a command with Termux runtime compatibility shims")
    run.add_argument("command_args", nargs=argparse.REMAINDER)
    run.set_defaults(func=cmd_run)

    asset = sub.add_parser("asset", help="choose the best GitHub release asset for Android/Termux")
    asset.add_argument("repo", help="owner/name or GitHub repository URL")
    asset.add_argument("--tag", default="latest")
    asset.add_argument("--arch")
    asset.add_argument("--json", action="store_true")
    asset.set_defaults(func=cmd_asset)

    g = sub.add_parser("generate", help="generate Termux install assets in a local repo")
    g.add_argument("path", nargs="?", default=".")
    g.set_defaults(func=cmd_generate)

    d = sub.add_parser("doctor", help="inspect the current Android/Termux toolchain")
    d.set_defaults(func=cmd_doctor)
    return p


def main():
    args = build_parser().parse_args()
    raise SystemExit(args.func(args))


if __name__ == "__main__":
    main()
