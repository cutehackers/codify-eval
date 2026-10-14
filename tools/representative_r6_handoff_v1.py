"""Reuse the frozen R6 software grader in a separate one-worker namespace."""
import argparse
import json
from pathlib import Path
import representative_eval_v1 as runner

BASE = Path(__file__).resolve().parents[1]
FREEZE = BASE / 'results/improvement-v1/representative-R6-handoff-freeze-v1.json'


def row_folder(case, condition):
    if (case, condition) != ('R6', 'C24'):
        raise ValueError('Only the separately frozen R6/C24 handoff observation is allowed')
    return BASE / 'runtime/representative-R6-handoff-v1/R6-C24-1'


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('operation', choices=['prepare', 'grade'])
    parser.add_argument('--preparation-sha256')
    args = parser.parse_args()
    frozen = json.loads(FREEZE.read_text())
    assert runner.digest(__file__) == frozen['wrapper_sha256']
    assert runner.digest(runner.MANIFEST) == frozen['original_manifest_sha256']
    assert runner.digest(BASE / frozen['prompt_path']) == frozen['prompt_sha256']
    runner.row_folder = row_folder
    result = (runner.prepare('R6', 'C24') if args.operation == 'prepare'
              else runner.grade('R6', 'C24', args.preparation_sha256))
    print(json.dumps(result, sort_keys=True))
