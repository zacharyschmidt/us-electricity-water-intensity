"""Stage 1: eGRID history.

Reads the subregion (SRL) sheet of every eGRID workbook in data/egrid/
(1998-2025), maps each workbook's column headers onto one schema, renames
the pre-2001 subregions to their modern equivalents, and adds a National row per
year (the sum of all subregions except Puerto Rico and offshore, which are dropped).
"""

import re

import numpy as np
import pandas as pd

from us_water_intensity import config

OUTPUTS = [config.EGRID_HISTORY_CSV]

FUEL_NEEDLES = {
    "Coal": ["coal net"],
    "Oil": ["oil net"],
    "Gas": ["gas net"],
    "Nuclear": ["nuclear net"],
    "Hydro": ["hydro net"],
    "Biomass": ["biomass net", "biomass/ wood net"],
    "Wind": ["wind net"],
    "Solar": ["solar net"],
    "Geothermal": ["geothermal net"],
    "Other fossil": ["other fossil net", "fossil (tires, batteries, chemicals, etc.) net"],
    "Other unknown/purchased": ["unknown", "purchased"],
}
CAPACITY = "eGRID subregion nameplate capacity (MW)"
SOLID_WASTE = "eGRID subregion annual solid waste net generation (MWh)"
CO2 = "eGRID subregion annual CO2 emissions"

TARGET_COLUMNS = {
    config.YEAR: ["data year"],
    config.ACRONYM: ["subrgn", "acronym"],
    config.NAME: ["srname", "name"],
    CAPACITY: ["namepcap", "pca capacity", "nameplate capacity"],
    **{col: FUEL_NEEDLES[fuel] for col, fuel in config.SOURCE_MAPPING.items()},
    SOLID_WASTE: ["solid waste net"],
    CO2: ["annual co2 emissions"],
}

# 1998-2000 subregions -> modern eGRID subregion.
# CISO was called CALI in 1999 and 2000.
LEGACY_REGIONS = {
    "CISO": "CAMX", "CALI": "CAMX", "ECMI": "RFCM", "ECOV": "RFCW", "MAAC": "RFCE",
    "MANN": "RFCW", "MANS": "SRMW", "MAPP": "MROW", "NWGB": "NWPP", "NWPN": "NWPP",
    "OFFG": "OFFG", "ROCK": "NWPP", "WSSW": "AZNM",
}
LEGACY_YEARS = (1998, 1999, 2000)


def load_srl_sheets():
    sheets = {}
    for path in sorted(config.EGRID_EXCEL_DIR.glob("*.xls*")):
        for sheet in pd.ExcelFile(path).sheet_names:
            if "SRL" in sheet.upper():
                sheets[f"{path.stem}_{sheet}"] = pd.read_excel(path, sheet_name=sheet)
    return sheets


def clean_srl_dataframe(df, key):
    """Map one raw SRL sheet onto TARGET_COLUMNS.

    The header row is one of the first five rows, and some vintages have a second
    row of field abbreviations below it. Pre-2018 vintages report CO2
    in short tons. Vintages without a Data Year column take the year from the file name.
    """
    table = pd.DataFrame(np.vstack([df.columns, df]))
    row_text = [" ".join(str(x).lower() for x in row if not pd.isna(x)) for row in table.to_numpy()[:5]]
    header_row = max(i for i, t in enumerate(row_text) if "egrid subregion name" in t)
    data_start = max((i + 1 for i, t in enumerate(row_text) if "srname" in t), default=None)
    headers = table.iloc[header_row].to_numpy()
    data = table.iloc[data_start:]

    mapping = {}            # header position -> output column
    co2_factor = 1
    for target, needles in TARGET_COLUMNS.items():
        for i, header in enumerate(headers):
            text = str(header).lower()
            if not pd.isna(header) and any(n in text for n in needles):
                mapping[i] = target
                if target == CO2 and "metric" not in text:
                    co2_factor = config.SHORT_TON_TO_METRIC
                break

    out = pd.DataFrame({target: data.iloc[:, i] for i, target in mapping.items()})
    if CO2 in out:
        out = out.assign(**{CO2: pd.to_numeric(out[CO2], errors="coerce") * co2_factor})
    if config.YEAR not in out:
        out = out.assign(**{config.YEAR: int(re.search(r"(?:eGRID)?(\d{4})", key).group(1))})
    return out.reindex(columns=list(TARGET_COLUMNS))


def combine(sheets):
    """Concatenate the cleaned sheets and make the numeric columns numeric."""
    df = pd.concat([clean_srl_dataframe(raw, key) for key, raw in sheets.items()], ignore_index=True)
    numeric = [c for c in df.columns if "generation" in c.lower() or "capacity" in c.lower()]
    return df.assign(
        **{config.YEAR: pd.to_numeric(df[config.YEAR], errors="coerce")},
        **{c: pd.to_numeric(df[c].astype(str).str.replace(",", ""), errors="coerce") for c in numeric},
    )


def apply_region_mapping(df):
    """Rename 1998-2000 subregions and sum rows that now share an acronym."""
    legacy = df[config.YEAR].isin(LEGACY_YEARS)
    acronym = df[config.ACRONYM].where(~legacy, df[config.ACRONYM].replace(LEGACY_REGIONS))
    return (df.assign(**{config.ACRONYM: acronym})
            .astype({c: float for c in df.columns if "MW" in c})
            .loc[lambda d: d[config.ACRONYM] != "SUBRGN"]
            .groupby([config.YEAR, config.ACRONYM]).sum()
            .reset_index())


def add_national_totals(df):
    """Drop PRMS and OFFG, then prepend a National row (sum of subregions) to each year."""
    def with_national(group):
        national = (group.sum(numeric_only=True).to_frame().T
                    .assign(**{config.ACRONYM: config.NATIONAL, config.NAME: config.NATIONAL}))
        return pd.concat([national, group]).reset_index(drop=True)

    return (df.loc[lambda d: ~d[config.ACRONYM].isin(["PRMS", "OFFG"])]
            .groupby([config.YEAR])
            .apply(with_national, include_groups=False)
            .reset_index()
            .drop(columns=["level_1"]))


def main():
    (combine(load_srl_sheets())
     .pipe(apply_region_mapping)
     .pipe(add_national_totals)
     .to_csv(config.EGRID_HISTORY_CSV, index=False))


if __name__ == "__main__":
    main()
