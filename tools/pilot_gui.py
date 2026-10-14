"""External user-flow probe for evaluated E05/E12 release executables."""
import argparse
import json
from pathlib import Path
import sys
import traceback
sys.path.insert(0,'/grader/scripts')
from software_runtime import GuiDriver

def enter_only_field(driver,value):
    fields=[n for n in driver.nodes() if 'EditableText' in n.get_interfaces()]
    if len(fields)!=1: raise AssertionError(f'Expected sole visible text field, found {len(fields)}')
    node=fields[0];action=node.get_action_iface()
    for index in range(action.get_n_actions()):
        if action.get_action_name(index).lower()=='focus':
            action.do_action(index)
            import time;time.sleep(.2)
            break
    if not node.get_editable_text_iface().set_text_contents(value):raise AssertionError('Text entry refused')
    driver.events.append({'action':'enter_only_visible_field','value':value})
    import time;time.sleep(.2)

def click_only_button(driver):
    buttons=[n for n in driver.nodes() if n.get_role_name()=='push button' and 'Action' in n.get_interfaces()]
    if len(buttons)!=1:raise AssertionError(f'Expected sole visible detail action button, found {len(buttons)}')
    action=buttons[0].get_action_iface()
    names=[action.get_action_name(i).lower() for i in range(action.get_n_actions())]
    index=next(i for i,name in enumerate(names) if name in ('tap','click','press','activate'))
    if not action.do_action(index):raise AssertionError('Button action refused')
    driver.events.append({'action':'click_only_visible_button','accessible_name':buttons[0].get_name()})
    import time;time.sleep(.2)

def run(case,executable,output):
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    driver=GuiDriver();result={'case':case,'evidence_tier':'external_linux_release_executable','requirements':{}}
    try:
        driver.launch(executable,output/'data',output/'app.log')
        if case=='E05':
            driver.present('산책');driver.click('산책');driver.present('저녁 산책')
            click_only_button(driver);driver.present('독서');driver.click('독서');driver.present('책 읽기')
            click_only_button(driver);driver.present('산책')
            result['requirements']['list_detail_return']=True
        elif case=='E12':
            driver.present('기록 없음');enter_only_field(driver,'   ');driver.click('저장');driver.present('기록 없음')
            enter_only_field(driver,'  산책 기록  ');driver.click('저장');driver.present('산책 기록');driver.absent('기록 없음')
            driver.click('산책 기록');enter_only_field(driver,'독서 기록');driver.click('저장')
            driver.present('독서 기록');driver.absent('산책 기록')
            result['requirements']['create_validate_edit']=True
        else:raise ValueError(case)
        result['status']='pass'
    except Exception as error:
        result.update(status='fail',error=str(error),traceback=traceback.format_exc(),accessible_tree=driver.snapshot())
    finally:
        driver.stop();result['events']=driver.events
        (output/'gui-result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
    return result

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('case');parser.add_argument('executable');parser.add_argument('output');args=parser.parse_args()
    result=run(args.case,args.executable,args.output);print(json.dumps(result,ensure_ascii=False));raise SystemExit(0 if result['status']=='pass' else 1)
