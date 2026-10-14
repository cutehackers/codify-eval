"""Actual owned Docker raw diagnostics plus injected byte/deadline guards."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tarfile
import time
import types
from unittest.mock import patch
import uuid

import improvement_software_broker_v4 as broker

ROOT=broker.ROOT
FOLDER=ROOT/'runtime/protocol-probes/software-broker-v4-archive-probe'
OUT=ROOT/'results/improvement-v1/software-broker-v4-archive-probe.json'


def main():
    assert not FOLDER.exists() and not OUT.exists()
    FOLDER.mkdir()
    name='codify-archive-v4-'+uuid.uuid4().hex
    report={'actual_model_actors':0,'full_broker_qualified':False,'superiority_proven':False,'checks':[],'first_error':None,'cleanup_error':None}
    def owned():
        info=json.loads(broker.runtime.docker(['inspect',name]).stdout)[0]
        assert info['Image']==broker.runtime.IMAGE and info['Config']['Labels'].get('codify.archive.probe')==name and info['HostConfig']['NetworkMode']=='none'
        return info
    try:
        created=broker.runtime.docker(['create','--name',name,'--network','none','--label','codify.archive.probe='+name,broker.runtime.IMAGE,'sleep','infinity'])
        info=owned();assert info['Id']==created.stdout.strip()
        (FOLDER/'identity-before.json').write_text(json.dumps(info,indent=2))
        broker.runtime.docker(['start',name])
        broker.runtime.docker(['exec',name,'/bin/sh','-c','printf "probe-data\\n" > /tmp/needed.txt'])
        broker.runtime.docker(['stop','-t','2',name]);assert not owned()['State']['Running']
        broker.archive_tmp(FOLDER,name,'actual')
        archive=next(FOLDER.glob('actual-tmp-*.tar'))
        with tarfile.open(archive) as tar:
            members=[m for m in tar.getmembers() if m.name.endswith('/needed.txt')]
            assert len(members)==1 and tar.extractfile(members[0]).read()==b'probe-data\n'
        report['checks'].append({'name':'actual_stopped_container_diagnostics_preserved','pass':True,'archive':str(archive.relative_to(ROOT)),'sha256':hashlib.sha256(archive.read_bytes()).hexdigest()})
        original=subprocess.Popen
        def bytes_process(*args,**kwargs):
            return original([sys.executable,'-c','import sys,time;sys.stdout.buffer.write(b"a"*16);sys.stdout.flush();time.sleep(.1);sys.stdout.buffer.write(b"b"*64);sys.stdout.flush();time.sleep(10)'],**kwargs)
        with patch.object(broker.subprocess,'Popen',side_effect=bytes_process):
            try:broker.archive_tmp(FOLDER,'injected-child','size',limit=32)
            except ValueError as error:
                assert 'byte budget' in str(error)
            else:raise AssertionError('Byte overflow accepted')
        partial=list(FOLDER.glob('size-tmp-*.tar'));assert len(partial)==1 and partial[0].stat().st_size<=32
        report['checks'].append({'name':'injected_byte_overflow_rejected_partial_retained','pass':True,'partial_bytes':partial[0].stat().st_size})
        begin=time.monotonic()
        clock=types.SimpleNamespace(monotonic=iter([begin,begin+31]).__next__,time=lambda:time.time())
        def sleeping_process(*args,**kwargs):return original([sys.executable,'-c','import time;time.sleep(10)'],**kwargs)
        with patch.object(broker.subprocess,'Popen',side_effect=sleeping_process),patch.object(broker,'time',clock):
            try:broker.archive_tmp(FOLDER,'injected-child','deadline')
            except TimeoutError as error:assert 'deadline' in str(error)
            else:raise AssertionError('Expired archive deadline accepted')
        report['checks'].append({'name':'injected_elapsed_deadline_rejected_child_terminated','pass':True})
    except Exception as error:
        report['first_error']=type(error).__name__+': '+str(error)
    finally:
        try:
            found=broker.runtime.docker(['inspect',name],check=False)
            if found.returncode==0:
                info=owned()
                if info['State']['Running']:broker.runtime.docker(['stop','-t','2',name])
                assert not owned()['State']['Running'];broker.runtime.docker(['rm',name])
            absent=broker.runtime.docker(['inspect',name],check=False)
            assert absent.returncode!=0 and 'No such object:' in absent.stderr
            report['owned_container_removed']=True
        except Exception as error:report['cleanup_error']=type(error).__name__+': '+str(error)
        paths=[Path(__file__),ROOT/'tools/improvement_software_broker_v4.py']
        report['source_hashes']={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
        report['status']='pass' if report['first_error'] is None and report['cleanup_error'] is None and len(report['checks'])==3 else 'fail'
        with OUT.open('x') as f:json.dump(report,f,indent=2)
    print(json.dumps(report))
    if report['status']!='pass':raise SystemExit(1)

if __name__=='__main__':main()
