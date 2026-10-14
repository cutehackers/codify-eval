"""Prospective stopped-product grading. No cleanup or comparison authority.

Only the exact stopped export and one frozen private test may enter the grading
copy. A frozen external coordinator must authenticate snapshot and delivered
owner assignment before this module can execute any SDK command.
"""
import copy
from pathlib import Path
import shutil
import time

import improvement_baseline_case_catalog_v3 as catalog
import improvement_baseline_comparison_inputs_v2 as inputs
import improvement_baseline_question_coordinator_v9 as coordinator
import improvement_baseline_sdk_verifier_v1 as sdk
import improvement_baseline_result_classification_v1 as classifier

runtime=coordinator.runtime
require=runtime.require
encoded=runtime.encoded
ROOT=inputs.ROOT


def selected_contract(case_id, selection):
    contracts=catalog.qualified_receipt_contracts(case_id)
    if selection is None:
        if case_id in ('B01','B02'):
            return contracts['private_reference_candidates'][0],True
        return contracts['public'],False
    require(type(selection) is dict and case_id in ('B03','B04'),
            'Only question tasks can select an assigned private reference')
    matches=[row for row in contracts['private_reference_candidates']
             if encoded(row)==encoded(selection)]
    require(len(matches)==1,'Exact unique qualified assigned-reference receipt required')
    return copy.deepcopy(matches[0]),True


def _grade(row,stopped_snapshot_reference,selection,*,
          coordinator_verifier,verifier_contract):
    inputs.row_valid(row)
    row=runtime.strict.decoded(encoded(row))
    contract,private=selected_contract(row['case_id'],selection)
    folder=ROOT/'runtime'/row['run_id']
    snapshot_path=Path(stopped_snapshot_reference['path'])
    require(snapshot_path.parent==folder/'events','Original owned stopped event required')
    snapshot=runtime.strict.decoded(runtime.question_reference_bytes(stopped_snapshot_reference))
    require(snapshot.get('op')=='stopped_snapshot' and snapshot.get('job')=='root'
            and snapshot.get('scope_error') is None,'Successful scoped root stopped snapshot required')
    source=Path(snapshot['export'])
    require(source.is_absolute() and source.resolve(strict=True)==source
            and not source.is_symlink() and source.parent==folder/'snapshots',
            'Exact owned stopped export required')
    state=runtime.load(folder)
    require(state['jobs']['root']['status']=='stopped'
            and state['jobs']['root']['container_id']==snapshot['container_id'],
            'Same original root container must be stopped before grading')
    deadline=state['deadline']
    require(time.time()<deadline,'Original grading deadline exhausted')
    exported=runtime.source.inventory(source,deadline)
    require(encoded(exported['source_entities'])==encoded(snapshot['inventory']['source_entities']),
            'Original stopped export differs from recorded protected source')
    coordinator.authenticate(coordinator_verifier,verifier_contract,'grade_original_stopped_product',
        {'row':row,'stopped_snapshot_reference':stopped_snapshot_reference,
         'qualified_receipt_contract':contract,'private_grading_requested':private,
         'delivered_owner_selection':selection,'original_deadline':deadline})
    require(encoded(runtime.load(folder))==encoded(state), 'Runtime changed during grading authentication')
    runtime.question_verify_reference(stopped_snapshot_reference)
    require(encoded(runtime.source.inventory(source,deadline))==encoded(exported),
            'Stopped source changed during grading authentication')
    directory=folder/'grading';directory.mkdir()
    intent={'row':row,'stopped_snapshot_reference':stopped_snapshot_reference,
            'qualified_receipt_contract':contract,'private_grading_requested':private,
            'original_deadline':deadline,'model_pilot_admitted':False}
    runtime.atomic_json(directory/'intent.json',intent,exclusive=True)
    destination=directory/'source'
    runtime.source.export(source,exported,destination,deadline)
    expected=copy.deepcopy(exported['source_entities'])
    if private:
        catalog.qualified_public_contract(row['case_id'])
        acceptance=inputs.case_directory(row)/'private/test/acceptance_test.dart'
        pin=runtime.question_file_entity(acceptance)
        name='test/pilot_acceptance_test.dart'
        require(name not in expected,'Private acceptance destination collision')
        target=destination/name
        shutil.copy2(acceptance,target)
        require(encoded(runtime.question_file_entity(acceptance))==encoded(pin)
                and encoded(runtime.question_file_entity(target))==encoded(pin),
                'Frozen private test changed during copying')
        expected[name]={key:value for key,value in pin.items() if key!='bytes'}
    require(encoded(runtime.source.inventory(destination,deadline)['source_entities'])==encoded(expected),
            'Grading source must be exact stopped product plus frozen private test only')
    receipt=sdk.verify(destination,directory/'verifier',deadline,
        expected_tests=contract['expected_nonloading_tests'],commands=contract['inner_argv'])
    require(encoded(runtime.source.inventory(source)['source_entities'])==encoded(exported['source_entities'])
            and encoded(runtime.source.inventory(destination)['source_entities'])==encoded(expected),
            'Stopped product or grading copy changed during SDK execution')
    runtime.question_verify_reference(stopped_snapshot_reference)
    classification=classifier.classify(receipt,contract['expected_nonloading_tests'],commands=contract['inner_argv'])
    result={'row':row,'grading_kind':'private' if private else 'public_only_unresolved_decision',
            'classification':classification,'software_pass':classification['software_pass'] if private else None,
            'receipt_reference':runtime.question_reference(directory/'verifier/receipt.json'),
            'original_deadline':deadline,'cleanup_authorized':False,
            'model_pilot_admitted':False,'superiority_proven':False}
    runtime.atomic_json(directory/'outcome.json',result,exclusive=True)
    return result


def grade(row,stopped_snapshot_reference,selection,*,coordinator_verifier,verifier_contract):
    """Retain partial grader evidence and propagate errors to failure closure."""
    inputs.row_valid(row)
    try:
        return _grade(row,stopped_snapshot_reference,selection,
                      coordinator_verifier=coordinator_verifier,verifier_contract=verifier_contract)
    except Exception as error:
        directory=ROOT/'runtime'/row['run_id']/'grading'
        if directory.is_dir() and not directory.is_symlink() and directory.resolve()==directory:
            path=directory/'evaluation-error.json'
            if not path.exists():
                runtime.atomic_json(path,{'error':{'type':type(error).__name__,'message':str(error)},
                    'software_pass':None,'cleanup_authorized':False,'model_pilot_admitted':False},exclusive=True)
        raise
