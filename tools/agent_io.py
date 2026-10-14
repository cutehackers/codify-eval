"""Credential-free, logged task I/O for native model evaluation agents."""
from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]

def run_command(run_id: str, command: str, timeout: int = 180) -> dict:
    if not run_id or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_' for c in run_id):
        raise ValueError('Invalid run identifier')
    directory = ROOT / 'runtime' / run_id
    metadata = json.loads((directory / 'run.json').read_text())
    deadline=metadata.get('agent_started_at',time.time())+metadata.get('time_limit_seconds',1200)
    remaining=deadline-time.time()
    if remaining<=0: raise TimeoutError('Trajectory time budget exhausted; stop work and retain failure evidence')
    timeout=min(timeout,max(1,int(remaining)))
    container = metadata['container']
    start = time.monotonic()
    entry = {'time': dt.datetime.now(dt.timezone.utc).isoformat(), 'command': command,
             'container': container, 'timeout': timeout}
    try:
        completed = subprocess.run(['docker','exec',container,'timeout','--signal=TERM','--kill-after=5s',
            str(timeout)+'s','bash','-lc','cd /work/repo && ' + command],
            capture_output=True, text=True, timeout=timeout+10)
        entry.update(exit_code=completed.returncode, output=completed.stdout + completed.stderr)
    except subprocess.TimeoutExpired as error:
        entry.update(exit_code=124, output=str(error), timed_out=True)
    entry['elapsed_seconds'] = time.monotonic() - start
    with (directory / 'commands.jsonl').open('a') as stream:
        stream.write(json.dumps(entry,ensure_ascii=False)+'\n')
    return entry

if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--run',required=True)
    parser.add_argument('--cmd',required=True)
    parser.add_argument('--timeout',type=int,default=180)
    args=parser.parse_args()
    result=run_command(args.run,args.cmd,min(args.timeout,600))
    print(json.dumps(result,ensure_ascii=False))
    sys.exit(0)  # Execution status is explicit in result, including unsuccessful checks.
