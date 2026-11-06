"""Download the EPA eGRID workbooks that stage 1 reads into data/egrid/.

    python -m us_water_intensity.fetch_egrid

Thirteen of the sixteen vintages come from EPA:
- 1998-2016: from EPA's historical archive, a single 157 MB zip. It is saved in
  data/external/ and only the eight workbooks used are extracted from it.
- 2018-2022: downloaded individually.

The other three vintages are committed to the repository in data/egrid/
"""

import hashlib
import zipfile

import requests

from us_water_intensity import config

EPA_FILES = "https://www.epa.gov/system/files"
ARCHIVE_URL = f"{EPA_FILES}/other-files/2023-01/egrid_historical_files_1996-2016.zip"
ARCHIVE_ZIP = config.EXTERNAL / "egrid_historical_files_1996-2016.zip"
ARCHIVE_SHA256 = "14503dcdf10c3d61a819a82be358e1c118991a6cf7f1901be291990104b74857"
ARCHIVE_FOLDER = "egrid_historical_files_1996-2016"   # folder inside the zip

# File name -> SHA-256, for the workbooks extracted from the archive.
FROM_ARCHIVE = {
    "eGRID1998_location.xls": "33d762b866738a85fecb840da1ea1aae1a2ac13a7354cc86ed669e2cdf6416e1",
    "eGRID1999_location.xls": "02f07fcfbae8b2f2f32fb2d22010228bfbb0bf0dbc35ef89b36b1384dbac0713",
    "eGRID2000_location.xls": "4debd50c2d7e53fa74a5cc0b4856784ed4ac751b1cfb556262b38d06846c9d9c",
    "eGRID2004_aggregation.xls": "48c3a413a1f5eb54e1604713efd1d523fd0dc94a23fb2582f9c0cb86d51a7104",
    "eGRID2005_aggregation.xls": "f9999d33145d0a0030d39754a60ed38385eedbe0dd34e5df45c7079ff30d8704",
    "eGRID2007_aggregation.xls": "d8d26c3eda1e3300c7ee52762a1e481108fe926d2ca53a91243c0b88dbd77561",
    "eGRID2014_Data_v2.xlsx": "4a70a27207904c72cb26532f2b2cd5c55de231ddad3302e9287648ba41f39af8",
    "egrid2016_data.xlsx": "21b8f7df0327eac3ff76d0240c92a328850d18a6ac5ba1469164374ba661f88f",
}

# File name -> (URL, SHA-256), for the workbooks downloaded one by one.
DIRECT = {
    "eGRID2018_data_metric_v2.xlsx": (
        f"{EPA_FILES}/documents/2023-01/eGRID2018_data_metric_v2.xlsx",
        "3d2f113a2c3ab897729e78493e29eed946ea5bf6e90011736febb68da2dcb87e"),
    "eGRID2019_data_metric_v2_0.xlsx": (
        f"{EPA_FILES}/documents/2023-01/eGRID2019_data_metric_v2_0.xlsx",
        "80e84b70ec2a59a1db4f68f945b05602dc3090ad61cb0f2db35ba7bb9c8fbbc8"),
    "eGRID2020_data_metric_v2.xlsx": (
        f"{EPA_FILES}/documents/2023-01/eGRID2020_data_metric_v2.xlsx",
        "d0a281ed259ad05d6c0b305e7170512e7a01d3b582c2affa56c20f0130ab43a3"),
    "eGRID2021_data_metric.xlsx": (
        f"{EPA_FILES}/documents/2023-01/eGRID2021_data_metric.xlsx",
        "b896809e9e9b4aa1bbe83ab48cfd0082cd36ec5e5735f3d181cb2a582481d571"),
    "egrid2022_data_metric.xlsx": (
        f"{EPA_FILES}/documents/2024-01/egrid2022_data_metric.xlsx",
        "52d9a7f0a36107290525850e66524dfc7a5521dcc3ace64c37bc5c248e57ef40"),
}


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def is_current(path, expected):
    return path.exists() and sha256(path) == expected


def check(path, expected):
    """Raise if `path` does not have the expected checksum."""
    actual = sha256(path)
    if actual != expected:
        raise RuntimeError(f"{path.name}: SHA-256 is {actual}, expected {expected}. "
                           "EPA may have replaced the file.")


def download(url, path):
    """Stream `url` to `path`, writing to a temporary name first so a failed download leaves nothing behind."""
    print(f"downloading {url}")
    part = path.with_name(path.name + ".part")
    with requests.get(url, stream=True, timeout=60) as r:
        r.raise_for_status()
        with open(part, "wb") as f:
            for chunk in r.iter_content(chunk_size=1 << 20):
                f.write(chunk)
    part.replace(path)


def fetch_archive_files():
    if all(is_current(config.EGRID_EXCEL_DIR / name, h) for name, h in FROM_ARCHIVE.items()):
        return
    if not is_current(ARCHIVE_ZIP, ARCHIVE_SHA256):
        download(ARCHIVE_URL, ARCHIVE_ZIP)
        check(ARCHIVE_ZIP, ARCHIVE_SHA256)
    with zipfile.ZipFile(ARCHIVE_ZIP) as z:
        for name, expected in FROM_ARCHIVE.items():
            target = config.EGRID_EXCEL_DIR / name
            if not is_current(target, expected):
                print(f"extracting {name}")
                target.write_bytes(z.read(f"{ARCHIVE_FOLDER}/{name}"))
                check(target, expected)


def fetch_direct_files():
    for name, (url, expected) in DIRECT.items():
        target = config.EGRID_EXCEL_DIR / name
        if not is_current(target, expected):
            download(url, target)
            check(target, expected)


def main():
    config.EGRID_EXCEL_DIR.mkdir(parents=True, exist_ok=True)
    config.EXTERNAL.mkdir(parents=True, exist_ok=True)
    fetch_archive_files()
    fetch_direct_files()
    print(f"eGRID workbooks are in {config.EGRID_EXCEL_DIR}")


if __name__ == "__main__":
    main()
