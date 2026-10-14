"""Supplemental H01 public-contract checks on actual Linux release GUI."""
import argparse
import json
from pathlib import Path
import sys
import traceback
sys.path.insert(0, '/grader/scripts')
from software_runtime import GuiDriver


def boundary(driver, label, enabled):
    driver.find(label)
    actual = driver.can_click(label)
    driver.events.append({'action': 'assert_control_enabled', 'label': label,
                          'expected': enabled, 'actual': actual})
    if actual != enabled:
        raise AssertionError(f'{label}: enabled={actual}, expected {enabled}')


def quantity(driver, value, maximum):
    driver.present(f'수량 {value}')
    shown = [n['name'] for n in driver.snapshot() if n['name'].startswith('수량 ')]
    if shown != [f'수량 {value}']:
        raise AssertionError(f'Unexpected quantity labels: {shown}')
    boundary(driver, '감소', value > 0)
    boundary(driver, '증가', value < maximum)


def run(executable, output, maximum):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    driver = GuiDriver()
    result = {'maximum': maximum, 'evidence_tier': 'external_linux_release_executable',
              'requirements': {}}
    try:
        driver.launch(executable, output/'data', output/'app.log')
        quantity(driver, 0, maximum)
        for value in range(1, maximum + 1):
            driver.click('증가')
            quantity(driver, value, maximum)
        for value in range(maximum - 1, -1, -1):
            driver.click('감소')
            quantity(driver, value, maximum)
        result.update(status='pass', requirements={'inclusive_range_and_disabled_boundaries': True})
    except Exception as error:
        result.update(status='fail', error=str(error), traceback=traceback.format_exc(),
                      accessible_tree=driver.snapshot())
    finally:
        driver.stop()
        result['events'] = driver.events
        (output/'gui-result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2))
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('executable')
    parser.add_argument('output')
    parser.add_argument('--maximum', type=int, required=True)
    args = parser.parse_args()
    result = run(args.executable, args.output, args.maximum)
    print(json.dumps(result, ensure_ascii=False))
    raise SystemExit(0 if result['status'] == 'pass' else 1)
