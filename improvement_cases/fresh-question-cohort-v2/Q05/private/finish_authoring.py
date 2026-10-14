import json,re,hashlib
from pathlib import Path
root=Path('improvement_cases/fresh-question-cohort-v2')
proposal=json.loads(Path('improvement_cases/fresh-question-design-v1/proposal-v2.json').read_text())
def write(base,path,text):
 p=base/path;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(text.rstrip()+'\n')
for id in ['Q05','Q06']:
 base=root/id; ref=(base/'private/reference.dart').read_text()
 if id=='Q05':
  controls={
   'N01':ref.replace("if (!store.accessible(request.warehouseId, identity.tenantId))", "if (!store.warehouses.containsKey(request.warehouseId))"),
   'N02':ref.replace('store.commit(request.warehouseId, request.orderId, Recorded(signature, outcome), next);','store.warehouses[request.warehouseId]!.stock = Map.of(next);\n      store.commit(request.warehouseId, request.orderId, Recorded(signature, outcome), next);'),
   'N03':ref.replace('if (previous != null) {',"if (previous != null && previous.signature == 'invalid signature sentinel') {"),
   'N04':ref.replace('final reserved = shortages.isEmpty ? List<Row>.of(request.rows) : <Row>[];', 'final reserved = request.rows.where((r) => stock[r.skuId]! >= r.quantity).toList();')
  }
  tests=base/'repo/test/contract_test.dart'; text=tests.read_text().replace("const Request('other', '', [])", "const Request('other', 'o', [Row('A', 1)])").replace("const Request('missing', 'o', [Row('A', 1)])", "const Request('missing', '', [])")
  tests.write_text(text)
  docs='''# Warehouse stock reservation

Implement `ReservationService.reserve` for the warehouse app. An operator submits an order ID and positive quantities of SKU IDs to reserve against a warehouse. The UI uses the outcome to decide whether to proceed with the order. Reserving stock changes what other operators can reserve.

An example stock snapshot contains SKU-A quantity 7 and SKU-B quantity 1. An order includes SKU-A quantity 3 and SKU-B quantity 2.

Edit only `lib/implementation.dart`. The provided models and in-memory transactional store are protected. Do not add dependencies. Run the supplied Dart/Flutter checks. No device, network or provider is required.

## Contract

- C01: Use the supplied identity tenant to authorize the requested warehouse before validation or content reads. Missing and inaccessible warehouses return `not_found` with empty result lists. Never expose another tenant's stock or change its data.
- C02: After access validation, reject a whitespace-only order ID, empty rows, whitespace-only SKU ID, quantity zero or less, and duplicate exact SKU IDs with `invalid_request`, before stock reads or writes. IDs are compared exactly. Trimming is only for detecting blank values.
- C03: Read a stock snapshot after C02. Every SKU must exist. Unknown SKUs return `invalid_request` before looking up an existing order or making writes.
- C04: An order's identity is scoped to its warehouse. Identical rows under the same order ID return the recorded outcome without writes. Row order does not affect request identity. Changed SKU IDs or quantities return `conflict` without writes. Results from a retry retain their original order.
- C05: When every requested quantity is available, reserve exactly those quantities in request order and decrement each stock quantity once. Return `ok` with those reserved rows and no shortage rows.
- C06: Stock must never become negative. Reserved quantities must not exceed requested quantities. Shortage rows list the SKU, requested quantity and snapshot available quantity in request order. Returned rows must agree with persisted effects. Unrelated stock stays unchanged.
- C07: Persist stock changes and recorded outcomes together using the supplied atomic store operation. A storage failure returns `storage_failure` with empty result lists and leaves both unchanged. Do not expose exception text. Only `ok` outcomes are recorded.
- C08: The operation is synchronous. The supplied store provides atomic commit and isolated snapshot copies. Adapter construction, concurrency, UI and persistence infrastructure are outside this change.

Validation order is C01, C02, C03, C04, allocation, C07. The supplied store has nonnegative starting stock. `ok`, `not_found`, `invalid_request`, `conflict` and `storage_failure` are the complete result codes.
'''
  mapping={ 'P01':['C05','C06'], 'P02':['C01'], 'P03':['C01'], 'P04':['C02'], 'P05':['C03'], 'P06':['C04'], 'P07':['C04'], 'P08':['C07'], 'A01':['C06','user_reply'], 'A02':['C04','user_reply'], 'A03':['C07','user_reply'] }
  defects={'N01':{'defect':'Authorization reduced to warehouse existence','expected_failing_tests':['P02']},'N02':{'defect':'Stock mutated before atomic commit','expected_failing_tests':['P08']},'N03':{'defect':'Recorded order ignored and reservation executed again','expected_failing_tests':['P06','P07','A02']},'N04':{'defect':'Available rows allocated despite another row shortage','expected_failing_tests':['A01','A02']}}
 else:
  controls={
   'N01':ref.replace("if (!store.canEdit(targetWorkspaceId, identity.userId))", "if (!store.workspaces.containsKey(targetWorkspaceId))"),
   'N02':ref.replace('store.apply(targetWorkspaceId, changes);','store.workspaces[targetWorkspaceId]!.notes.addAll({for (final n in changes) n.id: n});\n      store.apply(targetWorkspaceId, changes);'),
   'N03':ref.replace('!ids.add(id)', '(ids.add(id) && id.isEmpty)'),
   'N04':ref.replace('else { unchanged.add(note.id); }', 'else if (old.title == note.title && old.body == note.body) { unchanged.add(note.id); }\n      else { changes.add(note); updated.add(note.id); }')
  }
  tests=base/'repo/test/contract_test.dart';text=tests.read_text().replace("expect(service(s).importBackup('other', 'broken').code, 'access_denied');", "expect(service(s).importBackup('other', 'broken').code, 'access_denied');\n    expect(service(s).importBackup('other', backup([note('new')], workspace:'other')).code, 'access_denied');")
  tests.write_text(text)
  docs='''# Workspace note backup import

Implement `NoteImportService.importBackup` for restoring a workspace note backup. Users restore backups into an existing workspace and continue editing its notes. A backup can be older than notes already present.

For example, a workspace contains note n-1 titled Monday plan with body Send final draft. A backup contains n-1 titled Monday plan with body Send first draft, and a new note n-2.

Parse the JSON, check workspace access, and import the notes consistently. Return the supplied report for the UI. Edit only `lib/implementation.dart`. Models, schema constants and the in-memory transactional store are protected. Add no dependencies and run the supplied Dart/Flutter checks. No device, network or provider is required.

## Contract

- C01: Before parsing or note reads, require the current supplied identity user to have edit permission for the requested target workspace. Missing workspaces and denied permission return `access_denied`. Never derive identity from JSON.
- C02: Parse a JSON object containing exactly `version`, `workspaceId`, and `notes`. Version must be the integer 1, workspaceId a string exactly equal to the requested target, and notes a list. Reject malformed JSON, unsupported versions, wrong types, missing fields and additional fields with `invalid_backup` before note reads or writes.
- C03: Each note must be an object containing exactly string `id`, `title`, and `body`. Reject a whitespace-only ID, duplicate exact IDs, wrong types, missing or additional fields. IDs are compared exactly, with trimming only for blank detection. Validate every note before note reads or writes. A bad later note rejects the whole backup.
- C04: Maximum notes is 20, title length 80 and body length 1000. Length means Dart String.length (UTF-16 code units). Limits are inclusive. Empty title/body and empty note list are valid. Preserve accepted strings exactly, including Unicode and line breaks. Do not normalize content.
- C05: Insert IDs absent from the target workspace with their incoming title/body exactly. The supplied Note constructor's default metadata applies to a new note. Existing notes with identical title/body remain unchanged, including metadata, with no rewrite.
- C06: Return `ok` for successful imports. Each incoming ID occurs exactly once across insertedIds, updatedIds and unchangedIds. Each list follows input order and describes actual persisted effects. Notes absent from the backup and other workspaces stay unchanged.
- C07: Apply changes using the atomic store operation only after validation. Storage failure returns `storage_failure` with all report lists empty, leaves all notes unchanged and does not expose exception text. A successful no-change import must not rewrite notes. No store apply is required when no notes change.
- C08: The operation is synchronous. Store snapshots are isolated copies and apply is atomic. UI, backup filesystem, live persistence, encryption and adapter construction are outside the change.

Validation order is C01, JSON and top-level schema including target match, C03/C04 for every record, note snapshot, import planning, C07. Complete result codes are `ok`, `access_denied`, `invalid_backup`, `storage_failure`. Every error result has empty report lists.
'''
  mapping={'P01':['C04','C05','C06'],'P02':['C01'],'P03':['C01'],'P04':['C02'],'P05':['C02'],'P06':['C03'],'P07':['C04'],'P08':['C05','C07'],'P09':['C07'],'P10':['C04','C07'],'A01':['C05','C06','user_reply'],'A02':['C06','C07','user_reply'],'A03':['user_reply']}
  defects={'N01':{'defect':'Edit authorization reduced to workspace existence','expected_failing_tests':['P02']},'N02':{'defect':'Notes mutated before atomic apply','expected_failing_tests':['P09']},'N03':{'defect':'Duplicate incoming IDs accepted','expected_failing_tests':['P06']},'N04':{'defect':'Conflicting existing notes overwritten','expected_failing_tests':['A01','A02','A03']}}
 for n,text in controls.items(): write(base,'private/negative-controls/'+n+'.dart',text)
 write(base,'public/request.md',docs)
 metadata={'id':id,'status':'authored_unqualified','language':'Dart service usable from Flutter','editable_files':['repo/lib/implementation.dart'], 'protected_files':['repo/pubspec.yaml','repo/lib/models.dart','repo/test/contract_test.dart'],'agent_mounts':['public/request.md','repo/'], 'private_never_mounted':True,'public_test_count':8 if id=='Q05' else 10,'private_test_count':3,'full_test_count':11 if id=='Q05' else 13,'test_provenance':mapping,'negative_controls':defects,'reference_install':'Copy private/reference.dart to repo/lib/implementation.dart for qualification only. Copy private/acceptance_test.dart to repo/test/acceptance_test.dart for full checks. Negative controls use the same replacement. Restore the starting stub and remove acceptance tests afterward. Private files must never enter the agent mount.','question_evaluation':'Track semantic policy resolution, unnecessary/repeated questions and edit chronology separately. Public-contract implementation before the reply is allowed. No exact question wording is required. A matching unsupported guess is not a resolved policy choice.','fixed_reply_source':'Own proposal-v2.json, evaluator_only.fixed_reply, verbatim','cohort_retention':'Both tasks retained regardless of baseline outcomes','sha256_inventory':{}}
 write(base,'metadata.json',json.dumps(metadata,indent=2))
 provenance={'status':'authored_unqualified','source_blind_authorized_reads':['AGENTS.md','docs/improvement-spec-v1.md','improvement_cases/fresh-question-design-v1/proposal-v2.json','own new Q05/Q06 files'], 'excluded_reads':['existing fixtures','snapshots','results','evaluation runtime','sessions','model outputs','other repositories','private answers'], 'host_preliminary_checks':'Host Flutter/Dart only, offline resolution, no dependency download, no Docker, model calls, network or existing evaluation containers. Logs retained under private/preliminary-logs.', 'design_source':'proposal-v2.json','limitations':['No qualification, difficulty, candidate comparison or superiority claim.','Root owns independent static review and fixed-image qualification.']}
 write(base,'authoring-provenance.json',json.dumps(provenance,indent=2))
