"""Narrow saved-shell-quote presentation audit over unchanged native evidence."""
from contextlib import contextmanager
import argparse
import copy
import hashlib
import json
from pathlib import Path
import re
import collect_schema_v366 as prior
import transport
from prepare import ROOT

MANIFEST = ROOT / 'results/frozen-saved-quote-transport-v3.6.11.json'
VERSION = 'saved-quote-transport-v3.6.11'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def inline_view(code, root, run_id):
    match = prior.TEMPLATE.fullmatch(code.strip())
    if not match:
        return None
    variable, body, rest = match.groups()
    if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', variable):
        return None
    quoted = re.fullmatch(
        r'const\s+([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(' + transport.STRING + r')\s*\+\s*' +
        re.escape(variable) + r"\.replace\(\s*/'/g\s*,\s*(" + transport.STRING +
        r')\s*\)\s*\+\s*(' + transport.STRING + r')\s*;\s*(.*)', rest, re.S)
    if not quoted or quoted.group(1) == variable:
        return None
    q, left, escape, right, call = quoted.groups()
    try:
        if [json.loads(x) for x in (left, escape, right)] != ["'", "'\\''", "'"]:
            return None
    except ValueError:
        return None
    expr = r'text\s*\(\s*await\s+tools\.exec_command\s*\(\s*\{\s*"?cmd"?\s*:\s*'
    ending = transport.OPTIONS + r'\s*\}\s*\)\s*\)\s*;?\s*'
    invocation = re.fullmatch(expr + '(' + transport.STRING + r')\s*\+\s*' +
                              re.escape(q) + ending, call, re.S)
    if not invocation:
        return None
    try:
        prefix = json.loads(invocation.group(1))
    except ValueError:
        return None
    expected = f'python3 {root}/tools/agent_io.py --run {run_id} --cmd '
    if prefix != expected:
        return None
    # This substitutes an expression, never executes or decodes the template.
    view = (f'const {variable} = `{body}`;\ntext(await tools.exec_command({{cmd:' +
            json.dumps(prefix + "'") + ' + ' + variable + '.replace(/\'/g, ' +
            escape + ') + ' + right + '}));')
    return view if prior.wrapper_origin(view, root, run_id) else None


def wrapper_origin(code, root, run_id):
    return inline_view(code, root, run_id) is not None or prior.wrapper_origin(code, root, run_id)


@contextmanager
def patched_origin():
    with prior.patched_origin():
        original = transport.wrapper_origin
        transport.wrapper_origin = wrapper_origin
        try:
            yield
        finally:
            transport.wrapper_origin = original


def audit(events, metadata, root):
    with patched_origin():
        return prior.audit_transport(events, metadata, root)


def baseline(events, metadata, root):
    with prior.patched_origin():
        return prior.audit_transport(events, metadata, root)


def verify_registration():
    prior.verify_registration()
    frozen = json.loads(MANIFEST.read_text())
    if frozen.get('version') != VERSION or frozen.get('status') != 'frozen' or frozen.get('actor_reexecution_allowed') is not False:
        raise ValueError('Saved-quote audit is not preregistered')
    required = {'tools/saved_quote_transport_v3611.py', 'tools/saved_quote_transport_v3611_probes.py',
                'results/saved-quote-transport-qualification-v3.6.11.json',
                'results/saved-quote-transport-independent-review-v3.6.11.json'}
    if not required <= set(frozen['source_sha256']):
        raise ValueError('Missing required audit pins')
    for name, expected in frozen['source_sha256'].items():
        if sha(ROOT / name) != expected:
            raise ValueError('Saved-quote audit source changed: ' + name)
    return frozen


def compare(run_id):
    native = ROOT / 'results' / run_id / 'native-tools.jsonl'
    events = [json.loads(line) for line in native.read_text().splitlines()]
    metadata = json.loads((ROOT / 'runtime' / run_id / 'run.json').read_text())
    before = baseline(events, metadata, str(ROOT))
    after = audit(events, metadata, str(ROOT))
    origins = [e['payload']['call_id'] for e in events
               if e.get('payload', {}).get('type') in {'function_call', 'custom_tool_call'}
               and inline_view(str(e['payload'].get('arguments', e['payload'].get('input', ''))), str(ROOT), run_id)]
    return {'run_id': run_id, 'native_sha256': sha(native), 'before': before,
            'after': after, 'saved_quote_origin_call_ids': origins}


def apply(run_id):
    frozen = verify_registration()
    value = compare(run_id)
    metadata_path = ROOT / 'runtime' / run_id / 'run.json'
    manifest_path = ROOT / 'results' / run_id / 'manifest.json'
    proof_path = ROOT / 'results' / run_id / 'saved-quote-audit-v3.6.11.json'
    if proof_path.exists():
        raise ValueError('Audit already applied; preserve attempt')
    metadata = json.loads(metadata_path.read_text())
    manifest = json.loads(manifest_path.read_text())
    if value['before'] != value['after']:
        preservation = frozen.get('prior_preservation', {}).get(run_id)
        required_originals = {f'runtime/{run_id}/run.json'} | {
            f'results/{run_id}/{name}' for name in ('manifest.json','native-tools.jsonl','turns.json')}
        if not preservation or set(preservation) != required_originals:
            raise ValueError('Changed audit requires frozen original preservation')
        if (ROOT/'results'/run_id/'grade.json').exists():
            raise ValueError('Existing grade requires independent adjudication, not automatic change')
        original_native = sha(ROOT/'results'/run_id/'native-tools.jsonl')
        original_turns = sha(ROOT/'results'/run_id/'turns.json')
        for name, item in preservation.items():
            if ((ROOT/name).resolve() == (ROOT/item['copy']).resolve()
                    or sha(ROOT/name) != item['sha256'] or sha(ROOT/item['copy']) != item['sha256']):
                raise ValueError('Original evidence not preserved: ' + name)
        if (metadata.get('tool_audit'), metadata.get('tool_poll_evidence')) != tuple(value['before']):
            raise ValueError('Recorded audit differs from baseline; no unregistered changes')
        if (manifest.get('tool_audit'), manifest.get('tool_poll_evidence')) != tuple(value['before']):
            raise ValueError('Manifest audit differs from baseline')
        for target, data in [(metadata_path, metadata), (manifest_path, manifest)]:
            original = copy.deepcopy(data)
            data['tool_audit'], data['tool_poll_evidence'] = value['after']
            assert {k:v for k,v in data.items() if k not in {'tool_audit','tool_poll_evidence'}} == {
                k:v for k,v in original.items() if k not in {'tool_audit','tool_poll_evidence'}}
            target.write_text(json.dumps(data, ensure_ascii=False, indent=2))
        if (sha(ROOT/'results'/run_id/'native-tools.jsonl') != original_native
                or sha(ROOT/'results'/run_id/'turns.json') != original_turns):
            raise ValueError('Native or task snapshot changed during audit update')
    value.update(version=VERSION, registration_sha256=sha(MANIFEST),
                 actor_reexecuted=False, native_unmodified=True, turns_sha256=sha(ROOT/'results'/run_id/'turns.json'))
    with proof_path.open('x') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
    return value


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('run'); args = p.parse_args()
    print(json.dumps(apply(args.run), ensure_ascii=False, indent=2))
