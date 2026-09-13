"""Fixed-reference retrospective evaluation, separate from the serving artifacts.

2015-2018 climate reference; 2019-2021 fitting; 2022 selection; 2023-2024 test.
Realised weather is used. This does not establish advance forecast skill.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from heatwave_pipeline import (
    FEATURES, calendar_day_index, engineer_features, evaluate_models,
    train_models, validate_and_load,
)


def prepare_evaluation(raw: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    reference = raw.loc[raw.date.dt.year.between(2015, 2018)]
    if set(reference.date.dt.year.unique()) != {2015, 2016, 2017, 2018}:
        raise ValueError('Complete 2015-2018 reference years are required')
    result = raw.copy()
    reference_days = calendar_day_index(reference.date)
    normals, p95s, p98s = [], [], []
    for day in calendar_day_index(result.date):
        distance = np.abs(reference_days - day)
        values = reference.loc[np.minimum(distance, 366 - distance) <= 7, 'tmax']
        normals.append(float(values.mean()))
        p95s.append(float(np.percentile(values, 95)))
        p98s.append(float(np.percentile(values, 98)))
    # Legacy column name retained only for compatibility with engineer_features.
    # Values here use the fixed pre-training reference, not LOYO.
    result['climatology_normal_loyo'] = normals
    result['heatwave'] = (result.tmax >= p95s).astype('int8')
    result['severe'] = (result.tmax >= p98s).astype('int8')
    result = engineer_features(result).dropna(subset=FEATURES)
    years = result.date.dt.year
    partitions = (
        result.loc[years.between(2019, 2021)].copy(),
        result.loc[years == 2022].copy(),
        result.loc[years.between(2023, 2024)].copy(),
    )
    if any(frame.empty for frame in partitions):
        raise ValueError('Training, selection and test periods must all be present')
    return partitions


def select_model(selection_metrics: dict) -> str:
    return max(selection_metrics, key=lambda name: (
        selection_metrics[name]['csi'], selection_metrics[name]['f1'], name,
    ))


def run_evaluation(data: Path, output_dir: Path) -> dict:
    train, selection, test = prepare_evaluation(validate_and_load(data))
    models, class_weight = train_models(train)
    selection_metrics, _ = evaluate_models(models, selection)
    winner = select_model(selection_metrics)
    # Winner is locked before the test is evaluated. No post-test model refit.
    test_metrics, _ = evaluate_models({winner: models[winner]}, test)
    report = {
        'evaluation_version': 'fixed-reference-retrospective-v2',
        'status': 'preliminary_retrospective_not_forecast_skill',
        'serving_model_replaced': False,
        'climate_reference': '2015-2018, fixed before fitting and evaluation',
        'split': {'train': '2019-2021', 'selection': '2022', 'test': '2023-2024'},
        'rows': {'train': len(train), 'selection': len(selection), 'test': len(test)},
        'selected_model': winner,
        'selection_metric': 'CSI; F1 then name as deterministic tie-breakers',
        'selection_metrics': selection_metrics,
        'test_metrics': test_metrics,
        'xgboost_scale_pos_weight': class_weight,
        'limitations': [
            'Uses realised daily weather, not archived issue-time forecasts.',
            'No probability calibration or mortality outcomes.',
            'Single location and short climate reference; not official IMD normals.',
            'The test period has been inspected in earlier experiments; fresh external validation is still needed.',
            'Historical temperature lags assume a completed prior day; deployment availability requires separate evaluation.',
        ],
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / 'evaluation_metrics.json').write_text(json.dumps(report, indent=2) + '\n')
    return report
