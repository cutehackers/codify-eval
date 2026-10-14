#!/usr/bin/env python3
"""Public-screen acceptance against separate Linux executable processes.

No generated Dart tests or application internals are imported. The declared legacy
JSON contract is read only to prove original values survive actual file writes.
"""
import argparse
import hashlib
import json
import pathlib
import sys
import shutil
import time
import traceback
sys.path.insert(0, '/grader/scripts')
from software_runtime import GuiDriver

LEGACY=[{'id':'legacy-active','title':'기존 진행','done':False},{'id':'legacy-done','title':'기존 완료','done':True}]

def run(executable,output,data):
    output=pathlib.Path(output);output.mkdir(parents=True,exist_ok=True)
    data=pathlib.Path(data)
    if data.exists():shutil.rmtree(data)
    assert not data.exists(), 'fresh data directory must not exist before app launch'
    driver=GuiDriver()
    result={'evidence_tier':'external_linux_release_executable','requirements':{},'processes':[]}
    def launch():
        phase=len(result['processes'])+1
        pid=driver.launch(executable,data,output/f'app-{phase}.log')
        result['processes'].append({'phase':phase,'pid':pid,'fresh_process':True,'data_dir':str(data)})
        driver.present('추가')
    def records():
        return json.loads((data/'todos.json').read_text())
    def legacy_preserved():
        by_id={r['id']:r for r in records()}
        for original in LEGACY:
            assert original['id'] in by_id,'legacy item was permanently deleted'
            for field in ['id','title','done']:
                assert by_id[original['id']][field]==original[field],f'legacy {field} changed'
    try:
        launch()
        driver.enter('할 일 제목','디렉토리 생성');driver.click('추가');driver.present('완료: 디렉토리 생성')
        assert data.is_dir() and (data/'todos.json').is_file(),'app did not create its data directory'
        result['requirements']['app_creates_missing_data_directory']=True
        driver.stop()
        shutil.rmtree(data);data.mkdir(parents=True)
        (data/'todos.json').write_text(json.dumps(LEGACY,ensure_ascii=False))
        launch()
        driver.present('완료: 기존 진행');driver.present('완료 취소: 기존 완료')
        result['requirements']['legacy_load_unarchived']=True
        driver.enter('할 일 제목','   ');driver.click('추가')
        assert len(records())==2,'blank title persisted'
        result['requirements']['blank_title_rejected']=True
        driver.enter('할 일 제목','  새 산책  ');driver.click('추가');driver.present('완료: 새 산책')
        new=[r for r in records() if r['id'] not in {'legacy-active','legacy-done'}]
        assert len(new)==1 and new[0]['title']=='새 산책' and new[0]['done'] is False
        driver.click('완료: 새 산책');driver.present('완료 취소: 새 산책')
        result['requirements']['create_trim_and_toggle']=True
        driver.click('진행 중');driver.present('완료: 기존 진행');driver.absent('완료 취소: 기존 완료');driver.absent('완료 취소: 새 산책')
        driver.click('완료');driver.present('완료 취소: 기존 완료');driver.present('완료 취소: 새 산책');driver.absent('완료: 기존 진행')
        driver.click('전체');driver.present('완료: 기존 진행');driver.present('완료 취소: 기존 완료')
        # Absence and a disabled public control are both valid. Test actual state,
        # not a particular UI layout or visibility choice.
        controls=[n for n in driver.nodes() if n.get_name()=='보관: 기존 진행' and 'Action' in n.get_interfaces()]
        if controls:
            action=controls[0].get_action_iface()
            for i in range(action.get_n_actions()):
                if action.get_action_name(i).lower() in ('tap','click','press','activate'):
                    action.do_action(i);time.sleep(0.2);break
            driver.events.append({'action':'attempt_active_archive','label':'보관: 기존 진행'})
        driver.present('완료: 기존 진행');driver.click('보관함');driver.absent('복원: 기존 진행');driver.click('전체')
        active=next(r for r in records() if r['id']=='legacy-active')
        assert active['done'] is False and active['title']=='기존 진행'
        result['requirements']['active_item_cannot_be_archived']=True
        result['requirements']['all_active_done_filters']=True
        # A directory at the declared file path makes atomic rename fail even as
        # root. File permissions alone would not establish a real save failure.
        file=data/'todos.json';before=file.read_bytes();backup=data/'todos.json.before-failure'
        file.rename(backup);file.mkdir()
        driver.enter('할 일 제목','복구 작업');driver.click('추가')
        driver.present('저장 실패');driver.present('다시 시도');driver.absent('완료: 복구 작업')
        driver.present('완료: 기존 진행');driver.present('완료 취소: 기존 완료')
        assert backup.read_bytes()==before,'failed save mutated existing persisted data'
        result['requirements']['save_failure_preserves_data_and_ui']=True
        file.rmdir();backup.rename(file)
        driver.click('다시 시도');driver.present('완료: 복구 작업');driver.absent('저장 실패')
        recovered=[r for r in records() if r['title']=='복구 작업']
        assert len(recovered)==1 and recovered[0]['done'] is False
        result['requirements']['original_save_retries_after_recovery']=True
        driver.click('보관: 기존 완료');driver.absent('완료 취소: 기존 완료')
        driver.click('보관함');driver.present('복원: 기존 완료');driver.absent('복원: 새 산책');driver.absent('복원: 기존 진행')
        legacy_preserved();result['requirements']['archive_only_completed_without_delete']=True
        file=data/'todos.json';result['file_before_restart']={'path':'todos.json','bytes':file.stat().st_size,'sha256':hashlib.sha256(file.read_bytes()).hexdigest()}
        driver.stop();launch()
        driver.absent('완료 취소: 기존 완료');driver.present('완료: 기존 진행');driver.present('완료 취소: 새 산책')
        driver.click('보관함');driver.present('복원: 기존 완료')
        result['requirements']['archive_survives_cold_restart']=True
        driver.click('복원: 기존 완료');driver.absent('복원: 기존 완료')
        driver.click('완료');driver.present('완료 취소: 기존 완료');driver.present('완료 취소: 새 산책')
        legacy_preserved();result['requirements']['restore_keeps_completion']=True
        driver.stop();launch()
        driver.present('완료 취소: 기존 완료');driver.click('보관함');driver.absent('복원: 기존 완료')
        driver.click('진행 중');driver.present('완료: 기존 진행');driver.absent('완료 취소: 새 산책')
        driver.click('완료');driver.present('완료 취소: 기존 완료');driver.present('완료 취소: 새 산책')
        legacy_preserved()
        assert len(records())==4,'restoration duplicated or dropped items'
        assert len({p['pid'] for p in result['processes']})==4,'not fresh processes'
        result['requirements']['restore_survives_second_cold_restart']=True
        result['requirements']['legacy_id_title_done_preserved']=True
        result['status']='pass'
    except Exception as error:
        result.update({'status':'fail','error':str(error),'traceback':traceback.format_exc(),'accessible_tree':driver.snapshot()})
    finally:
        driver.stop();result['events']=driver.events
        (output/'gui-result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('executable');p.add_argument('output');p.add_argument('data');a=p.parse_args()
    result=run(a.executable,a.output,a.data)
    print(json.dumps({'status':result['status'],'requirements':result['requirements'],'error':result.get('error')},ensure_ascii=False))
    raise SystemExit(0 if result['status']=='pass' else 1)
