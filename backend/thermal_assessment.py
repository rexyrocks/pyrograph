"""Daily thermal estimates; not peak exposure or a calibrated health score."""
import os
import tempfile
from pathlib import Path
from typing import Literal

os.environ.setdefault('NUMBA_CACHE_DIR', str(Path(tempfile.gettempdir()) / 'pyrograph-numba'))

import numpy as np
import pandas as pd
from pydantic import BaseModel
from pythermalcomfort.models import utci, wbgt
from thermal.preprocessing import prepare_weather_data
from thermal.radiation import add_radiation_features

class ThermalAssessment(BaseModel):
    method_version: Literal['daily-approximation-v1'] = 'daily-approximation-v1'
    status: Literal['estimated', 'partial', 'unavailable']
    wbgt_c: float | None
    utci_c: float | None
    units: Literal['degC'] = 'degC'
    assumptions: list[str]
    unavailable_reason: str | None = None

ASSUMPTIONS = [
    'Daily mean temperature/humidity and maximum wind; not peak-hour exposure.',
    'Globe and radiant temperatures are empirical estimates, not measurements.',
    'Wet-bulb estimate uses standard atmospheric pressure.',
    'Not validated against local thermal measurements; not a mortality score.',
]

def assess_thermal(record) -> ThermalAssessment:
    values = record.model_dump()
    frame = add_radiation_features(prepare_weather_data(pd.DataFrame([values])))
    row = frame.iloc[0]
    u = float(utci(tdb=row.tdb, tr=row.tmrt, v=row.wind_speed, rh=row.rh,
                   limit_inputs=True, round_output=False).utci)
    w = float(wbgt(twb=row.wet_bulb_temperature, tg=row.globe_temperature,
                   tdb=row.tdb, with_solar_load=True, round_output=False).wbgt)
    valid_u, valid_w = bool(np.isfinite(u)), bool(np.isfinite(w))
    return ThermalAssessment(
        status='estimated' if valid_u and valid_w else 'partial' if valid_u or valid_w else 'unavailable',
        wbgt_c=round(w, 2) if valid_w else None,
        utci_c=round(u, 2) if valid_u else None,
        assumptions=ASSUMPTIONS,
        unavailable_reason=None if valid_u and valid_w else 'Outside thermal calculation applicability limits.',
    )
