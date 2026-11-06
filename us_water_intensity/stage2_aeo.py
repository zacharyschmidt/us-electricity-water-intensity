"""Stage 2: splice eGRID history (1998-2025) with AEO 2026 projections (2026-2030).

1. Read the stage-1 eGRID history and check the 2025 hydro anchor.
2. Load AEO 2026 generation and CO2 by EMM region and convert to MWh and metric tons.
3. Split each EMM region's value across eGRID subregions with the fuel-specific
   share table data/crosswalks/share_emm_egrid_fuel.csv.
4. Rebase each (subregion, series) projection onto its eGRID 2025 value, keeping
   AEO's year-over-year growth, so 2025 -> 2026 has no jump. Series that
   AEO lacks are held at their 2025 value.

    python -m us_water_intensity.stage2_aeo
    -> data/net_generation_egrid_aeo_projections_with_co2.csv  (generation by subregion, 1998-2030)
       data/aeo_2025_generation_by_subregion.csv               (AEO's own 2025, for the stage-5 overlay)
       results/aeo_projection_net_generation_for_excel.csv     (complete year x subregion grid)
"""

import numpy as np
import pandas as pd

from us_water_intensity import common, config

EXCEL_CSV = config.RESULTS / "aeo_projection_net_generation_for_excel.csv"
OUTPUTS = [config.GENERATION_CSV, config.AEO_2025_GENERATION_CSV, EXCEL_CSV]

# A subregion's anchor-year hydro must sit within this band aroundits 2014-2024 median.
ANCHOR_HYDRO_BAND = (0.55, 1.5)
MIN_BASELINE_MWH = 500_000

# AEO seriesName -> (eGRID generation column, share-table fuel key).
# End-Use Sectors fossil series add industrial/commercial CHP, which eGRID
# counts but the Electric Power Sector series exclude. Biomass uses the
# All Sectors series (EPS + industrial CHP) to match eGRID's scope.
# "Solar (All)" / "Wind (All)" are the sums of AEO's per-technology rows.
AEO_SERIES = {
    "Electricity : Electric Power Sector : Generation : Coal":
        ("eGRID subregion annual coal net generation (MWh)", "coal"),
    "Electricity : Electric Power Sector : Generation : Natural Gas":
        ("eGRID subregion annual gas net generation (MWh)", "gas"),
    "Electricity : Electric Power Sector : Generation : Nuclear":
        ("eGRID subregion annual nuclear net generation (MWh)", "nuclear"),
    "Electricity : Electric Power Sector : Generation : Petroleum":
        ("eGRID subregion annual oil net generation (MWh)", "oil"),
    "Renewable Energy : Electric Power Sector : Electricity Generation : Biogenic Municipal Waste":
        ("eGRID subregion annual biomass net generation (MWh)", "biomass"),
    "Renewable Energy : Electric Power Sector : Electricity Generation : Geothermal":
        ("eGRID subregion annual geothermal net generation (MWh)", "geothermal"),
    "Renewable Energy : Electric Power Sector : Electricity Generation : Hydropower":
        ("eGRID subregion annual hydro net generation (MWh)", "hydro"),
    "Renewable Energy : Electric Power Sector : Electricity Generation : Solar (All)":
        ("eGRID subregion annual solar net generation (MWh)", "solar"),
    "Renewable Energy : Electric Power Sector : Electricity Generation : Wind (All)":
        ("eGRID subregion annual wind net generation (MWh)", "wind"),
    "Renewable Energy : All Sectors : Electricity Generation : Wood and Other Biomass":
        ("eGRID subregion annual biomass net generation (MWh)", "biomass"),
    "Electricity : End-Use Sectors : Generation : Natural Gas":
        ("eGRID subregion annual gas net generation (MWh)", "gas"),
    "Electricity : End-Use Sectors : Generation : Coal":
        ("eGRID subregion annual coal net generation (MWh)", "coal"),
    "Electricity : End-Use Sectors : Generation : Petroleum":
        ("eGRID subregion annual oil net generation (MWh)", "oil"),
    "Electricity : End-Use Sectors : Generation : Other Gaseous Fuels":
        ("eGRID subregion annual other fossil net generation (MWh)", "other_fossil"),
    "Electricity : End-Use Sectors : Generation : Other":
        ("eGRID subregion annual other unknown/ purchased fuel net generation (MWh)", "other"),
    "Electricity : Emissions : Carbon Dioxide":
        ("eGRID subregion annual CO2 emissions", "co2"),
}
SERIES_MAP = (pd.DataFrame.from_dict(AEO_SERIES, orient="index", columns=["egrid_series", "fuel"])
              .rename_axis("seriesName").reset_index())
CO2_SERIES = "Electricity : Emissions : Carbon Dioxide"
EPS_BIOMASS = "Renewable Energy : Electric Power Sector : Electricity Generation : Wood and Other Biomass"
SOLAR_ALL = "Renewable Energy : Electric Power Sector : Electricity Generation : Solar (All)"
WIND_ALL = "Renewable Energy : Electric Power Sector : Electricity Generation : Wind (All)"

EXCEL_COLUMNS = [
    config.YEAR, config.ACRONYM, config.NAME,
    "eGRID subregion nameplate capacity (MW)",
    *config.SOURCE_MAPPING,
]


def check_anchor_hydro(egrid):
    """Stop if a material subregion's anchor-year hydro is far outside its recent range.

    Every projection is rebased on the anchor year, so a bad anchor would distort 2026-2030.
    """
    hydro = (egrid
             .loc[lambda df: df[config.ACRONYM] != config.NATIONAL]
             .pivot(index=config.ACRONYM, columns=config.YEAR, values=config.HYDRO_COL))
    baseline = hydro.loc[:, 2014:2024].median(axis=1)
    ratio = (hydro[config.ANCHOR_YEAR] / baseline).loc[baseline.abs() >= MIN_BASELINE_MWH]
    outside = ratio.loc[~ratio.between(*ANCHOR_HYDRO_BAND)]
    assert outside.empty, f"anchor-year hydro outside {ANCHOR_HYDRO_BAND} x the 2014-2024 median:\n{outside}"
    return egrid


def load_aeo_long():
    """AEO rows as (regionName, period, value, seriesName) generation in MWh, CO2 in metric tons."""
    raw = pd.concat([pd.read_csv(p) for p in config.AEO_GEN_CSVS], ignore_index=True)
    solar_wind = {s for s in raw["seriesName"].dropna().unique()
                  if "Electric Power Sector : Electricity Generation" in s and ("Solar" in s or "Wind" in s)}
    needed = (set(AEO_SERIES) - {CO2_SERIES} | solar_wind) - {EPS_BIOMASS}
    gen = (raw
           .loc[lambda df: df["seriesName"].isin(needed) & (df["regionName"] != "No Regional Tables")]
           .assign(value=lambda df: pd.to_numeric(df["value"]) * 1e6)       # BkWh -> MWh
           [["regionName", "period", "value", "seriesName"]])

    def technology_total(pattern, name):
        return (gen.loc[lambda df: df["seriesName"].str.contains(pattern)]
                .groupby(["regionName", "period"], as_index=False).agg(value=("value", "sum"))
                .assign(seriesName=name))

    co2 = (pd.read_csv(config.AEO_CO2_CSV)
           .assign(value=lambda df: pd.to_numeric(df["value"]) * config.SHORT_TON_TO_METRIC * 1e6)
           [["regionName", "period", "value", "seriesName"]])
    return (pd.concat([gen, technology_total("Solar", SOLAR_ALL), technology_total("Wind", WIND_ALL), co2],
                      ignore_index=True)
            .assign(period=lambda df: pd.to_numeric(df["period"]).astype(int))
            .astype({"regionName": str, "seriesName": str}))


def apportion_aeo_to_egrid(aeo_long, share_table):
    """Split EMM-region values onto eGRID subregions with the fuel-specific shares.

    Returns (Data Year, eGRID subregion acronym, seriesName = eGRID column, calc_value).
    The per-technology solar and wind rows drop out here, we keep their sums.
    """
    return (aeo_long
            .loc[lambda df: ~df["regionName"].isin(["United States", "No Regional Tables"])
                 & df["seriesName"].isin(AEO_SERIES)]
            .merge(SERIES_MAP, on="seriesName", how="left")
            .merge(share_table[["emm_region_name", "egrid_subregion", "fuel", "share"]],
                   left_on=["regionName", "fuel"], right_on=["emm_region_name", "fuel"], how="left")
            .loc[lambda df: df["egrid_subregion"].notna()]
            .assign(calc_value=lambda df: df["value"] * df["share"])
            .groupby(["period", "egrid_subregion", "egrid_series"], as_index=False)["calc_value"].sum()
            .rename(columns={"period": config.YEAR, "egrid_subregion": config.ACRONYM,
                             "egrid_series": "seriesName"})
            .sort_values([config.YEAR, config.ACRONYM, "seriesName"])
            .reset_index(drop=True))


def extend_with_projections(egrid_long, aeo):
    """eGRID rows through the anchor year, rebased AEO rows, constant fallback rows and National.

    """
    key = [config.ACRONYM, "seriesName"]
    cols = [config.YEAR, config.ACRONYM, config.NAME, "seriesName", "calc_value"]
    hist = (egrid_long
            .loc[lambda df: df[config.YEAR] <= config.ANCHOR_YEAR]
            .assign(calc_value=lambda df: pd.to_numeric(df["value"], errors="coerce")))
    anchor = hist.loc[lambda df: df[config.YEAR] == config.ANCHOR_YEAR]

    # Scale each projected series so that AEO's own anchor-year value lands on eGRID's.
    proj = aeo.loc[lambda df: df[config.YEAR].isin(config.PROJECTION_YEARS)]
    idx = pd.MultiIndex.from_frame(proj[key])
    e = anchor.groupby(key)["calc_value"].sum().reindex(idx).to_numpy(dtype=float)
    a = (aeo.loc[lambda df: df[config.YEAR] == config.ANCHOR_YEAR]
         .groupby(key)["calc_value"].sum().reindex(idx).to_numpy(dtype=float))
    with np.errstate(divide="ignore", invalid="ignore"):
        scale = np.where(np.isfinite(e) & np.isfinite(a) & (a > 0) & (e > 0), e / a, 1.0)
    # Projected rows take their name from EGRID_SUBREGION_NAMES in main().
    proj = proj.assign(calc_value=proj["calc_value"] * scale, **{config.NAME: proj[config.ACRONYM]})

    # Series AEO does not project are held at their anchor-year value.
    in_aeo = pd.MultiIndex.from_frame(anchor[key]).isin(idx)
    held = anchor.loc[~in_aeo & (anchor[config.ACRONYM] != config.NATIONAL).to_numpy()]
    fallback = pd.concat([held.assign(**{config.YEAR: y}) for y in config.PROJECTION_YEARS])

    future = pd.concat([proj[cols], fallback[cols]], ignore_index=True)
    national = (future.groupby([config.YEAR, "seriesName"], as_index=False)["calc_value"].sum()
                .assign(**{config.ACRONYM: config.NATIONAL, config.NAME: config.NATIONAL}))
    return pd.concat([hist[cols], future, national[cols]], ignore_index=True)


def aeo_2025_table(aeo):
    """AEO 2026's own anchor-year generation by subregion, in the generation-table layout."""
    return (aeo.loc[lambda df: df[config.YEAR] == config.ANCHOR_YEAR]
            .pivot_table(index=config.ACRONYM, columns="seriesName", values="calc_value", aggfunc="sum")
            .reset_index()
            .assign(**{config.YEAR: config.ANCHOR_YEAR,
                       config.NAME: lambda df: df[config.ACRONYM].map(config.EGRID_SUBREGION_NAMES)})
            .reindex(columns=[config.YEAR, config.ACRONYM, config.NAME, *config.SOURCE_MAPPING], fill_value=0.0))


def excel_table(pivot):
    """Every (year, subregion) pair, National dropped, sorted. missing years left blank."""
    regions = pivot[[config.ACRONYM, config.NAME]].drop_duplicates()
    years = pd.DataFrame({config.YEAR: sorted(pivot[config.YEAR].unique())})
    return (years.merge(regions, how="cross")
            .merge(pivot, on=[config.YEAR, config.ACRONYM, config.NAME], how="left")
            .loc[lambda df: df[config.ACRONYM] != config.NATIONAL]
            .sort_values([config.YEAR, config.ACRONYM])
            [EXCEL_COLUMNS]
            .reset_index(drop=True))


def main():
    egrid = common.read_generation(config.EGRID_HISTORY_CSV).pipe(check_anchor_hydro)
    id_vars = [config.YEAR, config.NAME, config.ACRONYM]
    aeo = apportion_aeo_to_egrid(load_aeo_long(), pd.read_csv(config.SHARE_CSV))
    pivot = (egrid.melt(id_vars=id_vars, var_name="seriesName", value_name="value")
             .pipe(extend_with_projections, aeo)
             .assign(**{config.NAME: lambda df: df[config.ACRONYM].map(config.EGRID_SUBREGION_NAMES)
                        .fillna(df[config.NAME])})
             .pivot_table(index=id_vars, columns="seriesName", values="calc_value")
             .reset_index())
    pivot.to_csv(config.GENERATION_CSV, index=False)
    config.RESULTS.mkdir(exist_ok=True)
    aeo_2025_table(aeo).to_csv(config.AEO_2025_GENERATION_CSV, index=False)
    excel_table(pivot).to_csv(EXCEL_CSV, index=False)


if __name__ == "__main__":
    main()
