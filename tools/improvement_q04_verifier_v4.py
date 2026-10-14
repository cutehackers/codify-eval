"""Draft pristine-image public Flutter verifier for fixed Q04 orchestration.

This is not the external private acceptance grader or a native broker route.
"""
import json
from pathlib import Path
import shutil
import subprocess
import time
import uuid

from prepare import ROOT
from improvement_boundary_v1 import inspect_repo
from improvement_software_artifacts_v3 import atomic_json, tree

IMAGE = 'sha256:9751b1bbd374a218e0fe7dcd362e478f2b8bb5453dbed90658da8dd0b2be3638'
PATH = '/sdks/flutter/bin:/sdks/flutter/bin/cache/dart-sdk/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin'
COMMANDS = (['/sdks/flutter/bin/flutter', 'pub', 'get', '--offline'],
            ['/sdks/flutter/bin/flutter', 'test', '--no-pub', '--machine'],
            ['/sdks/flutter/bin/flutter', 'analyze', '--no-pub'])


class DuplicateKey(ValueError):
    pass


def unique_object(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise DuplicateKey('duplicate JSON key: ' + key)
        value[key] = item
    return value


def machine(log, expected_tests):
    starts, ends, done, errors = {}, {}, [], []
    protocol_errors, test_errors = [], []
    error_ids = set()

    def invalid(message):
        protocol_errors.append(message)
        errors.append(message)
    for line in log.splitlines():
        try:
            event = json.loads(line, object_pairs_hook=unique_object)
        except DuplicateKey as error:
            invalid(str(error))
            continue
        except ValueError:
            continue
        if not isinstance(event, dict):
            continue
        kind = event.get('type')
        if kind in ('testStart', 'testDone', 'error', 'done') and done:
            invalid('test lifecycle event after terminal done')
        if kind == 'testStart':
            test = event.get('test')
            if (not isinstance(test, dict) or type(test.get('id')) is not int
                    or not isinstance(test.get('name'), str)):
                invalid('invalid test start schema')
                continue
            if test['id'] in starts:
                invalid('duplicate test start')
            starts[test['id']] = test['name']
        elif kind == 'testDone':
            if (type(event.get('testID')) is not int
                    or not isinstance(event.get('result'), str)
                    or type(event.get('skipped')) is not bool):
                invalid('invalid test end schema')
                continue
            if event['testID'] not in starts:
                invalid('test end precedes start')
            if event['testID'] in ends:
                invalid('duplicate test end')
            ends[event['testID']] = event
        elif kind == 'error':
            if type(event.get('testID')) is not int or event['testID'] not in starts:
                invalid('test error has unknown or invalid test ID')
            else:
                error_ids.add(event['testID'])
                if event['testID'] in ends:
                    invalid('test error after test end')
            test_errors.append(str(event.get('error')))
            errors.append(str(event.get('error')))
        elif kind == 'done':
            if not starts or set(starts) != set(ends):
                invalid('terminal done before all test ends')
            if type(event.get('success')) is not bool:
                invalid('invalid terminal schema')
            done.append(event)
    tests = {identifier: name for identifier, name in starts.items() if not name.startswith('loading ')}
    valid_results = all(event.get('result') in {'success', 'failure', 'error'}
                        and event.get('skipped') is False for event in ends.values())
    semantic_success = all(event.get('result') == 'success' for event in ends.values()) and not test_errors
    if any(identifier not in ends or ends[identifier].get('result') == 'success' for identifier in error_ids):
        invalid('test error contradicts test end')
    if len(done) == 1 and done[0].get('success') is not semantic_success:
        invalid('terminal success contradicts test outcomes')
    well_formed = (len(done) == 1 and not protocol_errors and bool(starts)
                   and set(starts) == set(ends) and len(tests) == expected_tests and valid_results)
    success = (well_formed and len(done) == 1 and done[0].get('success') is True and not errors
               and set(starts) == set(ends) and len(tests) == expected_tests
               and all(event.get('result') == 'success' and event.get('skipped') is False for event in ends.values()))
    return {'pass': success, 'well_formed': well_formed, 'protocol_errors': protocol_errors,
            'test_errors': test_errors, 'tests': tests, 'test_count': len(tests), 'errors': errors,
            'terminal_events': done, 'missing_end_ids': sorted(set(starts) - set(ends))}


def verify(source, folder, deadline, expected_tests=1):
    source, folder = Path(source).resolve(), Path(folder).resolve()
    assert source.is_relative_to(ROOT) and folder.is_relative_to(ROOT / 'runtime')
    assert not folder.exists() and not folder.is_relative_to(source)
    assert type(expected_tests) is int and expected_tests > 0
    inspect_repo(source)
    before = tree(source)
    folder.mkdir(parents=True)
    destination = folder / 'repo'
    owner = uuid.uuid4().hex
    name = 'codify-q04-verifier-' + owner
    receipt = folder / 'receipt.json'
    value = {'status': 'creation_intent', 'name': name, 'owner': owner, 'image_id': IMAGE,
             'checks': [], 'first_error': None, 'cleanup_errors': [], 'source_before': before,
             'source_path': str(source), 'expected_nonloading_tests': expected_tests,
             'private_acceptance_grading': False, 'superiority_proven': False, 'pass': False}
    atomic_json(receipt, value, exclusive=True)
    identity = None

    def run(args, seconds=30, bounded=True):
        timeout = min(seconds, deadline - time.time()) if bounded else seconds
        assert timeout > 0, 'Shared trajectory deadline exhausted'
        return subprocess.run(args, capture_output=True, text=True, timeout=timeout)

    def inspect(cleanup=False):
        result = run(['docker', 'inspect', name], bounded=not cleanup)
        result.check_returncode()
        info = json.loads(result.stdout)[0]
        assert info['Image'] == IMAGE and info['HostConfig']['NetworkMode'] == 'none'
        assert info['Config']['Labels'].get('codify.q04.verifier.owner') == owner
        assert len(info['Mounts']) == 1
        mount = info['Mounts'][0]
        assert mount['Type'] == 'bind' and mount['Source'] == str(destination) and mount['Destination'] == '/work/repo' and mount['RW'] is True
        assert identity is None or info['Id'] == identity
        return info

    try:
        assert shutil.disk_usage(ROOT).free >= 3 * 1024**3
        shutil.copytree(source, destination, ignore=shutil.ignore_patterns('.git', '.dart_tool', 'build', '__pycache__'))
        create = ['docker', 'create', '--name', name, '--network', 'none', '--label', 'codify.q04.verifier.owner=' + owner,
                  '-v', str(destination) + ':/work/repo', '-w', '/work/repo', IMAGE, 'sleep', 'infinity']
        value['create_argv'] = create
        run(create, 60).check_returncode()
        info = inspect()
        identity = info['Id']
        value.update(container_id=identity, identity=info)
        atomic_json(receipt, value)
        run(['docker', 'start', name]).check_returncode()
        for command in COMMANDS:
            seconds = min(180, int(deadline - time.time()) - 6)
            assert seconds > 0, 'Insufficient remaining verifier budget'
            argv = ['docker', 'exec', '-w', '/work/repo', '-e', 'PATH=' + PATH,
                    '-e', 'HOME=/root', '-e', 'CI=true', '-e', 'FLUTTER_SUPPRESS_ANALYTICS=true',
                    name, '/usr/bin/timeout', '--kill-after=5s', str(seconds) + 's', *command]
            started = time.monotonic()
            result = run(argv, seconds + 6)
            value['checks'].append({'argv': argv, 'inner_argv': command, 'exit_code': result.returncode,
                                    'stdout': result.stdout, 'stderr': result.stderr,
                                    'elapsed_seconds': time.monotonic() - started})
            atomic_json(receipt, value)
        value['machine'] = machine(value['checks'][1]['stdout'], expected_tests)
        assert time.time() <= deadline, 'Shared trajectory deadline exhausted before verification completed'
        value['pass'] = all(check['exit_code'] == 0 for check in value['checks']) and value['machine']['pass']
        value['status'] = 'completed'
    except Exception as error:
        value.update(status='evaluation_error', first_error={'type': type(error).__name__, 'message': str(error)})
        value['pass'] = False
        if isinstance(error, subprocess.TimeoutExpired):
            value['partial_stdout'] = error.stdout.decode(errors='replace') if isinstance(error.stdout, bytes) else error.stdout
            value['partial_stderr'] = error.stderr.decode(errors='replace') if isinstance(error.stderr, bytes) else error.stderr
    finally:
        try:
            found = run(['docker', 'inspect', name], bounded=False)
            if found.returncode == 0:
                info = inspect(cleanup=True)
                if info['State']['Running']:
                    try:
                        run(['docker', 'stop', '-t', '2', name], 10, bounded=False).check_returncode()
                    except Exception:
                        run(['docker', 'kill', name], 10, bounded=False).check_returncode()
                assert not inspect(cleanup=True)['State']['Running']
                from improvement_software_broker_v7 import preserve_tmp
                preserve_tmp(folder, name, 'verifier')
                run(['docker', 'rm', name], bounded=False).check_returncode()
                gone = run(['docker', 'inspect', name], bounded=False)
                assert gone.returncode != 0 and 'No such object' in gone.stderr
            else:
                assert 'No such object' in found.stderr
            value['removed'] = True
        except Exception as error:
            value['cleanup_errors'].append({'type': type(error).__name__, 'message': str(error)})
            value['status'] = 'evaluation_error'
            value['pass'] = False
        try:
            assert tree(source) == before, 'Original integrated source changed'
            value['source_unchanged'] = True
        except Exception as error:
            value.setdefault('artifact_errors', []).append({'type': type(error).__name__, 'message': str(error)})
            value['status'] = 'evaluation_error'
            value['pass'] = False
        atomic_json(receipt, value)
    return value
