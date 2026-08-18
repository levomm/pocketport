from pathlib import Path

from pocketport.runtime import (
    compat_env,
    ensure_node_atomic_publish_shim,
    prepare_linux_release_compat,
)


def test_termux_env_injects_atomic_publish_shim(tmp_path: Path):
    env = {
        "PREFIX": "/data/data/com.termux/files/usr",
        "HOME": str(tmp_path),
    }

    result = compat_env(env, home=tmp_path)
    shim = tmp_path / ".pocketport" / "shims" / "node-atomic-publish.cjs"

    assert shim.exists()
    assert result["POCKETPORT_NODE_ATOMIC_PUBLISH_FALLBACK"] == "1"
    assert f"--require={shim}" in result["NODE_OPTIONS"]


def test_non_termux_env_is_unchanged(tmp_path: Path):
    env = {"PREFIX": "/usr", "NODE_OPTIONS": "--trace-warnings"}

    result = compat_env(env, home=tmp_path)

    assert result == env
    assert not (tmp_path / ".pocketport").exists()


def test_shim_only_falls_back_for_known_atomic_publish_shapes(tmp_path: Path):
    shim = ensure_node_atomic_publish_shim(tmp_path).read_text("utf-8")

    assert "code === 'EACCES' || code === 'EPERM'" in shim
    assert "sourceName.startsWith(`${targetName}.`)" in shim
    assert "sourceName.endsWith('.tmp')" in shim
    assert "sourceName === `${targetName}.tmp`" in shim
    assert "stagingDirName.startsWith(`.${targetName}.`)" in shim
    assert "stagingDirName.endsWith('.tmpdir')" in shim
    assert "COPYFILE_EXCL" in shim
    assert "syncBuiltinESMExports()" in shim


def test_external_elf_gets_termux_dns_and_ca_overlay(tmp_path: Path):
    prefix = tmp_path / "data" / "data" / "com.termux" / "files" / "usr"
    termux_resolv = prefix / "etc" / "resolv.conf"
    cert_bundle = prefix / "etc" / "tls" / "cert.pem"
    termux_resolv.parent.mkdir(parents=True)
    cert_bundle.parent.mkdir(parents=True)
    termux_resolv.write_text("nameserver 8.8.8.8\n", "utf-8")
    cert_bundle.write_text("test-ca\n", "utf-8")

    binary = tmp_path / "plandex"
    binary.write_bytes(b"\x7fELF" + b"static-go-release" * 16)
    system_resolv = tmp_path / "system-resolv.conf"
    system_resolv.write_text("", "utf-8")
    env = {"PREFIX": str(prefix), "PATH": "/usr/bin"}

    command, result_env = prepare_linux_release_compat(
        [str(binary), "version"],
        env,
        system_resolv=system_resolv,
        proot_executable="/usr/bin/proot",
    )

    assert command == [
        "/usr/bin/proot",
        "-b",
        f"{termux_resolv}:/etc/resolv.conf",
        str(binary),
        "version",
    ]
    assert result_env["SSL_CERT_FILE"] == str(cert_bundle)
    assert result_env["POCKETPORT_TERMUX_CA_BUNDLE"] == "1"
    assert result_env["POCKETPORT_TERMUX_DNS_OVERLAY"] == "1"


def test_android_elf_is_not_wrapped(tmp_path: Path):
    prefix = tmp_path / "data" / "data" / "com.termux" / "files" / "usr"
    binary = tmp_path / "termux-tool"
    binary.write_bytes(b"\x7fELF" + b"/system/bin/linker64" + b"android" * 16)
    env = {"PREFIX": str(prefix), "PATH": "/usr/bin"}

    command, result_env = prepare_linux_release_compat(
        [str(binary), "--help"],
        env,
        system_resolv=tmp_path / "missing-resolv.conf",
        proot_executable="/usr/bin/proot",
    )

    assert command == [str(binary), "--help"]
    assert result_env == env
