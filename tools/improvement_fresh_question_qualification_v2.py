"""Actor-free fixed-image controls for both independently authored question cases."""
import ast
import hashlib
import stat
import json
from pathlib import Path
import re
import shutil
import subprocess
import time

from improvement_fresh_pilot_qualification_v1 import classify, sha
from improvement_q04_artifacts_v1 import atomic_json
from improvement_q04_verifier_v5 import IMAGE, verify

ROOT = Path(__file__).resolve().parents[1]
CASES = ROOT / 'improvement_cases/fresh-question-cohort-v2'
STATIC = ROOT / 'results/improvement-v1/fresh-question-cohort-v2-static-review-v2.json'
HELPER = ROOT / 'results/improvement-v1/fresh-question-cohort-v2-qualification-helper-review-v2.json'
OUT = ROOT / 'results/improvement-v1/fresh-question-cohort-v2-qualification-v2'
RUNTIME = ROOT / 'runtime/protocol-probes/fresh-question-cohort-v2-qualification-v2'
COUNTS = {'Q05': (8, 3), 'Q06': (10, 3)}


def closure():
    pending, found = [Path(__file__).resolve()], set()
    while pending:
        path = pending.pop()
        if path in found:
            continue
        found.add(path)
        for node in ast.walk(ast.parse(path.read_bytes())):
            names = [a.name for a in node.names] if isinstance(node, ast.Import) else (
                [node.module] if isinstance(node, ast.ImportFrom) else [])
            for name in names:
                if name:
                    local = ROOT / 'tools' / (name.split('.')[0] + '.py')
                    if local.is_file():
                        pending.append(local)
    return found


def reviewed(path, required):
    value = json.loads(path.read_bytes())
    assert value['verdict'] == 'pass' and not value['issues']
    pins = {}
    for key in ('source_hashes', 'evidence_hashes', 'current_source_closure_sha256'):
        for name, digest in value.get(key, {}).items():
            assert name not in pins or pins[name] == digest, name
            pins[name] = digest
    for name, digest in pins.items():
        source = Path(name) if name.startswith('/') else ROOT / name
        assert sha(source) == digest, name
    assert all(str(p.relative_to(ROOT)) in pins or str(p) in pins for p in required)


def owned(case, relative):
    path = case / relative
    assert not Path(relative).is_absolute() and '..' not in Path(relative).parts
    assert path.is_file() and not path.is_symlink() and path.resolve().is_relative_to(case.resolve())
    return path


def failed_ids(receipt):
    names, failures = {}, []
    for line in receipt['checks'][1]['stdout'].splitlines():
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if not isinstance(event, dict):
            continue
        if event.get('type') == 'testStart':
            names[event['test']['id']] = event['test']['name']
        if event.get('type') == 'testDone' and event.get('result') == 'failure':
            failures.append(event['testID'])
    result = set()
    for identifier in failures:
        matches = re.findall(r'\b[PA]\d{2}\b', names[identifier])
        assert len(matches) == 1, names[identifier]
        result.add(matches[0])
    return sorted(result)


def fixture_tree():
    records = {}
    for path in [CASES, *sorted(CASES.rglob('*'))]:
        info = path.lstat()
        relative = str(path.relative_to(CASES))
        mode = stat.S_IMODE(info.st_mode)
        if stat.S_ISDIR(info.st_mode):
            records[relative] = {'kind': 'directory', 'mode': mode}
        else:
            assert stat.S_ISREG(info.st_mode), str(path)
            digest = hashlib.sha256()
            with path.open('rb') as stream:
                for chunk in iter(lambda: stream.read(262144), b''):
                    digest.update(chunk)
            records[relative] = {'kind': 'file', 'mode': mode, 'sha256': digest.hexdigest()}
    return records


def run():
    assert not OUT.exists() and not RUNTIME.exists()
    assert not subprocess.check_output(['docker', 'ps', '-a', '-q', '--filter', 'name=codify-'], text=True, timeout=30).strip()
    files = {p for p in CASES.rglob('*') if p.is_file()}
    assert files and not any(p.is_symlink() for p in CASES.rglob('*'))
    reviewed(STATIC, files)
    sources = closure()
    reviewed(HELPER, sources | {STATIC})
    assert json.loads((ROOT / 'runtime/image.json').read_bytes())['image_id'] == IMAGE
    pins = {str(p.relative_to(ROOT)): sha(p) for p in files | sources | {STATIC, HELPER, ROOT / 'runtime/image.json', ROOT / 'AGENTS.md'}}
    original = fixture_tree()
    OUT.mkdir(); RUNTIME.mkdir()
    summary = {'status': 'RUNNING', 'source_hashes': pins, 'image_id': IMAGE,
               'model_actors_allocated': 0, 'measured_model_difficulty': False,
               'superiority_proven': False, 'cases': {}, 'started_at': time.time()}
    atomic_json(OUT / 'summary-v1.json', summary, exclusive=True)
    try:
        for identifier, (public, private) in COUNTS.items():
            case = CASES / identifier
            meta = json.loads((case / 'metadata.json').read_bytes())
            assert meta['id'] == identifier and meta['public_test_count'] == public
            assert meta['private_test_count'] == private and meta['full_test_count'] == public + private
            assert set(meta['negative_controls']) == {'N01', 'N02', 'N03', 'N04'}
            rows = [('starting_public', None, False, public), ('reference', 'private/reference.dart', True, public + private)]
            rows += [(n, 'private/negative-controls/' + n + '.dart', True, public + private) for n in sorted(meta['negative_controls'])]
            summary['cases'][identifier] = {}
            for label, implementation, hidden, count in rows:
                assert fixture_tree() == original
                assert all(sha(ROOT / name) == digest for name, digest in pins.items())
                source = RUNTIME / identifier / label / 'source'
                shutil.copytree(case / 'repo', source)
                if implementation:
                    shutil.copyfile(owned(case, implementation), source / 'lib/implementation.dart')
                if hidden:
                    target = source / 'test/acceptance_test.dart'
                    assert not target.exists()
                    shutil.copyfile(owned(case, 'private/acceptance_test.dart'), target)
                receipt = verify(source, RUNTIME / identifier / label / 'verification', time.time() + 600, expected_tests=count)
                atomic_json(OUT / (identifier + '-' + label + '-receipt.json'), receipt, exclusive=True)
                result = classify(receipt, count)
                result['expected_test_count'] = count
                if result['valid_behavior_observation']:
                    result['failed_test_ids'] = failed_ids(receipt)
                if label == 'reference':
                    result['qualified'] = result['positive_checks_pass']
                elif label == 'starting_public':
                    result['qualified'] = result['valid_behavior_observation'] and result['behavior_pass'] is False
                else:
                    result['qualified'] = (result['genuine_assertion_negative'] and result['failed_test_ids'] == sorted(meta['negative_controls'][label]['expected_failing_tests']))
                summary['cases'][identifier][label] = result
                atomic_json(OUT / 'summary-v1.json', summary)
                print(json.dumps({'case': identifier, 'variant': label, **result}), flush=True)
                if not result['qualified'] or result['removed'] is not True:
                    summary['status'] = 'FAIL_BEHAVIOR_OR_INCOMPLETE_OBSERVATION'
                    return summary
        assert fixture_tree() == original
        assert all(sha(ROOT / name) == digest for name, digest in pins.items())
        summary['status'] = 'behavior_controls_pass'
        return summary
    except Exception as error:
        summary['status'] = 'FAIL_QUALIFICATION_ERROR'
        summary['error'] = type(error).__name__ + ': ' + str(error)
        raise
    finally:
        summary['all_allocated_containers_removed'] = all(v.get('removed') is True for case in summary['cases'].values() for v in case.values())
        summary['finished_at'] = time.time()
        atomic_json(OUT / 'summary-v1.json', summary)


if __name__ == '__main__':
    value = run()
    print(json.dumps({k: v for k, v in value.items() if k != 'source_hashes'}))
    raise SystemExit(0 if value['status'] == 'behavior_controls_pass' else 1)
