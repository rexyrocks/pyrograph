"""Calculate WBGT and UTCI from prepared thermal inputs."""

from __future__ import annotations

import numpy as np
import pandas as pd

from pythermalcomfort.models import utci, wbgt


def calculate_thermal_indices(df: pd.DataFrame) -> pd.DataFrame:
    """Calculate daily WBGT and UTCI."""
    result = df.copy()

    utci_result = utci(
        tdb=result["tdb"].to_numpy(),
        tr=result["tmrt"].to_numpy(),
        v=result["wind_speed"].to_numpy(),
        rh=result["rh"].to_numpy(),
        round_output=False,
        limit_inputs=False,
    )

    result["utci"] = np.asarray(utci_result.utci, dtype=float)

    wbgt_result = wbgt(
        twb=result["wet_bulb_temperature"].to_numpy(),
        tg=result["globe_temperature"].to_numpy(),
        tdb=result["tdb"].to_numpy(),
        with_solar_load=True,
        round_output=False,
    )

    result["wbgt"] = np.asarray(wbgt_result.wbgt, dtype=float)

    return result