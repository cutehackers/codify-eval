"""Prospective optional native dispatch intents and literal role bootstrap.

Coordinator owns namespace and actual allocation. Public broker may prepare a
worker but never launches it. Full actual native origin/routes/current inventory,
original-clock observer continuity and source fences must be audited separately.
"""
import hashlib
from datetime import datetime, timezone
from pathlib import Path
import re
import shlex
import time

import improvement_optional_registry_v4 as registry
import improvement_optional_checkout_artifacts_v2 as checkout
import improvement_optional_broker_v6 as original_broker
from improvement_software_artifacts_v3 import atomic_json, encoded

ROOT = Path(__file__).resolve().parents[1]
BROKER_SCRIPT = ROOT/'tools/improvement_optional_broker_v9.py'
require = registry.require


def command(run, job, capability, op, data=None):
    require(isinstance(run,str) and re.fullmatch('[A-Za-z0-9_-]+',run),'Exact run namespace required')
    require(job in ('root','worker1','worker2') and isinstance(capability,str)
            and re.fullmatch('[0-9a-f]{48}',capability),'Exact role capability required')
    return shlex.join(['python3',str(BROKER_SCRIPT),'--run',run,'--job',job,'--cap',capability,
                       '--op',op,'--data',encoded({} if data is None else data).decode()])


def bootstrap(run, job, capability):
    first=command(run,job,capability,'read')
    import json
    wrapper='text(await tools.exec_command('+json.dumps({'cmd':first,'yield_time_ms':10000,'max_output_tokens':20000})+'));'
    common=("Use only the registered public broker through functions.exec. Your FIRST tool call must be exactly:\n"
            +wrapper+"\nRead its entire returned public task. Every later functions.exec call must contain only one literal "
            "text(await tools.exec_command({...})); with a cmd that invokes this same broker script/run/job/cap. "
            "Change only --op and --data. Exec data is an object with command and optional seconds. Commands run inside "
            "your isolated checkout with working directory /work/repo. To observe an exec_command that returns session_id, "
            "use only text(await tools.write_stdin({session_id:THE_RETURNED_ID,chars:\"\",yield_time_ms:10000,max_output_tokens:20000})); "
            "until that original session finishes. Never restart a command merely because it is still running. "
            "Do not use any other host tools, filesystem reads, network or native routes. "
            "Check the broker status, actual inner exit_code and output_complete before proceeding. "
            "Do not edit protected files, test files, source modes or files outside your public editable scope. "
            "All actors use gpt-6.1-sol at medium. You have one approved turn and the original shared deadline.\n")
    if job!='root':
        return common+("Allowed broker operations: read, exec, seal. Work only on your assigned goal and leased files. "
            "Never spawn or message another agent. Finish by seal with optional findings, then return a concise final "
            "describing the actual change and verification. After seal no further broker execution is allowed.\n")
    return common+("Allowed broker operations: read, exec, worker, view, decide, integrate, verify. "
        "worker data has goal, scope and optional mode(write or review). Scope must be disjoint editable files. "
        "A read-only review uses mode review and empty scope. At most two cumulative worker slots, no retries/replacements. "
        "After a successful worker result, spawn EXACTLY that job with collaboration.spawn_agent task_name set to job, "
        "message set to its returned native_bootstrap, fork_turns none, model gpt-6.1-sol, reasoning_effort medium. "
        "Do not change the bootstrap message. Only inspect your own subtree via collaboration.list_agents with "
        "path_prefix equal to your exact agent path, or use collaboration.wait_agent with timeout_ms10000..60000. "
        "Do not send follow-ups or spawn unregistered workers. Root must not edit leased files while a worker owns them. "
        "Wait for each worker's genuine final and completion. view data:{slot:job} returns its original view, "
        "then decide data:{slot:job,view:returned_view,decision:accept_or_reject,reason:reason}. "
        "Every reserved worker needs an explicit decision. integrate with empty data installs accepted contributions "
        "and releases leases once. After integration no new workers or views/decisions are allowed. "
        "Root may then correct editable implementation and verify with empty data runs fixed public tests and analyzer. "
        "Preserve all unsuccessful results and return actual outcome. Cleanup is coordinator-owned.\n")


def create(folder, root_path, coordinator_id, root_capability):
    folder=Path(folder).resolve()
    require(folder.parent==ROOT/'runtime' and re.fullmatch('/root/[A-Za-z0-9_]+',root_path),
            'Owned namespace and immediate product root required')
    require(isinstance(coordinator_id,str) and coordinator_id,'Original coordinator identity required')
    state=registry.read(folder/'registry'); config=state['configuration']
    require(not state['workers'] and 'integration_release' not in state,'Dispatch setup before workers/integration required')
    directory=folder/'native-dispatch';directory.mkdir();(directory/'intents').mkdir()
    value={'run_id':config['run_id'],'configuration_sha256':registry.sha(config),
           'root_path':root_path,'coordinator_id':coordinator_id,'model':'gpt-6.1-sol','effort':'medium',
           'broker_script':str(BROKER_SCRIPT),'native_qualified':False,'comparison_eligible':False}
    atomic_json(directory/'configuration.json',value,exclusive=True)
    return prepare(folder,'root',root_capability)


def prepare(folder,job,capability):
    folder=Path(folder).resolve();directory=folder/'native-dispatch'
    original_broker.runtime.role(folder,job,capability)
    config_raw=original_broker.original(directory/'configuration.json')
    configuration_pin=checkout.file_pin(directory/'configuration.json')
    require(configuration_pin['sha256']==hashlib.sha256(config_raw).hexdigest() and configuration_pin['bytes']==len(config_raw),'Dispatch configuration changed while reading')
    value=registry.strict.decoded(config_raw)
    require(isinstance(value,dict) and set(value)=={'run_id','configuration_sha256','root_path','coordinator_id','model','effort','broker_script','native_qualified','comparison_eligible'}
            and re.fullmatch('/root/[A-Za-z0-9_]+',value['root_path'])
            and isinstance(value['coordinator_id'],str) and value['coordinator_id']
            and value['native_qualified'] is False and value['comparison_eligible'] is False,'Exact original dispatch schema required')
    with registry.locked(folder/'registry'):
        state=registry.read(folder/'registry')
    config=state['configuration']; now=time.time()
    require(value['run_id']==config['run_id'] and value['configuration_sha256']==registry.sha(config)
            and value['model']=='gpt-6.1-sol' and value['effort']=='medium'
            and value['broker_script']==str(BROKER_SCRIPT) and config['started_at']<=now<config['deadline'],
            'Original dispatch configuration/clock changed')
    require(job=='root' or job in state['workers'],'Unreserved native member')
    require('integration_release' not in state,'No native dispatch after final integration')
    if job!='root':
        root_row=registry.strict.decoded(original_broker.original(directory/'intents/root.json'))
        require(set(root_row)=={'intent','native_bootstrap','bootstrap_sha256','provision','dispatch_configuration_pin','native_qualified','comparison_eligible'}
                and encoded(root_row['dispatch_configuration_pin'])==encoded(configuration_pin)
                and root_row['intent']['agent_path']==value['root_path']
                and root_row['intent']['configuration_sha256']==registry.sha(config)
                and root_row['bootstrap_sha256']==hashlib.sha256(root_row['native_bootstrap'].encode()).hexdigest(),
                'Original root dispatch/configuration changed')
    control=registry.strict.decoded(original_broker.original(folder/'broker'/job/'control.json'))
    require(isinstance(control,dict) and set(control)=={'job','run_id','configuration_sha256','capability_sha256','request_sha256','request_bytes','native_qualified','comparison_eligible'}
            and control['run_id']==config['run_id'] and type(control['request_bytes']) is int
            and 0<=control['request_bytes']<=2*1024*1024
            and isinstance(control['request_sha256'],str) and re.fullmatch('[0-9a-f]{64}',control['request_sha256'])
            and control['native_qualified'] is False and control['comparison_eligible'] is False,'Exact original broker control required')
    public_raw=original_broker.original(folder/job/'input/request.txt')
    require(len(public_raw)==control['request_bytes'] and hashlib.sha256(public_raw).hexdigest()==control['request_sha256'],'Original public task changed')
    require(control['job']==job and control['configuration_sha256']==registry.sha(config)
            and control['capability_sha256']==hashlib.sha256(capability.encode()).hexdigest(),
            'Prepared role transport required')
    public_raw.decode('utf-8')  # Prepared task must be returnable by the literal first read.
    message=bootstrap(folder.name,job,capability)
    path=value['root_path'] if job=='root' else value['root_path']+'/'+job
    worker=None if job=='root' else state['workers'][job]
    intent={'job':job,'agent_path':path,'at':datetime.fromtimestamp(now,timezone.utc).isoformat(),
        'public_request_sha256':control['request_sha256'],'configuration_sha256':registry.sha(config),
        'reservation_worker_sha256':None if worker is None else registry.sha({key:worker[key] for key in ('slot','goal','scope','mode','snapshot','snapshot_sha256')})}
    row={'intent':intent,'native_bootstrap':message,'bootstrap_sha256':hashlib.sha256(message.encode()).hexdigest(),
         'provision':{'job':job,'agent_path':path,'intent_sha256':registry.sha(intent),
                     'public_request_sha256':control['request_sha256'],'status':'prepared'},
         'dispatch_configuration_pin':configuration_pin,'native_qualified':False,'comparison_eligible':False}
    atomic_json(directory/'intents'/(job+'.json'),row,exclusive=True)
    return row
