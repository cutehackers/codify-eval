#!/usr/bin/env python3
"""Grade public UI, exact editable values and cold restart without node cardinality."""
import argparse, hashlib, json, pathlib, sys, time, traceback
sys.path.insert(0,'/grader/scripts')
from software_runtime import GuiDriver

LIMIT='Distinct opening labels do not independently identify same-title duplicate records; universal record cardinality is not claimed.'

def run(executable, output, data):
    output=pathlib.Path(output);output.mkdir(parents=True,exist_ok=True)
    data=pathlib.Path(data);driver=GuiDriver();result={'version':'2-review-repair','evidence_tier':'external_linux_release_executable','requirements':{},'processes':[],'initial_data_directory_absent':not data.exists(),'opening_label_checks':[],'exact_field_checks':[],'limits':[LIMIT]}
    first_body='  저녁 공원\n30분 걸음  '
    updated_body='  저녁 공원\n45분 걸음  '
    def launch():
        index=len(result['processes'])+1
        pid=driver.launch(executable,data,output/f'app-{index}.log')
        result['processes'].append({'phase':index,'pid':pid,'fresh_process':True})
        driver.present('새 메모')
    def ensure_list(label):
        deadline=time.monotonic()+driver.timeout
        while time.monotonic()<deadline:
            names={n['name'] for n in driver.snapshot()}
            if label in names:return
            if '목록으로' in names and driver.can_click('목록으로'):
                try:driver.click('목록으로')
                except AssertionError as e:driver.events.append({'action':'navigation_transition_retry','label':label,'error':str(e)})
                driver.present(label);return
            time.sleep(0.1)
        driver.present(label)
    def openings(*titles):
        expected={'열기: '+title for title in titles};deadline=time.monotonic()+driver.timeout;raw=[]
        while time.monotonic()<deadline:
            raw=[n['name'] for n in driver.snapshot() if n['name'].startswith('열기: ')]
            if set(raw)==expected:
                result['opening_label_checks'].append({'expected_labels':sorted(expected),'observed_labels':sorted(set(raw)),'raw_nodes_diagnostic_only':len(raw)})
                return
            time.sleep(0.1)
        raise AssertionError(f'opening label set mismatch: expected={sorted(expected)!r}, actual={sorted(set(raw))!r}')
    def read_field(label):
        node=driver.find(label,interface='EditableText')
        assert 'Text' in node.get_interfaces(),f'editable field has no readable Text interface: {label}'
        from gi.repository import Atspi
        return Atspi.Text.get_text(node,0,-1)
    def exact_fields(title,body):
        expected={'제목':title,'내용':body};deadline=time.monotonic()+driver.timeout;actual={};error=None
        while time.monotonic()<deadline:
            try:
                actual={label:read_field(label) for label in expected}
                if actual==expected:
                    result['exact_field_checks'].append({'expected':expected,'actual':actual})
                    driver.events.append({'action':'assert_exact_edit_fields','values':actual});return
            except Exception as e:error=str(e)
            time.sleep(0.1)
        raise AssertionError(f'editable field exact mismatch: expected={expected!r}, actual={actual!r}, read_error={error!r}')
    def create(title,body):
        driver.click('새 메모');driver.enter('제목',title);driver.enter('내용',body);driver.click('저장');ensure_list('열기: '+title.strip())
    def detail(title,body=None):
        driver.click('열기: '+title);driver.present('편집');driver.present('삭제');driver.present(title,exact=False)
        if body is not None:driver.present(body,exact=False)
    def remove(title,remaining_label):
        detail(title);driver.click('삭제');driver.click('삭제 확인');ensure_list(remaining_label)
    try:
        assert result['initial_data_directory_absent'],'grader must start with a nonexistent data directory'
        launch();driver.present('메모가 없습니다');openings();result['requirements']['initial_empty']=True
        driver.click('새 메모');driver.enter('제목','   ');driver.enter('내용','잘못된 항목');driver.click('저장');driver.present('제목을 입력하세요');driver.click('취소');ensure_list('메모가 없습니다');openings();result['requirements']['blank_validation']=True
        driver.click('새 메모');driver.enter('제목','취소할 기록');driver.enter('내용','이 내용은 저장하면 안 됨');driver.click('취소');ensure_list('메모가 없습니다');driver.absent('열기: 취소할 기록');openings();result['requirements']['valid_create_cancel']=True
        create('  산책 기록  ',first_body);create('독서 기록','책 12쪽');create('내용 없는 기록','');openings('산책 기록','독서 기록','내용 없는 기록')
        detail('내용 없는 기록');driver.click('편집');exact_fields('내용 없는 기록','');driver.click('취소');ensure_list('열기: 내용 없는 기록');result['requirements']['empty_body_allowed']=True
        remove('내용 없는 기록','열기: 산책 기록');driver.absent('열기: 내용 없는 기록');openings('산책 기록','독서 기록');result['requirements']['create_trim_multiline']=True
        assert data.is_dir(),'application did not create its data directory';result['requirements']['app_creates_data_directory']=True
        detail('산책 기록',first_body);driver.click('편집');exact_fields('산책 기록',first_body);result['requirements']['detail_read']=True
        driver.enter('제목','취소된 제목');driver.enter('내용','취소된 본문');driver.click('취소');ensure_list('열기: 산책 기록');driver.absent('열기: 취소된 제목');detail('산책 기록',first_body);driver.click('편집');exact_fields('산책 기록',first_body);result['requirements']['valid_edit_cancel']=True
        driver.enter('제목','긴 산책');driver.enter('내용',updated_body);driver.click('저장');ensure_list('열기: 긴 산책');driver.absent('열기: 산책 기록');openings('긴 산책','독서 기록');result['requirements']['edit_without_duplicate']=True
        detail('독서 기록','책 12쪽');driver.click('삭제');driver.present('메모 삭제');driver.click('취소');driver.present('책 12쪽',exact=False);driver.click('삭제');driver.click('삭제 확인');ensure_list('열기: 긴 산책');driver.absent('열기: 독서 기록');openings('긴 산책');result['requirements']['delete_confirmation_cancel']=True
        files=[p for p in data.rglob('*') if p.is_file() and p.stat().st_size>0]
        assert files,'no real local file saved under EVAL_DATA_DIR'
        result['local_files_before_restart']=[{'path':str(p.relative_to(data)),'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in files];result['requirements']['real_local_file']=True
        driver.stop();launch();driver.present('열기: 긴 산책');driver.absent('열기: 독서 기록');driver.absent('열기: 산책 기록');openings('긴 산책')
        detail('긴 산책',updated_body);driver.click('편집');exact_fields('긴 산책',updated_body);driver.click('취소');ensure_list('열기: 긴 산책');result['requirements']['cold_restart_restore']=True
        remove('긴 산책','메모가 없습니다');openings();driver.stop();launch();driver.present('메모가 없습니다');openings();result['requirements']['delete_survives_restart']=True
        result['status']='pass'
    except Exception as e:
        result.update({'status':'fail','error':str(e),'traceback':traceback.format_exc(),'accessible_tree':driver.snapshot()})
    finally:
        driver.stop();result['events']=driver.events
        (output/'gui-result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('executable');p.add_argument('output');p.add_argument('data');a=p.parse_args();r=run(a.executable,a.output,a.data);print(json.dumps({'status':r['status'],'requirements':r['requirements'],'error':r.get('error')},ensure_ascii=False));raise SystemExit(0 if r['status']=='pass' else 1)
