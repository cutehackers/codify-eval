"""Build evaluated pilot code for Linux and verify its actual release executable."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import time
from prepare import ROOT

def check(run_id,version='v1'):
    run=json.loads((ROOT/'runtime'/run_id/'run.json').read_text())
    path=ROOT/'runtime'/'runtime-integration'/(run_id if version=='v1' else run_id+'-'+version)
    if path.exists():raise ValueError('Preserve original runtime evidence; choose versioned rerun explicitly')
    repo=path/'repo'
    shutil.copytree(ROOT/'runtime'/run_id/'repo',repo,ignore=shutil.ignore_patterns('.git','.dart_tool','build','.agents'))
    # Only host platform scaffolding is supplied, never reference application code.
    shutil.copytree(ROOT/'software_cases/W01/repo/linux',repo/'linux')
    container='runtime-'+run_id.lower()+'-'+version
    subprocess.run(['docker','run','-d','--name',container,'--network','none','-v',f'{repo}:/work/repo',
                    '-v',f'{ROOT}:/grader:ro','-v',f'{path}:/evidence',run['image_id'],'sleep','infinity'],check=True,capture_output=True)
    checks=[]
    def command(cmd,timeout):
        started=time.monotonic()
        result=subprocess.run(['docker','exec',container,'timeout',str(timeout)+'s','bash','-lc',cmd],capture_output=True,text=True,timeout=timeout+10)
        checks.append({'command':cmd,'exit_code':result.returncode,'output':result.stdout+result.stderr,'elapsed_seconds':time.monotonic()-started})
        return result.returncode==0
    try:
        built=command('cd /work/repo && flutter pub get --offline && flutter build linux --release --no-pub',600)
        if built:
            executable=next(f for f in repo.glob('build/linux/*/release/bundle/*') if f.is_file() and f.stat().st_mode & 0o111)
            binary='/work/repo/'+executable.relative_to(repo).as_posix()
            command('Xvfb :99 -screen 0 1280x900x24 >/evidence/xvfb.log 2>&1 & DISPLAY=:99 dbus-run-session -- python3 /grader/tools/pilot_gui.py '+run['case_id']+' '+binary+' /evidence/gui',90)
    finally:subprocess.run(['docker','rm','-f',container],capture_output=True)
    gui_path=path/'gui/gui-result.json'
    result={'run_id':run_id,'case_id':run['case_id'],'image_id':run['image_id'],'checks':checks,
            'pass':built and len(checks)==2 and checks[-1]['exit_code']==0,
            'gui':json.loads(gui_path.read_text()) if gui_path.exists() else None,
            'evidence_tier':'external_linux_release_executable',
            'limitation':'Scaffolding supplied in external copy; public program unchanged. E12 same-controller recreation remains widget evidence; no disk persistence claim.'}
    filename='runtime-integration.json' if version=='v1' else 'runtime-integration-'+version+'.json'
    (ROOT/'results'/run_id/filename).write_text(json.dumps(result,ensure_ascii=False,indent=2))
    return {k:v for k,v in result.items() if k not in {'checks','gui'}}

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('run');parser.add_argument('--version',default='v1');args=parser.parse_args();print(json.dumps(check(args.run,args.version),indent=2))
