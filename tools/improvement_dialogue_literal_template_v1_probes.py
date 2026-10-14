"""Prospective direct cmd literals, ownership and actual reply barrier probes."""
import copy
import hashlib
import json
import shlex
from pathlib import Path
from prepare import ROOT
from improvement_dialogue_literal_template_v1 import project
from improvement_dialogue_native_v10 import READ, SCRIPT, exact_read, wrapper, reply_barrier
from improvement_dialogue_native_v10_probes import fixture, encode


def main():
    rows = []
    prefix = f'python3 {ROOT}/tools/{SCRIPT} --run probe --cmd '
    cmd = prefix + shlex.quote(READ)
    def literal(command):
        return 'text(await tools.exec_command({"cmd":`' + command + '`,"max_output_tokens":2000}));'
    def check(name, got, expected):
        assert got == expected, (name, got, expected)
        rows.append({'name': name, 'pass': True})
    check('direct read literal accepted', wrapper(literal(cmd), str(ROOT), 'probe'), True)
    check('direct read literal exact read accepted', exact_read(literal(cmd), str(ROOT), 'probe'), True)
    code = literal(prefix + "'python3 - <<\"PY\"\nprint(\"safe\")\nPY'")
    check('multiline inner command accepted', wrapper(code, str(ROOT), 'probe'), True)
    check('CRLF cooked normalization', project(literal(cmd+'\r\nx')) == project(literal(cmd+'\nx')), True)
    invalid = {
        'template substitution': literal(cmd+'${run}'),
        'backslash escape': literal(cmd+'\\n'),
        'nested backtick': literal(cmd+'`x'),
        'extra statement': literal(cmd)+'text(1);',
        'alias call': literal(cmd).replace('tools.exec_command', 'runner'),
        'duplicate cmd': literal(cmd).replace(',"max_output_tokens":2000', ',"cmd":`other`'),
        'dynamic option': literal(cmd).replace('2000', 'limit'),
        'unsupported option': literal(cmd).replace('max_output_tokens', 'workdir'),
        'wrong broker': literal(cmd.replace(SCRIPT, 'agent_io.py')),
        'wrong run': literal(cmd.replace('--run probe', '--run other')),
        'second shell argv': literal(cmd+' extra'),
        'broken nested apostrophes': literal(prefix+"'python3 -c 'print(1)' '"),
    }
    for name, bad in invalid.items():
        check(name+' rejected', wrapper(bad, str(ROOT), 'probe'), False)
    check('not a read rejected by exact read', exact_read(literal(prefix+"'echo x'"), str(ROOT), 'probe'), False)
    actor, parent, metadata, staged, records = copy.deepcopy(fixture())
    actor[6]['payload']['input'] = literal(cmd)
    got = reply_barrier(encode(actor), encode(parent), metadata, staged, records, str(ROOT))
    check('actual same-session barrier accepts direct read', bool(got), True)
    value = {'status': 'pass', 'count': len(rows), 'probes': rows,
             'scope': 'Pure prospective parser/barrier only; no actual actor qualification or old-run regrade',
             'source_hashes': {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                               for p in [Path(__file__).resolve(), ROOT/'tools/improvement_dialogue_literal_template_v1.py', ROOT/'tools/improvement_dialogue_native_v10.py']}}
    path = ROOT/'results/improvement-v1/dialogue-literal-template-v1-probes.json'
    with path.open('x') as stream:
        json.dump(value, stream, indent=2)
    print(json.dumps({'status': value['status'], 'count': value['count']}))


if __name__ == '__main__':
    main()
