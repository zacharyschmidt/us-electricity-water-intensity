"""Small helpers shared by the pipeline stages and the tools."""

import functools
import operator
import os
import time

import pandas as pd

from us_water_intensity import config


def clamp_year(year, years):
    """`year` if it lies within `years`, else the nearest end of the range."""
    return min(max(int(year), int(min(years))), int(max(years)))


def read_table(path):
    """CSV read with thousands separators and stray header whitespace removed."""
    return pd.read_csv(path, thousands=",").rename(columns=str.strip)


def read_generation(path=config.GENERATION_CSV):
    """Generation by subregion and year, with an integer year column."""
    return (read_table(path)
            .dropna(subset=[config.YEAR])
            .assign(**{config.YEAR: lambda df: df[config.YEAR].astype(int)}))


def read_water_factors():
    """Stage-3 factor table, one row per (year, subregion)."""
    return read_table(config.WATER_FACTORS_CSV)


def read_hydro_factors():
    """Stage-4 hydro factors by case, indexed by subregion."""
    return pd.read_csv(config.HYDRO_FACTORS_CSV).set_index("egrid_region")


def with_case_hydro(factors, hydro_factors, case):
    """Factor rows with Hydro replaced by the case's factor; subregions the case lacks keep Peer's."""
    case_hydro = factors["egrid region"].map(hydro_factors[config.CASE_COLUMNS[case]])
    return factors.assign(Hydro=case_hydro.where(case_hydro.notna(), factors["Hydro"]))


def sequential_sum(values):
    """Add left to right, so the total matches a per-row += loop; sum() and Series.sum() do not."""
    return functools.reduce(operator.add, list(values), 0)


def coerce_plant_id(df, column):
    """Integer `plant_id` from `column`; rows whose id does not parse are dropped."""
    return (df.assign(plant_id=lambda d: pd.to_numeric(d[column], errors="coerce"))
            .dropna(subset=["plant_id"])
            .astype({"plant_id": int}))


def get_with_retry(url, params=None, timeout=60, stream=False, attempts=7):
    """GET that waits and retries on 429 and 5xx, honouring Retry-After."""
    import requests

    for attempt in range(attempts):
        r = requests.get(url, params=params, timeout=timeout, stream=stream)
        if r.status_code != 429 and r.status_code < 500:
            r.raise_for_status()
            return r
        time.sleep(float(r.headers.get("Retry-After", 2 ** attempt)))
    r.raise_for_status()
    return r


def eia_api_key():
    """The EIA_API_KEY environment variable."""
    key = os.environ.get("EIA_API_KEY")
    if not key:
        raise SystemExit("Set EIA_API_KEY; keys are free at https://www.eia.gov/opendata/register.php")
    return key
