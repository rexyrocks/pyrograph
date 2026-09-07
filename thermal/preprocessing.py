"""Preprocess daily weather data for thermal-stress calculations."""

from __future__ import annotations

import numpy as np
import pandas as pd

from pythermalcomfort.utilities import psy_ta_rh


REQUIRED_COLUMNS = [
    "date",
    "tmean",
    "rh_mean",
    "wind_speed_max",
    "solar_radiation_sum",
    "cloud_cover_mean",
]


def prepare_weather_data(df: pd.DataFrame) -> pd.DataFrame:
    """Prepare daily weather data for thermal calculations."""
    missing = sorted(set(REQUIRED_COLUMNS) - set(df.columns))
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    result = df.copy()

    result["date"] = pd.to_datetime(result["date"], errors="raise")

    # Daily mean air temperature → dry-bulb temperature.
    result["tdb"] = result["tmean"].astype(float)

    # Relative humidity (%).
    result["rh"] = result["rh_mean"].clip(0, 100).astype(float)

    # Available wind variable is daily maximum wind speed.
    result["wind_speed"] = (
        result["wind_speed_max"].clip(lower=0).astype(float)/3.6
    )

    # MJ/m²/day → W/m².
    result["solar_radiation_wm2"] = (
        result["solar_radiation_sum"].clip(lower=0).astype(float) / 0.0864
    )

    # Percentage → fraction.
    result["cloud_fraction"] = (
        result["cloud_cover_mean"].clip(0, 100).astype(float) / 100.0
    )

    # Psychrometric properties, including wet-bulb temperature.
    psychrometric = psy_ta_rh(
        tdb=result["tdb"].to_numpy(),
        rh=result["rh"].to_numpy(),
        p_atm=101325,
    )

    result["wet_bulb_temperature"] = np.asarray(
        psychrometric.wet_bulb_tmp,
        dtype=float,
    )

    return result