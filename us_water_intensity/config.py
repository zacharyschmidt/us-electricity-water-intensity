"""Paths and shared constants for the U.S. water-intensity pipeline.

Every stage imports its file paths and column names from here, so this file is
also a map of what the pipeline reads and writes. All paths are absolute.
"""

from pathlib import Path
from typing import NamedTuple

REPO = Path(__file__).resolve().parents[1]
DATA = REPO / "data"
RESULTS = REPO / "results"
PLOTS = REPO / "figures"
EXTERNAL = DATA / "external"          # gitignored raw EIA / Reitz downloads

# --- Inputs -----------------------------------------------------------------
EGRID_EXCEL_DIR = DATA / "egrid"                     # one eGRID workbook per vintage
EGRID_2020_XLSX = EGRID_EXCEL_DIR / "eGRID2020_data_metric_v2.xlsx"   # PLNT20 for hydro
EGRID_2014_XLSX = EGRID_EXCEL_DIR / "eGRID2014_Data_v2.xlsx"          # PLNT14 pre-2014 plants
AEO_DIR = DATA / "aeo_2026"                          # EIA AEO 2026 API pulls (cached CSVs)
AEO_CO2_CSV = AEO_DIR / "aeo_projection_co2_v2.csv"
AEO_GEN_CSVS = [AEO_DIR / "aeo_projection_net_generation_full.csv",
                AEO_DIR / "aeo_projection_net_generation_renew_v3.csv"]
SHARE_CSV = DATA / "crosswalks/share_emm_egrid_fuel.csv"     # EMM region -> eGRID subregion shares
PLANT_XWALK_CSV = DATA / "crosswalks/plant_emm_egrid.csv"    # EIA plant -> eGRID subregion
COUNTY_EMM_CSV = DATA / "crosswalks/county_emm_lookup.csv"   # county -> EMM region
PEER_CSV = DATA / "peer_water_factors_egrid.csv"             # Peer et al. 2019 factors (l/kWh)
TD_LOSSES_CSV = DATA / "td_losses_by_year.csv"
SIDDIK_DAMS_CSV = DATA / "siddik2024/hydro_dam_lookup.csv"
DAM_ET_CF_CSV = DATA / "siddik2024/dam_counterfactual_et.csv"
EIA860_DIR = EXTERNAL / "eia860"
EIA923_DIR = EXTERNAL / "eia923"
PANEL_CACHE_DIR = EXTERNAL / "panel_cache"           # 8D reporting-history panel, 2014-2025
EIA_CACHE = EXTERNAL / "eia_cache"                   # pickled EIA loader results (stage 3)

# --- Intermediate files (data/) ---------------------------------------------
EGRID_HISTORY_CSV = DATA / "net_generation_egrid_from_script_no_prms_with_co2.csv"   # stage 1
GENERATION_CSV = DATA / "net_generation_egrid_aeo_projections_with_co2.csv"          # stage 2
AEO_2025_GENERATION_CSV = DATA / "aeo_2025_generation_by_subregion.csv"              # stage 2
WATER_FACTORS_CSV = DATA / "water_factors_by_year.csv"                               # stage 3
WATER_TYPE_SHARES_CSV = DATA / "water_type_shares_by_year.csv"                       # stage 3
THERMO_FUEL_COOLING_CSV = DATA / "eia_thermo_factors_fuel_cooling_by_year.csv"       # stage 3
THERMO_MULTIPLIERS_CSV = DATA / "thermo_climate_multipliers.csv"                     # stage 3
HYDRO_FACTORS_CSV = DATA / "hydro_factors_by_case.csv"                               # stage 4
HEADLINE_SUMMARY_CSV = DATA / "generation_and_water_intensity_summaryV3.csv"         # stage 5
HYDRO_VOLUMES_CSV = DATA / "hydro_volumes_by_case.csv"                               # stage 6

# --- Result series read by more than one module (results/) --------------------
NATIONAL_TS_CSV = RESULTS / "national_timeseries_by_case.csv"                        # stage 5
NATIONAL_TS_CONUS_CSV = RESULTS / "national_timeseries_by_case_conus.csv"            # stage 5
NATIONAL_TS_FIXEDVOL_CSV = RESULTS / "national_timeseries_by_case_fixedvol.csv"      # stage 6
NATIONAL_TS_FIXEDVOL_CONUS_CSV = RESULTS / "national_timeseries_by_case_fixedvol_conus.csv"

# --- Unit conversions -----------------------------------------------------------
SHORT_TON_TO_METRIC = 0.907185
ACRE_M2 = 4046.86

# --- Column names -------------------------------------------------------------
YEAR = "Data Year"
ACRONYM = "eGRID subregion acronym"
NAME = "eGRID subregion name"
HYDRO_COL = "eGRID subregion annual hydro net generation (MWh)"
NATIONAL = "National"

# Generation column -> water-factor column. The order is the summation order
# of the intensity engine, so do not reorder it.
SOURCE_MAPPING = {
    "eGRID subregion annual coal net generation (MWh)": "Coal",
    "eGRID subregion annual oil net generation (MWh)": "Oil",
    "eGRID subregion annual gas net generation (MWh)": "Gas",
    "eGRID subregion annual nuclear net generation (MWh)": "Nuclear",
    HYDRO_COL: "Hydro",
    "eGRID subregion annual biomass net generation (MWh)": "Biomass",
    "eGRID subregion annual wind net generation (MWh)": "Wind",
    "eGRID subregion annual solar net generation (MWh)": "Solar",
    "eGRID subregion annual geothermal net generation (MWh)": "Geothermal",
    "eGRID subregion annual other fossil net generation (MWh)": "Other fossil",
    "eGRID subregion annual other unknown/ purchased fuel net generation (MWh)":
        "Other unknown/purchased",
}

# Factor columns whose water is thermoelectric cooling. The two "Other" columns
# carry the Oil and Gas factors.
THERMAL_FUELS = ["Coal", "Oil", "Gas", "Nuclear", "Biomass", "Other fossil", "Other unknown/purchased"]
THERMAL_ALIASES = {"Other fossil": "Oil", "Other unknown/purchased": "Gas"}
# EIA-860 cooling water types, in the order the share tables use.
WATER_TYPES = ["fresh", "reclaimed", "brackish", "saline", "unknown"]

# Subregions outside the contiguous US (excluded from the CONUS series).
NON_CONUS_SUBS = ["AKGD", "AKMS", "HIMS", "HIOA"]


# --- Hydro allocation cases -------------------------------------------------
class HydroCase(NamedTuple):
    column: str              # column in hydro_factors_by_case.csv
    label: str
    description: str
    anchor_year: int | None  # fixed-volume anchor: the vintage of the factor's own generation denominator


HYDRO_CASES = {
    "a":      HydroCase("hydro_a_gross_all",        "A",      "gross evaporation, all to hydro", 2020),
    "b1":     HydroCase("hydro_b1_gross_eqweight",  "B",      "gross evaporation, equal portion to each use", 2020),
    "b2":     HydroCase("hydro_b2_fraction_ah",     "B2",     "gross evaporation, fixed fraction to hydro", 2020),
    "c1":     HydroCase("hydro_c1_gross_primary",   "C1",     "gross evaporation, primary-purpose", 2020),
    "a_net":  HydroCase("hydro_a_net_all",          "A-net",  "net evaporation, all to hydro", 2020),
    "b1_net": HydroCase("hydro_b1_net_eqweight",    "B-net",  "net evaporation, equal portion to each use", 2020),
    "b2_net": HydroCase("hydro_b2_net_fraction_ah", "B2-net", "net evaporation, fixed fraction to hydro", 2020),
    "c1_net": HydroCase("hydro_c1_net_primary",     "C1-net", "net evaporation, primary-purpose (Siddik dams)", 2020),
    "c2":     HydroCase("hydro_c2_net_primary",     "C2",     "net evaporation, primary-purpose (Peer 2019)", 2014),
    "d":      HydroCase("hydro_d_zero",             "D",      "hydro excluded", None),
}
CASE_ORDER = list(HYDRO_CASES)
CASE_COLUMNS = {k: c.column for k, c in HYDRO_CASES.items()}
# Case behind the single-series headline tables.
HEADLINE_CASE = "c2"

# --- AEO projections ------------------------------------------------------------
ANCHOR_YEAR = 2025                    # last eGRID year. AEO is rebased onto it
PROJECTION_YEARS = range(2026, 2031)

# Subregion names used for every year (the eGRID 2023 names).
EGRID_SUBREGION_NAMES = {
    "AKGD": "ASCC Alaska Grid", "AKMS": "ASCC Miscellaneous", "AZNM": "WECC Southwest",
    "CAMX": "WECC California", "ERCT": "ERCOT All", "FRCC": "FRCC All",
    "HIMS": "HICC Miscellaneous", "HIOA": "HICC Oahu", "MROE": "MRO East", "MROW": "MRO West",
    "NEWE": "NPCC New England", "NWPP": "WECC Northwest", "NYCW": "NPCC NYC/Westchester",
    "NYLI": "NPCC Long Island", "NYUP": "NPCC Upstate NY", "PRMS": "Puerto Rico Miscellaneous",
    "RFCE": "RFC East", "RFCM": "RFC Michigan", "RFCW": "RFC West", "RMPA": "WECC Rockies",
    "SPNO": "SPP North", "SPSO": "SPP South", "SRMV": "SERC Mississippi Valley",
    "SRMW": "SERC Midwest", "SRSO": "SERC South", "SRTV": "SERC Tennessee Valley",
    "SRVC": "SERC Virginia/Carolina",
}
