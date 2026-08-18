from pathlib import Path

from pocketport.runtime import compat_env, ensure_node_atomic_publish_shim


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


def test_shim_only_falls_back_for_atomic_publish_shapes(tmp_path: Path):
    shim = ensure_node_atomic_publish_shim(tmp_path).read_text("utf-8")

    assert "code === 'EACCES' || code === 'EPERM'" in shim
    assert "sourceName.startsWith(`${targetName}.`)" in shim
    assert "sourceName.endsWith('.tmp')" in shim
    assert "sourceName === `${targetName}.tmp`" in shim
    assert "stagingDirName.startsWith(`.${targetName}.`)" in shim
    assert "stagingDirName.endsWith('.tmpdir')" in shim
    assert "COPYFILE_EXCL" in shim
    assert "syncBuiltinESMExports()" in shim
