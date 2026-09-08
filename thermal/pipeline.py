"""End-to-end thermal stress calculation pipeline."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from .indices import calculate_thermal_indices
from .preprocessing import prepare_weather_data
from .radiation import add_radiation_features


def run_thermal_pipeline(
    input_path: str | Path,
    output_path: str | Path | None = None,
) -> pd.DataFrame:
    """Run the complete weather → WBGT/UTCI pipeline."""
    df = pd.read_csv(input_path)

    df = prepare_weather_data(df)
    df = add_radiation_features(df)
    df = calculate_thermal_indices(df)

    if output_path is not None:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(output_path, index=False)

    return df