"""Approximate globe temperature and mean radiant temperature."""

from __future__ import annotations

import numpy as np
import pandas as pd

from pythermalcomfort.utilities import mean_radiant_tmp


def estimate_globe_temperature(df: pd.DataFrame) -> pd.Series:
    """Estimate globe temperature from daily weather variables.

    The dataset does not contain measured globe temperature or Tmrt.
    We therefore use a transparent empirical approximation driven by
    solar radiation, cloud cover, air temperature and wind speed.

    This is a prototype approximation, not a replacement for a
    measured globe thermometer or a full radiative-transfer model.
    """
    solar = df["solar_radiation_wm2"].to_numpy(dtype=float)
    cloud = df["cloud_fraction"].to_numpy(dtype=float)
    tdb = df["tdb"].to_numpy(dtype=float)
    wind = df["wind_speed"].to_numpy(dtype=float)

    # Reduce effective solar loading under cloudier conditions.
    effective_solar = solar * (1.0 - 0.5 * cloud)

    # Approximate solar-induced globe heating.
    solar_warming = (
        0.05 * effective_solar / (1.0 + 0.2 * wind)
    )

    # Keep the approximation physically reasonable for this prototype.
    solar_warming = np.clip(solar_warming, 0.0, 25.0)

    return pd.Series(
        tdb + solar_warming,
        index=df.index,
        name="globe_temperature",
    )


def add_radiation_features(df: pd.DataFrame) -> pd.DataFrame:
    """Add estimated globe temperature and mean radiant temperature."""
    result = df.copy()

    result["globe_temperature"] = estimate_globe_temperature(result)

    result["tmrt"] = mean_radiant_tmp(
        tg=result["globe_temperature"].to_numpy(),
        tdb=result["tdb"].to_numpy(),
        v=result["wind_speed"].to_numpy(),
        d=0.15,
        emissivity=0.95,
        standard="ISO",
    )

    result["tmrt"] = np.asarray(result["tmrt"], dtype=float)

    return result