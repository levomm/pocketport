from pocketport.release import normalize_arch, select_asset


def test_normalize_arm64():
    assert normalize_arch("arm64") == "aarch64"
    assert normalize_arch("aarch64") == "aarch64"


def test_selects_arm64_linux_asset():
    assets = [
        {"name": "tool-linux-amd64.tar.gz", "browser_download_url": "https://x/amd64"},
        {"name": "tool-linux-arm64.tar.gz", "browser_download_url": "https://x/arm64"},
        {"name": "tool-windows-arm64.zip", "browser_download_url": "https://x/win"},
    ]
    choice = select_asset(assets, "aarch64")
    assert choice is not None
    assert choice.name == "tool-linux-arm64.tar.gz"


def test_prefers_android_over_linux():
    assets = [
        {"name": "tool-linux-aarch64.tar.gz", "browser_download_url": "https://x/linux"},
        {"name": "tool-android-arm64.tar.gz", "browser_download_url": "https://x/android"},
    ]
    choice = select_asset(assets, "aarch64")
    assert choice is not None
    assert choice.name == "tool-android-arm64.tar.gz"


def test_rejects_wrong_arch_only():
    assets = [
        {"name": "tool-linux-amd64.tar.gz", "browser_download_url": "https://x/amd64"},
    ]
    assert select_asset(assets, "aarch64") is None
