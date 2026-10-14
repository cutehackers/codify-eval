"""Bounded immutable template composition. Never evaluate actor code."""
import hashlib
import json
from pathlib import Path
import re
import shlex
import subprocess
import time
import improvement_composed_quote_collect_v6_base_probes as prior
import improvement_composed_quote_origin_v6 as origin
import improvement_composed_quote_collect_v6 as adapter
from prepare import ROOT
from transport import STRING


def run():
    before_origin, before_adapter = prior.origin, prior.adapter
    prior.origin, prior.adapter = origin, adapter
    try:
        result = prior.run()
    finally:
        prior.origin, prior.adapter = before_origin, before_adapter
    checks = result['checks']
    def check(name, passed):
        assert passed, name
        checks.append({'name': name, 'pass': True})
    run_id = 'control-probe-P02-pilot-v6-P02-A-2'
    folder = ROOT / 'results' / run_id
    names = [folder / n for n in ['native-tools.jsonl', 'grade.json', 'independent-terminal-diagnostic-v1.json']]
    names += [ROOT / 'runtime' / run_id / n for n in ['run.json', 'commands.jsonl']]
    sealed = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in names}
    events = [json.loads(line) for line in (folder / 'native-tools.jsonl').read_bytes().splitlines()]
    journal = [json.loads(line) for line in (ROOT / 'runtime' / run_id / 'commands.jsonl').read_bytes().splitlines()]
    for call in ['call_cbe9d8fe3d6c4da8afb5ab0db98d1b10', 'call_b2e63ae3453b42838f983be241185fba']:
        code = next(e['payload']['input'] for e in events if e.get('payload', {}).get('type') == 'custom_tool_call' and e['payload']['call_id'] == call)
        view = origin.project(code, str(ROOT), run_id)
        check('immutable_template_origin_' + call, view is not None)
        match = re.search('"cmd":(' + STRING + ')', view)
        argv = shlex.split(json.loads(match.group(1)))
        check('immutable_template_exact_journal_' + call, len(argv) == 6 and sum(j['command'] == argv[-1] for j in journal) == 1)
    metadata = json.loads((ROOT / 'runtime' / run_id / 'run.json').read_bytes())
    violations, polls = adapter.audit(events, metadata, str(ROOT))
    check('immutable_template_owned_poll', not violations and len(polls) == 1 and polls[0]['session_id'] == 3719 and polls[0]['origin_call_id'] == 'call_cbe9d8fe3d6c4da8afb5ab0db98d1b10')
    check('historical_sources_unchanged', sealed == {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in names})
    prefix = f'python3 {ROOT}/tools/agent_io.py --run {run_id} --cmd '
    quote = 'const q=s=>' + json.dumps("'") + '+s.replaceAll(' + json.dumps("'") + ',' + json.dumps("'\\''") + ')+' + json.dumps("'") + ';'
    synthetic = 'const piece=' + json.dumps("a'\\b한국어") + ';const command=' + chr(96) + 'printf ${ piece } ${piece}' + chr(96) + ';' + quote + 'text(await tools.exec_command({cmd:' + json.dumps(prefix) + '+q(command)}));'
    view = origin.project(synthetic, str(ROOT), run_id)
    check('authored_immutable_interpolation_recognized', view is not None)
    setup = 'const text=x=>{};const tools={exec_command:async x=>{console.log(JSON.stringify(x));return null;}};'
    def execute(code):
        receipt = subprocess.run([str(prior.NODE), '--input-type=module', '-e', setup + code], capture_output=True, text=True, timeout=10)
        receipt.check_returncode()
        return json.loads(receipt.stdout)
    check('authored_immutable_interpolation_node_equality', execute(synthetic) == execute(view))
    for expression in ['unknown', 'piece.length', 'piece[0]', 'process.env.HOME', 'piece+piece', 'piece="x"', 'q(piece)', '${piece}']:
        changed = synthetic.replace('${ piece }', '${' + expression + '}')
        check('closed_interpolation_' + expression, origin.project(changed, str(ROOT), run_id) is None)
    check('interpolation_forward_reference_rejected', origin.project(synthetic.replace('const piece=', 'const missing='), str(ROOT), run_id) is None)
    check('escaped_interpolation_remains_literal', origin.template_value('\\${piece}', {'piece': 'x'}) == '${piece}')
    value = 'x' * 524288
    check('common_newline_escapes_exact', origin.template_value(r'\n\r\t') == '\n\r\t')
    check('interpolation_1m_allowed', len(origin.template_value('${v}${v}', {'v': value})) == 1048576)
    started = time.monotonic()
    check('interpolation_expansion_bounded', origin.template_value('${v}' * 100000, {'v': value}) is None)
    check('interpolation_expansion_bounded_time', time.monotonic() - started < 1)
    names += [Path(__file__), Path(origin.__file__), Path(adapter.__file__)]
    result['source_hashes'].update({str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in names})
    result.update(count=len(checks), inherited_checks=98, inherited_closed_escape_check_replaced_by_unknown_unicode_escape=True, prospective_only=True, historical_mutation_allowed=False)
    return result


if __name__ == '__main__':
    result = run()
    path = ROOT / 'results/improvement-v1/composed-quote-collector-probes-v11.json'
    with path.open('x') as stream:
        json.dump(result, stream, indent=2)
    print(json.dumps({'status': result['status'], 'checks': result['count']}))
