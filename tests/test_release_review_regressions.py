from pocketport.release import select_asset


def test_ios_asset_is_rejected_before_arch_score():
    assets = [
        {"name": "tool-linux.tar.gz", "browser_download_url": "https://x/linux"},
        {"name": "tool-ios-amd64.zip", "browser_download_url": "https://x/ios"},
        {"name": "tool-iphoneos-amd64.zip", "browser_download_url": "https://x/iphoneos"},
    ]

    choice = select_asset(assets, "x86_64")

    assert choice is not None
    assert choice.name == "tool-linux.tar.gz"


def test_sbom_and_provenance_assets_are_rejected():
    assets = [
        {"name": "tool-linux.tar.gz", "browser_download_url": "https://x/linux"},
        {"name": "tool-amd64.spdx.json", "browser_download_url": "https://x/spdx"},
        {"name": "tool-amd64.sbom.json", "browser_download_url": "https://x/sbom"},
        {"name": "tool-amd64.provenance.json", "browser_download_url": "https://x/provenance"},
    ]

    choice = select_asset(assets, "x86_64")

    assert choice is not None
    assert choice.name == "tool-linux.tar.gz"


def test_source_archive_tar_aliases_are_rejected():
    binary = {"name": "tool-linux.tar.gz", "browser_download_url": "https://x/linux"}
    source_names = (
        "tool-android-amd64-source.txz",
        "tool-android-amd64-source.tbz2",
        "tool-android-amd64-source.tar.lz",
        "tool-android-amd64-source.tar.lzma",
        "tool-android-amd64-source.tzst",
    )

    for source_name in source_names:
        choice = select_asset(
            [binary, {"name": source_name, "browser_download_url": "https://x/source"}],
            "x86_64",
        )
        assert choice is not None
        assert choice.name == "tool-linux.tar.gz"
