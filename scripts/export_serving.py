"""Export a newly evaluated immutable serving bundle; never deploys it."""
import argparse
from pathlib import Path
from evaluate_retrospective import run_evaluation

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data', type=Path, required=True)
    parser.add_argument('--bundle-dir', type=Path, required=True)
    parser.add_argument('--report-dir', type=Path, default=Path('work/export-evaluation'))
    args = parser.parse_args()
    run_evaluation(args.data, args.report_dir, args.bundle_dir)
    print(f'Exported {args.bundle_dir}; deployment is unchanged')
