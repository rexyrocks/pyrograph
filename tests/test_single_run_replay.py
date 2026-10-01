"""Guard the issue-time feature boundary in the archived-run replay."""
import unittest
from datetime import date, timedelta

from scripts.evaluate_single_runs import EXPECTED_UNITS, aggregate_complete_days, record_for_target
from scripts.probe_forecast_archive import HOURLY_FIELDS


class SingleRunReplayTests(unittest.TestCase):
    def test_partial_initial_day_cannot_be_used_as_a_complete_lag(self):
        run_day = date(2025, 5, 1)
        times = [f'2025-05-01T{hour:02d}:00' for hour in range(6, 24)]
        for offset in range(1, 7):
            day = run_day + timedelta(days=offset)
            times.extend(f'{day.isoformat()}T{hour:02d}:00' for hour in range(24))
        hourly = {'time': times}
        for name in HOURLY_FIELDS:
            hourly[name] = [30.0] * len(times)
        daily, coverage = aggregate_complete_days({'timezone': 'Asia/Kolkata',
                                                   'hourly_units': EXPECTED_UNITS, 'hourly': hourly})
        self.assertFalse(coverage['2025-05-01']['complete'])
        self.assertIsNone(record_for_target(run_day + timedelta(days=3), daily))
        record = record_for_target(run_day + timedelta(days=4), daily)
        self.assertIsNotNone(record)
        self.assertEqual(record.tmax_lag3, daily[run_day + timedelta(days=1)]['tmax'])

    def test_missing_hour_in_target_rejects_scoring(self):
        day = date(2025, 5, 5)
        hourly = {'time': [f'{day.isoformat()}T{hour:02d}:00' for hour in range(23)]}
        for name in HOURLY_FIELDS:
            hourly[name] = [30.0] * 23
        daily, coverage = aggregate_complete_days({'timezone': 'Asia/Kolkata',
                                                   'hourly_units': EXPECTED_UNITS, 'hourly': hourly})
        self.assertFalse(coverage[day.isoformat()]['complete'])
        self.assertNotIn(day, daily)

    def test_unit_change_is_rejected_before_scoring(self):
        with self.assertRaisesRegex(ValueError, 'units'):
            aggregate_complete_days({'timezone': 'Asia/Kolkata',
                                     'hourly_units': {**EXPECTED_UNITS, 'wind_speed_10m': 'm/s'},
                                     'hourly': {}})


if __name__ == '__main__':
    unittest.main()
