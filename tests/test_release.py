from pocketport.release import normalize_arch, select_asset


def test_normalize_arm64():
    assert normalize_arch("arm64") == "aarch64"
    assert normalize_arch("aarch64") == "aarch64"


def test_normalize_i386_family():
    assert normalize_arch("i386") == "x86"
    assert normalize_arch("i486") == "x86"
    assert normalize_arch("i586") == "x86"
    assert normalize_arch("i686") == "x86"


def test_selects_i586_asset_for_i586_request():
    assets = [
        {"name": "tool-linux-i586.tar.gz", "browser_download_url": "https://x/i586"},
        {"name": "tool-linux-amd64.tar.gz", "browser_download_url": "https://x/amd64"},
    ]
    choice = select_asset(assets, "i586")
    assert choice is not None
    assert choice.name == "tool-linux-i586.tar.gz"


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


def test_selects_x86_64_for_x86_64_request():
    assets = [
        {"name": "tool-linux-arm64.tar.gz", "browser_download_url": "https://x/arm64"},
        {"name": "tool-linux-amd64.tar.gz", "browser_download_url": "https://x/amd64"},
    ]
    choice = select_asset(assets, "x86_64")
    assert choice is not None
    assert choice.name == "tool-linux-amd64.tar.gz"


def test_x86_request_does_not_accept_x86_64_only_asset():
    assets = [
        {"name": "tool-linux-x86_64.tar.gz", "browser_download_url": "https://x/x64"},
    ]
    assert select_asset(assets, "x86") is None


def test_underscore_delimited_x86_is_recognized():
    assets = [
        {"name": "tool-x86_linux.tar.gz", "browser_download_url": "https://x/x86"},
    ]
    assert select_asset(assets, "aarch64") is None
    choice = select_asset(assets, "x86")
    assert choice is not None
    assert choice.name == "tool-x86_linux.tar.gz"


def test_x86_dash_64_is_classified_as_x86_64():
    assets = [
        {"name": "tool-linux-x86-64.tar.gz", "browser_download_url": "https://x/x64"},
    ]
    assert select_asset(assets, "x86") is None
    choice = select_asset(assets, "x86_64")
    assert choice is not None
    assert choice.name == "tool-linux-x86-64.tar.gz"


def test_win32_x86_does_not_beat_linux_asset():
    assets = [
        {"name": "tool-linux.tar.gz", "browser_download_url": "https://x/linux"},
        {"name": "tool-win32-x86.zip", "browser_download_url": "https://x/win32"},
    ]
    choice = select_asset(assets, "x86")
    assert choice is not None
    assert choice.name == "tool-linux.tar.gz"


def test_win_component_arm64_is_rejected():
    assets = [
        {"name": "tool-linux-arm64.tar.gz", "browser_download_url": "https://x/linux"},
        {"name": "tool-win-arm64.zip", "browser_download_url": "https://x/win"},
    ]
    choice = select_asset(assets, "aarch64")
    assert choice is not None
    assert choice.name == "tool-linux-arm64.tar.gz"


def test_freebsd_asset_is_rejected_before_arch_score():
    assets = [
        {"name": "tool-linux.tar.gz", "browser_download_url": "https://x/linux"},
        {"name": "tool-freebsd-amd64.tar.gz", "browser_download_url": "https://x/freebsd"},
    ]
    choice = select_asset(assets, "x86_64")
    assert choice is not None
    assert choice.name == "tool-linux.tar.gz"


def test_mingw_target_is_rejected_before_arch_score():
    assets = [
        {"name": "tool-linux.tar.gz", "browser_download_url": "https://x/linux"},
        {"name": "tool-x86_64-w64-mingw32.zip", "browser_download_url": "https://x/mingw"},
    ]
    choice = select_asset(assets, "x86_64")
    assert choice is not None
    assert choice.name == "tool-linux.tar.gz"


def test_msvc_target_is_rejected_before_arch_score():
    assets = [
        {"name": "tool-linux.tar.gz", "browser_download_url": "https://x/linux"},
        {"name": "tool-msvc-x64.zip", "browser_download_url": "https://x/msvc"},
    ]
    choice = select_asset(assets, "x86_64")
    assert choice is not None
    assert choice.name == "tool-linux.tar.gz"


def test_macosx_target_is_rejected():
    assets = [
        {"name": "tool-linux.tar.gz", "browser_download_url": "https://x/linux"},
        {"name": "tool-macosx-amd64.zip", "browser_download_url": "https://x/macosx"},
    ]
    choice = select_asset(assets, "x86_64")
    assert choice is not None
    assert choice.name == "tool-linux.tar.gz"


def test_darwin64_target_is_rejected():
    assets = [
        {"name": "tool-linux.tar.gz", "browser_download_url": "https://x/linux"},
        {"name": "tool-darwin64-amd64.zip", "browser_download_url": "https://x/darwin64"},
    ]
    choice = select_asset(assets, "x86_64")
    assert choice is not None
    assert choice.name == "tool-linux.tar.gz"


def test_checksum_asset_is_rejected():
    assets = [
        {
            "name": "tool-linux-aarch64.tar.gz.sha256",
            "browser_download_url": "https://x/checksum",
        },
    ]
    assert select_asset(assets, "aarch64") is None


def test_sha384_sidecar_is_rejected():
    assets = [
        {"name": "tool-amd64.sha384", "browser_download_url": "https://x/sha384"},
        {"name": "tool-linux.tar.gz", "browser_download_url": "https://x/linux"},
    ]
    choice = select_asset(assets, "x86_64")
    assert choice is not None
    assert choice.name == "tool-linux.tar.gz"


def test_checksum_text_wrapper_is_rejected():
    assets = [
        {
            "name": "tool-android-arm64.tar.gz.sha256.txt",
            "browser_download_url": "https://x/checksum-text",
        },
        {
            "name": "tool-linux-arm64.tar.gz",
            "browser_download_url": "https://x/binary",
        },
    ]
    choice = select_asset(assets, "aarch64")
    assert choice is not None
    assert choice.name == "tool-linux-arm64.tar.gz"


def test_signature_asset_is_rejected_even_with_good_markers():
    assets = [
        {
            "name": "tool-android-arm64.tar.gz.sig",
            "browser_download_url": "https://x/sig",
        },
    ]
    assert select_asset(assets, "aarch64") is None


def test_minisig_asset_is_rejected():
    assets = [
        {
            "name": "tool-android-arm64.tar.gz.minisig",
            "browser_download_url": "https://x/minisig",
        },
    ]
    assert select_asset(assets, "aarch64") is None


def test_binary_name_containing_checksum_is_not_rejected():
    assets = [
        {
            "name": "checksum-linux-arm64.tar.gz",
            "browser_download_url": "https://x/binary",
        },
    ]
    choice = select_asset(assets, "aarch64")
    assert choice is not None
    assert choice.name == "checksum-linux-arm64.tar.gz"


def test_checksum_manifest_trailer_is_rejected():
    assets = [
        {
            "name": "tool-checksums.txt",
            "browser_download_url": "https://x/manifest",
        },
    ]
    assert select_asset(assets, "aarch64") is None


def test_singular_sha256sum_manifest_is_rejected():
    assets = [
        {
            "name": "tool-android-arm64.sha256sum.txt",
            "browser_download_url": "https://x/sha256sum",
        },
        {
            "name": "tool-linux-arm64.tar.gz",
            "browser_download_url": "https://x/binary",
        },
    ]
    choice = select_asset(assets, "aarch64")
    assert choice is not None
    assert choice.name == "tool-linux-arm64.tar.gz"
