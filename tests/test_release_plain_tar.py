from pocketport.release import select_asset


def test_plain_tar_source_archive_is_rejected_before_scoring():
    assets = [
        {
            "name": "tool-android-arm64-source.tar",
            "browser_download_url": "https://x/source",
        },
        {
            "name": "tool-linux-arm64.tar.gz",
            "browser_download_url": "https://x/binary",
        },
    ]

    choice = select_asset(assets, "aarch64")

    assert choice is not None
    assert choice.name == "tool-linux-arm64.tar.gz"
