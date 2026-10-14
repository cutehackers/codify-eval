#!/usr/bin/env python3
"""Build and verify isolated Flutter fixtures. Oracle tests never enter starting repos."""
import argparse, json, pathlib, shutil, subprocess, tempfile, os
ROOT=pathlib.Path(__file__).resolve().parents[1]
FLUTTER=os.environ.get('FLUTTER_BIN','/Users/junhyounglee/Library/flutter/bin/flutter')
CASES={}
def case(id, kind, task, files, tests, reference, **extra):
    CASES[id]=dict(kind=kind,task=task,files=files,tests=tests,reference=reference,extra=extra)
PUB='''name: fixture_app\ndescription: Isolated Codify evaluation fixture\npublish_to: none\nenvironment:\n  sdk: '>=3.10.0 <4.0.0'\ndependencies:\n  flutter:\n    sdk: flutter\ndev_dependencies:\n  flutter_test:\n    sdk: flutter\nflutter:\n  uses-material-design: true\n'''
IMP="import 'package:flutter/material.dart';\n"
TEST="import 'package:flutter/material.dart';\nimport 'package:flutter_test/flutter_test.dart';\nimport 'package:fixture_app/main.dart';\n"
case('E01','widget_bug','목록의 마지막 항목도 탭하면 선택되어야 합니다. 빈 목록은 빈 화면 문구를 보여 주고, 한 항목과 여러 항목의 선택이 모두 동작해야 합니다. 선택 후 화면에 선택한 항목 이름을 표시하세요.',
{'lib/main.dart':IMP+'''void main() => runApp(const MaterialApp(home: ChoicePage(items: ['가','나','다'])));
class ChoicePage extends StatefulWidget {
  final List<String> items;
  const ChoicePage({super.key, required this.items});
  @override State<ChoicePage> createState()=>_ChoicePageState();
}
class _ChoicePageState extends State<ChoicePage> {
  String? selected;
  @override Widget build(BuildContext context)=>Scaffold(body: Column(children:[
    if(widget.items.isEmpty) const Text('항목 없음'),
    for(var i=0;i<widget.items.length;i++) TextButton(key:ValueKey('item-$i'),onPressed:(){
      if(i < widget.items.length-1) setState(()=>selected=widget.items[i]);
    },child:Text(widget.items[i])),
    Text('선택: ${selected ?? "없음"}',key:const Key('selected')),
  ]));
}
'''},TEST+'''void main(){
  testWidgets('last and singleton are selectable',(t) async {
    for(final items in <List<String>>[['끝'],['첫','중간','끝']]) {
      await t.pumpWidget(MaterialApp(home:ChoicePage(items:items)));
      await t.tap(find.byKey(ValueKey('item-${items.length-1}'))); await t.pump();
      expect(find.text('선택: 끝'),findsOneWidget);
      await t.pumpWidget(const SizedBox());
    }
  });
  testWidgets('empty list has explicit state',(t) async {
    await t.pumpWidget(const MaterialApp(home:ChoicePage(items:[])));
    expect(find.text('항목 없음'),findsOneWidget); expect(t.takeException(),isNull);
  });
}
''',{'lib/main.dart':None})
CASES['E01']['reference']['lib/main.dart']=CASES['E01']['files']['lib/main.dart'].replace('if(i < widget.items.length-1) ','')
MODEL='''class Entry { final int id; final String title; final String body; const Entry(this.id,this.title,this.body); }
'''
REPO='''import 'entry.dart';
class EntryRepository { final List<Entry> entries; EntryRepository(this.entries); Entry? find(int id) { for(final entry in entries){if(entry.id==id)return entry;} return null; } }
'''
E05MAIN=IMP+'''import 'entry.dart';
import 'repository.dart';
import 'pages.dart';
export 'entry.dart';
export 'repository.dart';
export 'pages.dart';
void main()=>runApp(EntryApp(repository:EntryRepository(const [Entry(1,'산책','저녁 산책'),Entry(2,'독서','책 읽기')])));
class EntryApp extends StatelessWidget {
 final EntryRepository repository; const EntryApp({super.key,required this.repository});
 @override Widget build(BuildContext context)=>MaterialApp(home:EntryList(repository:repository));
}
'''
E05PAGES=IMP+'''import 'repository.dart';
class EntryList extends StatelessWidget {
 final EntryRepository repository; const EntryList({super.key,required this.repository});
 @override Widget build(BuildContext context)=>Scaffold(appBar:AppBar(title:const Text('기록')),body:ListView(children:[
  for(final entry in repository.entries) ListTile(key:ValueKey('entry-${entry.id}'),title:Text(entry.title),onTap:(){}),
 ]));
}
'''
E05REF=IMP+'''import 'repository.dart';
class EntryList extends StatelessWidget {
 final EntryRepository repository; const EntryList({super.key,required this.repository});
 @override Widget build(BuildContext context)=>Scaffold(appBar:AppBar(title:const Text('기록')),body:ListView(children:[
  for(final entry in repository.entries) ListTile(key:ValueKey('entry-${entry.id}'),title:Text(entry.title),onTap:()=>Navigator.of(context).push(MaterialPageRoute<void>(builder:(_)=>EntryDetail(repository:repository,id:entry.id)))),
 ]));
}
class EntryDetail extends StatelessWidget {
 final EntryRepository repository; final int id; const EntryDetail({super.key,required this.repository,required this.id});
 @override Widget build(BuildContext context) {
  final entry=repository.find(id);
  return Scaffold(appBar:AppBar(title:Text(entry?.title ?? '찾을 수 없음')),body:Text(entry?.body ?? '기록이 없습니다'));
 }
}
'''
case('E05','cross_module_feature','기록 목록에서 각 항목을 누르면 해당 ID의 상세 화면으로 이동하도록 구현하세요. 상세에는 제목과 본문을 표시하고 뒤로 가기로 목록으로 돌아옵니다. 존재하지 않는 ID는 제목 "찾을 수 없음", 본문 "기록이 없습니다"를 표시하세요. EntryDetail(repository:, id:)를 공개 위젯으로 제공하세요. 모델과 저장소는 기존 모듈을 사용하세요.',{'lib/main.dart':E05MAIN,'lib/entry.dart':MODEL,'lib/repository.dart':REPO,'lib/pages.dart':E05PAGES},TEST+'''void main(){
 testWidgets('id based navigation and return',(t) async {
  final repo=EntryRepository(const [Entry(42,'같은 제목','첫 본문'),Entry(91,'같은 제목','둘째 본문')]);
  await t.pumpWidget(EntryApp(repository:repo));
  await t.tap(find.byKey(const ValueKey('entry-91'))); await t.pumpAndSettle();
  expect(find.text('둘째 본문'),findsOneWidget); expect(find.text('첫 본문'),findsNothing);
  await t.pageBack();await t.pumpAndSettle();expect(find.byKey(const ValueKey('entry-42')),findsOneWidget);
 });
 testWidgets('missing record',(t) async {
  await t.pumpWidget(MaterialApp(home:EntryDetail(repository:EntryRepository([]),id:999)));
  expect(find.text('찾을 수 없음'),findsOneWidget);expect(find.text('기록이 없습니다'),findsOneWidget);
 });
}
''',{'lib/pages.dart':E05REF})
E12MODEL='''import 'package:flutter/foundation.dart';
class Note { final int id; final String title; Note(this.id,this.title); }
class NoteController extends ChangeNotifier {
 final List<Note> notes=[];int nextId=1;
 void save(String title,{int? id}) {}
}
'''
E12MAIN=IMP+'''import 'notes.dart';
export 'notes.dart';
void main()=>runApp(NoteApp(controller:NoteController()));
class NoteApp extends StatelessWidget {
 final NoteController controller;const NoteApp({super.key,required this.controller});
 @override Widget build(BuildContext context)=>MaterialApp(home:NotePage(controller:controller));
}
class NotePage extends StatefulWidget {
 final NoteController controller;const NotePage({super.key,required this.controller});
 @override State<NotePage> createState()=>_NotePageState();
}
class _NotePageState extends State<NotePage> {
 final input=TextEditingController();int? editing;
 @override void dispose(){input.dispose();super.dispose();}
 @override Widget build(BuildContext context)=>Scaffold(body:AnimatedBuilder(animation:widget.controller,builder:(context,_)=>Column(children:[
 TextField(key:const Key('title'),controller:input),
 TextButton(key:const Key('save'),onPressed:(){widget.controller.save(input.text,id:editing);input.clear();editing=null;},child:const Text('저장')),
 if(widget.controller.notes.isEmpty) const Text('기록 없음'),
 for(final note in widget.controller.notes) ListTile(key:ValueKey('note-${note.id}'),title:Text(note.title),onTap:(){input.text=note.title;editing=note.id;}),
 ])));
}
'''
E12REF=E12MODEL.replace('void save(String title,{int? id}) {}','''void save(String title,{int? id}) {
  final clean=title.trim();if(clean.isEmpty)return;
  if(id==null){notes.add(Note(nextId++,clean));}else{
   final index=notes.indexWhere((n)=>n.id==id);if(index<0)return;notes[index]=Note(id,clean);
  }
  notifyListeners();
 }''')
case('E12','whole_app_flow','메모 앱의 생성, 목록, 편집 흐름을 완성하세요. 저장 시 제목의 앞뒤 공백을 제거하고 빈 제목은 저장하지 않습니다. 새 메모는 고유 ID를 받고 목록에 나타납니다. 항목을 누르면 제목을 편집할 수 있으며 저장하면 같은 ID의 항목을 갱신하고 중복 항목을 만들지 않습니다. NoteController를 유지한 채 NoteApp을 다시 만들어도 목록을 복원합니다. 실제 영구 저장은 범위 밖입니다.',{'lib/main.dart':E12MAIN,'lib/notes.dart':E12MODEL},TEST+'''void main(){
 testWidgets('create edit recreate',(t) async {
  final controller=NoteController();await t.pumpWidget(NoteApp(controller:controller));
  await t.enterText(find.byKey(const Key('title')),'   ');await t.tap(find.byKey(const Key('save')));await t.pump();
  expect(find.text('기록 없음'),findsOneWidget);
  for(final title in [' 산책 ','독서']) {await t.enterText(find.byKey(const Key('title')),title);await t.tap(find.byKey(const Key('save')));await t.pump();}
  expect(controller.notes.length,2);final id=controller.notes.first.id;expect(controller.notes.last.id,isNot(id));
  await t.tap(find.byKey(ValueKey('note-$id')));await t.pump();await t.enterText(find.byKey(const Key('title')),'긴 산책');await t.tap(find.byKey(const Key('save')));await t.pump();
  expect(controller.notes.length,2);expect(controller.notes.first.id,id);expect(controller.notes.first.title,'긴 산책');
  await t.pumpWidget(const SizedBox());await t.pumpWidget(NoteApp(controller:controller));
  expect(find.text('긴 산책'),findsOneWidget);expect(find.text('독서'),findsOneWidget);
 });
}
''',{'lib/notes.dart':E12REF})

E02SRC=IMP+'''void main()=>runApp(CounterApp(controller:CounterController()));
class CounterController extends ChangeNotifier {
 int value=0; void increment(){value++;} void reset(){value=0;}
}
class CounterApp extends StatelessWidget {
 final CounterController controller;const CounterApp({super.key,required this.controller});
 @override Widget build(BuildContext context)=>MaterialApp(home:Scaffold(body:AnimatedBuilder(animation:controller,builder:(_,_)=>Column(children:[
 Text('합계 ${controller.value}',key:const Key('total')),Text('미리보기 ${controller.value}'),
 TextButton(key:const Key('add'),onPressed:controller.increment,child:const Text('추가')),
 TextButton(key:const Key('reset'),onPressed:controller.reset,child:const Text('초기화')),
 ]))));
}
'''
case('E02','shared_state_bug','추가와 초기화가 같은 CounterController를 사용하는 합계와 미리보기에 즉시 반영되도록 고치세요. 외부에서 controller.increment/reset을 호출해도 화면이 갱신되어야 합니다. 앱을 재생성해도 전달한 controller의 값을 사용하세요.',{'lib/main.dart':E02SRC},TEST+'''void main(){testWidgets('shared state updates and recreation',(t) async {
 final c=CounterController();await t.pumpWidget(CounterApp(controller:c));
 await t.tap(find.byKey(const Key('add')));await t.pump();expect(find.text('합계 1'),findsOneWidget);expect(find.text('미리보기 1'),findsOneWidget);
 c.increment();await t.pump();expect(find.text('합계 2'),findsOneWidget);
 await t.pumpWidget(const SizedBox());await t.pumpWidget(CounterApp(controller:c));expect(find.text('미리보기 2'),findsOneWidget);
 await t.tap(find.byKey(const Key('reset')));await t.pump();expect(find.text('합계 0'),findsOneWidget);expect(find.text('미리보기 0'),findsOneWidget);c.dispose();
});}
''',{'lib/main.dart':E02SRC.replace('value++;','value++;notifyListeners();').replace('value=0;}','value=0;notifyListeners();}')})
E03SRC=IMP+'''void main()=>runApp(const MaterialApp(home:CatalogPage(items:['Apple','Banana','Apricot'])));
class CatalogPage extends StatefulWidget {
 final List<String> items;const CatalogPage({super.key,required this.items});
 @override State<CatalogPage> createState()=>_CatalogPageState();
}
class _CatalogPageState extends State<CatalogPage> {
 String query='';
 @override Widget build(BuildContext context){final visible=widget.items;
 return Scaffold(body:Column(children:[TextField(key:const Key('query'),onChanged:(v)=>setState(()=>query=v)),
 for(final item in visible) Text(item,key:ValueKey('row-$item')),
 ]));}
}
'''
case('E03','filter_ui_feature','카탈로그 검색을 구현하세요. query 입력은 앞뒤 공백과 대소문자를 무시한 부분 문자열 검색입니다. 빈 검색어는 전체 목록을 원래 순서대로 표시하고, 결과가 없으면 "검색 결과 없음"을 표시합니다. 원본 items를 변경하지 마세요.',{'lib/main.dart':E03SRC},TEST+'''void main(){testWidgets('filter clear empty state',(t) async {
 final items=['Apple','Pineapple','Pear'];await t.pumpWidget(MaterialApp(home:CatalogPage(items:items)));
 await t.enterText(find.byKey(const Key('query')),'  APPLE  ');await t.pump();expect(find.byKey(const ValueKey('row-Apple')),findsOneWidget);expect(find.byKey(const ValueKey('row-Pineapple')),findsOneWidget);expect(find.byKey(const ValueKey('row-Pear')),findsNothing);
 await t.enterText(find.byKey(const Key('query')),'zzz');await t.pump();expect(find.text('검색 결과 없음'),findsOneWidget);
 await t.enterText(find.byKey(const Key('query')),'');await t.pump();expect(find.byKey(const ValueKey('row-Pear')),findsOneWidget);expect(items,['Apple','Pineapple','Pear']);
});}
''',{'lib/main.dart':E03SRC.replace('final visible=widget.items;','final q=query.trim().toLowerCase();final visible=widget.items.where((item)=>item.toLowerCase().contains(q)).toList();').replace('for(final item in visible)','if(visible.isEmpty) const Text(\'검색 결과 없음\'),\n for(final item in visible)')})
E04SRC=IMP+'''typedef SaveName=Future<void> Function(String name);
void main()=>runApp(MaterialApp(home:NameForm(save:(_) async {})));
class NameForm extends StatefulWidget {
 final SaveName save;const NameForm({super.key,required this.save});
 @override State<NameForm> createState()=>_NameFormState();
}
class _NameFormState extends State<NameForm> {
 final input=TextEditingController();String message='';bool busy=false;
 @override void dispose(){input.dispose();super.dispose();}
 Future<void> submit() async {await widget.save(input.text);setState(()=>message='저장 완료');}
 @override Widget build(BuildContext context)=>Scaffold(body:Column(children:[TextField(key:const Key('name'),controller:input),TextButton(key:const Key('submit'),onPressed:busy?null:submit,child:const Text('저장')),Text(message)]));
}
'''
E04REF=E04SRC.replace("Future<void> submit() async {await widget.save(input.text);setState(()=>message='저장 완료');}","""Future<void> submit() async {
 final clean=input.text.trim();if(clean.isEmpty){setState(()=>message='이름을 입력하세요');return;}
 if(busy)return;setState((){busy=true;message='저장 중';});
 try{await widget.save(clean);if(mounted)setState(()=>message='저장 완료');}
 catch(_){if(mounted)setState(()=>message='저장 실패. 다시 시도하세요');}
 finally{if(mounted)setState(()=>busy=false);}
 }""")
case('E04','form_failure_ui','이름 저장 폼을 완성하세요. 공백만 입력하면 "이름을 입력하세요"를 표시하고 save를 호출하지 않습니다. 이름은 trim 후 전달합니다. 저장 중 "저장 중"을 표시하고 저장 버튼을 비활성화합니다. 성공은 "저장 완료", 예외는 "저장 실패. 다시 시도하세요"로 표시하고 재시도가 가능해야 합니다. 저장 중 위젯이 제거되어도 예외가 발생하지 않아야 합니다.',{'lib/main.dart':E04SRC},TEST+"import 'dart:async';\n"+'''void main(){testWidgets('validation failure retry pending',(t) async {
 int calls=0;String? received;Completer<void>? pending;
 await t.pumpWidget(MaterialApp(home:NameForm(save:(name) async {calls++;received=name;if(calls==1)throw StateError('disk');pending=Completer<void>();await pending!.future;})));
 await t.enterText(find.byKey(const Key('name')),'  ');await t.tap(find.byKey(const Key('submit')));await t.pump();expect(calls,0);expect(find.text('이름을 입력하세요'),findsOneWidget);
 await t.enterText(find.byKey(const Key('name')),'  민수  ');await t.tap(find.byKey(const Key('submit')));await t.pump();expect(received,'민수');expect(find.text('저장 실패. 다시 시도하세요'),findsOneWidget);
 await t.tap(find.byKey(const Key('submit')));await t.pump();expect(find.text('저장 중'),findsOneWidget);expect(t.widget<TextButton>(find.byKey(const Key('submit'))).onPressed,isNull);
 pending!.complete();await t.pump();expect(find.text('저장 완료'),findsOneWidget);
 await t.tap(find.byKey(const Key('submit')));await t.pump();await t.pumpWidget(const SizedBox());pending!.complete();await t.pump();expect(t.takeException(),isNull);
});}
''',{'lib/main.dart':E04REF})
E06STORE='''abstract class LocalStore {Future<String?> read();Future<void> write(String value);}
class MemoryStore implements LocalStore {String? value;@override Future<String?> read() async=>value;@override Future<void> write(String value) async {this.value=value;}}
'''
E06SRC=IMP+'''import 'store.dart';
export 'store.dart';
void main()=>runApp(MaterialApp(home:DraftPage(store:MemoryStore())));
class DraftPage extends StatefulWidget {
 final LocalStore store;const DraftPage({super.key,required this.store});
 @override State<DraftPage> createState()=>_DraftPageState();
}
class _DraftPageState extends State<DraftPage> {
 final input=TextEditingController();String message='';
 @override void dispose(){input.dispose();super.dispose();}
 Future<void> save() async {setState(()=>message='저장됨');}
 @override Widget build(BuildContext context)=>Scaffold(body:Column(children:[TextField(key:const Key('draft'),controller:input),TextButton(key:const Key('save'),onPressed:save,child:const Text('저장')),Text(message)]));
}
'''
E06REF=E06SRC.replace("key:const Key('draft'),controller:input","key:const Key('draft'),controller:input,maxLines:null").replace("@override void dispose()", "@override void initState(){super.initState();restore();}\n Future<void> restore() async {try{final value=await widget.store.read();if(mounted)setState(()=>input.text=value ?? '');}catch(_){if(mounted)setState(()=>message='불러오기 실패');}}\n @override void dispose()") .replace("Future<void> save() async {setState(()=>message='저장됨');}","Future<void> save() async {try{await widget.store.write(input.text);if(mounted)setState(()=>message='저장됨');}catch(_){if(mounted)setState(()=>message='저장 실패');}}")
case('E06','local_persistence','교체 가능한 LocalStore를 사용해 입력 초안을 저장하고 위젯 재생성 시 불러오세요. 새 저장소의 null은 빈 초안을 의미합니다. write가 완료된 뒤에만 "저장됨"을 표시하고 실패 시 "저장 실패"를 표시하세요. read 실패 시 "불러오기 실패"를 표시하세요. 입력은 여러 줄을 지원하고 저장소의 내용은 공백과 줄바꿈을 포함해 입력 그대로 보존합니다. 외부 provider나 실제 디스크 접근은 필요 없습니다.',{'lib/main.dart':E06SRC,'lib/store.dart':E06STORE},TEST+"import 'dart:async';\n"+'''class FailingStore implements LocalStore {
 @override Future<String?> read() async=>throw StateError('read');
 @override Future<void> write(String value) async=>throw StateError('write');
}
class DelayedStore extends MemoryStore {final pending=Completer<void>();@override Future<void> write(String value) async {await pending.future;super.write(value);}}
void main(){
 testWidgets('save reload preserves exact input',(t) async {final s=MemoryStore();await t.pumpWidget(MaterialApp(home:DraftPage(store:s)));await t.pump();await t.enterText(find.byKey(const Key('draft')),'  원문\\n둘째 줄  ');await t.tap(find.byKey(const Key('save')));await t.pump();expect(s.value,'  원문\\n둘째 줄  ');await t.pumpWidget(const SizedBox());await t.pumpWidget(MaterialApp(home:DraftPage(store:s)));await t.pump();expect(t.widget<TextField>(find.byKey(const Key('draft'))).controller!.text,s.value);});
 testWidgets('errors and deferred success',(t) async {await t.pumpWidget(MaterialApp(home:DraftPage(store:FailingStore())));await t.pump();expect(find.text('불러오기 실패'),findsOneWidget);await t.tap(find.byKey(const Key('save')));await t.pump();expect(find.text('저장 실패'),findsOneWidget);await t.pumpWidget(const SizedBox());final s=DelayedStore();await t.pumpWidget(MaterialApp(home:DraftPage(store:s)));await t.pump();await t.tap(find.byKey(const Key('save')));await t.pump();expect(find.text('저장됨'),findsNothing);s.pending.complete();await t.pump();expect(find.text('저장됨'),findsOneWidget);});
}
''',{'lib/main.dart':E06REF})
E07SRC='''import 'dart:convert';
class SavedTask {
 final String title;final bool done;const SavedTask(this.title,this.done);
 Map<String,Object> toJson()=>{'schema':2,'title':title,'done':done};
}
List<SavedTask> decodeTasks(String data){final values=jsonDecode(data) as List<dynamic>;return values.map((v){final m=v as Map<String,dynamic>;return SavedTask(m['title'] as String,m['done'] as bool);}).toList();}
String encodeTasks(List<SavedTask> tasks)=>jsonEncode(tasks.map((t)=>t.toJson()).toList());
'''
E07REF=E07SRC[:E07SRC.index('List<SavedTask> decodeTasks')]+'''List<SavedTask> decodeTasks(String data){
 final root=jsonDecode(data);if(root is! List)throw const FormatException('expected list');
 return root.map((v){if(v is! Map)throw const FormatException('expected object');
 final version=v['schema'];if(v.containsKey('schema') && version!=1 && version!=2)throw const FormatException('unsupported schema');
 final title=v.containsKey('title') ? v['title'] : v['name'];final done=v.containsKey('done') ? v['done'] : false;
 if(title is! String || done is! bool)throw const FormatException('invalid task');
 return SavedTask(title,done);}).toList();
}
String encodeTasks(List<SavedTask> tasks)=>jsonEncode(tasks.map((t)=>t.toJson()).toList());
'''
case('E07','serialized_compatibility','SavedTask JSON 호환성을 보완하세요. 과거 형식은 schema가 없거나 1이며 title 대신 name을 사용할 수 있습니다. title이 있으면 name보다 우선합니다. done 누락은 false입니다. 현재 schema 2도 읽고, 저장은 항상 schema 2/title/done 형식으로 합니다. 루트가 목록이 아니거나 항목/필드 타입이 잘못되거나 schema가 1/2 이외면 FormatException을 던져야 합니다. JSON 손상도 FormatException입니다.',{'lib/main.dart':E07SRC},"import 'dart:convert';\nimport 'package:flutter_test/flutter_test.dart';\nimport 'package:fixture_app/main.dart';\n"+'''void main(){
 test('legacy migration and current roundtrip',(){final values=decodeTasks('[{"name":"옛 기록"},{"schema":1,"name":"이전","done":true},{"schema":2,"title":"새 기록","name":"무시","done":false}]');expect(values.map((v)=>v.title),['옛 기록','이전','새 기록']);expect(values.map((v)=>v.done),[false,true,false]);final encoded=jsonDecode(encodeTasks(values)) as List;expect(encoded.first,{'schema':2,'title':'옛 기록','done':false});expect(decodeTasks(encodeTasks(values)).length,3);});
 test('invalid shape uses stable error type',(){for(final input in ['{}','[4]','[{"name":4}]','[{"title":"x","done":"yes"}]','[{"schema":3,"title":"x"}]','[{"title":null,"name":"x"}]','[{"title":"x","done":null}]','broken']){expect(()=>decodeTasks(input),throwsFormatException,reason:input);}});
}
''',{'lib/main.dart':E07REF})

E08SERVICE='''abstract class RemoteService {Future<List<String>> fetch();}
class SampleService implements RemoteService {@override Future<List<String>> fetch() async=>['소식'];}
class NewsAdapter {final RemoteService service;NewsAdapter(this.service);Future<List<String>> load()=>service.fetch();}
'''
E08SRC=IMP+'''import 'service.dart';
export 'service.dart';
void main()=>runApp(MaterialApp(home:NewsPage(adapter:NewsAdapter(SampleService()))));
class NewsPage extends StatefulWidget {
 final NewsAdapter adapter;const NewsPage({super.key,required this.adapter});
 @override State<NewsPage> createState()=>_NewsPageState();
}
class _NewsPageState extends State<NewsPage> {
 List<String> news=[];bool busy=false;String? error;
 @override void initState(){super.initState();load();}
 Future<void> load() async {final result=await widget.adapter.load();if(mounted)setState(()=>news=result);}
 @override Widget build(BuildContext context)=>Scaffold(body:Column(children:[
 if(busy)const Text('불러오는 중'),if(error!=null)Text(error!),
 for(final title in news)Text(title),
 TextButton(key:const Key('retry'),onPressed:load,child:const Text('다시 시도')),
 ]));
}
'''
E08REF=E08SRC.replace('Future<void> load() async {final result=await widget.adapter.load();if(mounted)setState(()=>news=result);}',"""Future<void> load() async {
 if(busy)return;setState((){busy=true;error=null;});
 try{final result=await widget.adapter.load();if(mounted)setState(()=>news=result);}
 catch(_){if(mounted)setState(()=>error='소식을 불러오지 못했습니다');}
 finally{if(mounted)setState(()=>busy=false);}
 }""").replace('onPressed:load','onPressed:busy?null:load').replace('for(final title in news)','if(!busy && error==null && news.isEmpty)const Text(\'소식 없음\'),\n for(final title in news)')
case('E08','adapter_retry_ui','RemoteService와 NewsAdapter를 사용하는 소식 화면에서 초기 로딩과 실패 후 재시도를 완성하세요. 로딩 중 "불러오는 중", 실패 시 "소식을 불러오지 못했습니다", 성공 빈 목록은 "소식 없음"입니다. 재시도 버튼은 로딩 중 비활성화하며 한 번만 요청합니다. 성공 시 최신 항목을 표시하고 오류를 지웁니다. 위젯 제거 후 응답이 와도 예외가 없어야 합니다. 실제 네트워크 호출은 범위 밖입니다.',{'lib/main.dart':E08SRC,'lib/service.dart':E08SERVICE},TEST+"import 'dart:async';\n"+'''class ScriptService implements RemoteService {int calls=0;final pending=Completer<List<String>>();@override Future<List<String>> fetch() async {calls++;if(calls==1)throw StateError('offline');if(calls==2)return pending.future;return [];}}
void main(){testWidgets('failure recovery and empty',(t) async {
 final service=ScriptService();await t.pumpWidget(MaterialApp(home:NewsPage(adapter:NewsAdapter(service))));await t.pump();expect(find.text('소식을 불러오지 못했습니다'),findsOneWidget);
 await t.tap(find.byKey(const Key('retry')));await t.pump();expect(find.text('불러오는 중'),findsOneWidget);expect(t.widget<TextButton>(find.byKey(const Key('retry'))).onPressed,isNull);expect(service.calls,2);
 service.pending.complete(['복구 소식','두 번째']);await t.pump();expect(find.text('복구 소식'),findsOneWidget);expect(find.text('소식을 불러오지 못했습니다'),findsNothing);
 await t.tap(find.byKey(const Key('retry')));await t.pump();expect(find.text('소식 없음'),findsOneWidget);
});}
''',{'lib/main.dart':E08REF})
E09SRC='''import 'package:flutter/foundation.dart';
typedef SearchService=Future<List<String>> Function(String query);
class SearchController extends ChangeNotifier {
 final SearchService service;SearchController(this.service);List<String> results=[];String? error;bool busy=false;
 Future<void> search(String query) async {busy=true;notifyListeners();try{results=await service(query);error=null;}catch(_){error='검색 실패';}busy=false;notifyListeners();}
}
'''
E09REF='''import 'package:flutter/foundation.dart';
typedef SearchService=Future<List<String>> Function(String query);
class SearchController extends ChangeNotifier {
 final SearchService service;SearchController(this.service);List<String> results=[];String? error;bool busy=false;int _generation=0;bool _disposed=false;
 Future<void> search(String query) async {
 if(_disposed)return;final generation=++_generation;busy=true;error=null;notifyListeners();
 try{final next=await service(query);if(_disposed || generation!=_generation)return;results=next;error=null;}
 catch(_){if(_disposed || generation!=_generation)return;error='검색 실패';}
 if(_disposed || generation!=_generation)return;busy=false;notifyListeners();
 }
 @override void dispose(){_disposed=true;_generation++;super.dispose();}
}
'''
case('E09','async_race','검색 컨트롤러의 요청 경합을 고치세요. 여러 검색을 연속 실행하면 마지막 시작한 요청만 results/error/busy를 갱신합니다. 이전 요청 성공과 실패는 모두 무시합니다. 새 검색 시작 시 error를 지우고 busy=true를 알립니다. 마지막 요청 실패 후 같은 쿼리 재시도도 가능해야 합니다. dispose 후 응답은 무시하고 이후 search도 서비스 호출 없이 종료합니다.',{'lib/main.dart':E09SRC},"import 'dart:async';\nimport 'package:flutter_test/flutter_test.dart';\nimport 'package:fixture_app/main.dart';\n"+'''void main(){
 test('newest wins success and failure',() async {final requests=<Completer<List<String>>>[];final c=SearchController((_) {final p=Completer<List<String>>();requests.add(p);return p.future;});final first=c.search('a');final latest=c.search('b');requests[1].complete(['latest']);await latest;requests[0].complete(['stale']);await first;expect(c.results,['latest']);expect(c.busy,false);final old=c.search('c');final next=c.search('d');requests[3].complete(['d']);await next;requests[2].completeError(StateError('old'));await old;expect(c.error,isNull);expect(c.results,['d']);c.dispose();});
 test('failure retry disposal',() async {int calls=0;final requests=<Completer<List<String>>>[];final c=SearchController((_) {calls++;final p=Completer<List<String>>();requests.add(p);return p.future;});final fail=c.search('same');requests[0].completeError(StateError('x'));await fail;expect(c.error,'검색 실패');final retry=c.search('same');expect(c.error,isNull);expect(c.busy,true);requests[1].complete(['ok']);await retry;expect(c.results,['ok']);final pending=c.search('dispose');c.dispose();requests[2].complete(['late']);await pending;await c.search('ignored');expect(calls,3);});
}
''',{'lib/main.dart':E09REF})
E10SRC=IMP+'''void main()=>runApp(ShelfApp(controller:ShelfController()));
class Book {final String isbn;final String title;const Book(this.isbn,this.title);}
class ShelfController extends ChangeNotifier {final List<Book> books=[];void add(Book book){books.add(book);notifyListeners();}}
class ShelfApp extends StatefulWidget {
 final ShelfController controller;const ShelfApp({super.key,required this.controller});
 @override State<ShelfApp> createState()=>_ShelfAppState();
}
class _ShelfAppState extends State<ShelfApp> {
 final isbn=TextEditingController();final title=TextEditingController();
 @override void dispose(){isbn.dispose();title.dispose();super.dispose();}
 @override Widget build(BuildContext context)=>MaterialApp(home:Scaffold(body:AnimatedBuilder(animation:widget.controller,builder:(_,_)=>Column(children:[TextField(key:const Key('isbn'),controller:isbn),TextField(key:const Key('title'),controller:title),TextButton(key:const Key('add'),onPressed:()=>widget.controller.add(Book(isbn.text,title.text)),child:const Text('등록')),for(final b in widget.controller.books)Text('${b.isbn}: ${b.title}')]))));
}
'''
E10REF=E10SRC.replace('books.add(book);notifyListeners();',"final index=books.indexWhere((b)=>b.isbn==book.isbn);if(index<0){books.add(book);}else{books[index]=book;}notifyListeners();")
case('E10','explicit_decision','서재에 같은 ISBN을 다시 등록할 때 동작을 정한 뒤 구현하세요. 최초 요청에는 중복 처리 정책이 비어 있으므로 decisionID "shelf-duplicate-policy"로 사용자에게 "기존 항목 유지"와 "기존 항목의 제목 교체" 중 선택을 요청해야 합니다. 답변을 받기 전에는 중복 정책을 임의로 정하지 마세요. 제목 교체를 선택하면 기존 위치와 ISBN을 유지하고 제목만 새 값으로 바꾸며 목록 개수를 늘리지 않습니다. 기존 항목 유지를 선택하면 아무 항목도 변경하지 않습니다. 다른 ISBN은 새 항목입니다. 문자열은 그대로 비교합니다.',{'lib/main.dart':E10SRC},TEST+'''void main(){testWidgets('chosen replacement semantics',(t) async {
 final c=ShelfController();await t.pumpWidget(ShelfApp(controller:c));
 for(final data in [['A','처음'],['B','둘째'],['A','개정']]){await t.enterText(find.byKey(const Key('isbn')),data[0]);await t.enterText(find.byKey(const Key('title')),data[1]);await t.tap(find.byKey(const Key('add')));await t.pump();}
 expect(c.books.map((b)=>b.isbn),['A','B']);expect(c.books.map((b)=>b.title),['개정','둘째']);expect(find.text('A: 개정'),findsOneWidget);expect(find.text('A: 처음'),findsNothing);
});}
''',{'lib/main.dart':E10REF},decision_rules=[{'decisionID':'shelf-duplicate-policy','trigger':'duplicate ISBN behavior unspecified','options':['기존 항목 유지','기존 항목의 제목 교체'],'choice':'기존 항목의 제목 교체','required_before_implementation':True}])
E11BANNER="const userBanner='사용자가 작성한 문구: 오늘도 꾸준히';\n"
E11SRC=IMP+'''import 'user_banner.dart';
void main()=>runApp(const TodoPage());
class TodoPage extends StatefulWidget {const TodoPage({super.key});@override State<TodoPage> createState()=>_TodoPageState();}
class _TodoPageState extends State<TodoPage> {
 bool done=false;
 @override Widget build(BuildContext context)=>MaterialApp(home:Scaffold(body:Column(children:[const Text(userBanner),Checkbox(key:const Key('done'),value:done,onChanged:(value){}),Text(done?'완료':'진행 중')])));
}
'''
case('E11','dirty_preservation','체크박스를 누르면 할 일의 완료 상태와 문구가 즉시 전환되도록 고치세요. 다시 누르면 진행 중으로 돌아옵니다. lib/user_banner.dart에는 사용자가 이미 수정한 미커밋 문구가 있으므로 바이트를 그대로 유지하세요. 그 파일의 Git 변경을 취소하거나 커밋하지 마세요.',{'lib/main.dart':E11SRC,'lib/user_banner.dart':E11BANNER},TEST+'''void main(){testWidgets('toggle and existing banner',(t) async {await t.pumpWidget(const TodoPage());expect(find.text('사용자가 작성한 문구: 오늘도 꾸준히'),findsOneWidget);await t.tap(find.byKey(const Key('done')));await t.pump();expect(find.text('완료'),findsOneWidget);await t.tap(find.byKey(const Key('done')));await t.pump();expect(find.text('진행 중'),findsOneWidget);});}
''',{'lib/main.dart':E11SRC.replace('onChanged:(value){}','onChanged:(value)=>setState(()=>done=value ?? false)')},protected_paths=['pubspec.yaml','lib/user_banner.dart'],initial_dirty={'path':'lib/user_banner.dart','head_content':"const userBanner='기본 문구';\n",'working_content':E11BANNER})

H01SRC=IMP+'''void main()=>runApp(const MaterialApp(home:QuantityPage(maximum:5)));
class QuantityPage extends StatefulWidget {final int maximum;const QuantityPage({super.key,required this.maximum});@override State<QuantityPage> createState()=>_QuantityPageState();}
class _QuantityPageState extends State<QuantityPage> {int count=0;@override Widget build(BuildContext context)=>Scaffold(body:Column(children:[Text('수량 $count'),TextButton(key:const Key('minus'),onPressed:()=>setState(()=>count--),child:const Text('감소')),TextButton(key:const Key('plus'),onPressed:()=>setState(()=>count++),child:const Text('증가'))]));}
'''
H01REF=H01SRC.replace('onPressed:()=>setState(()=>count--)','onPressed:count>0?()=>setState(()=>count--):null').replace('onPressed:()=>setState(()=>count++)','onPressed:count<widget.maximum?()=>setState(()=>count++):null')
case('H01','heldout_widget_bug','수량 선택 화면을 고치세요. 수량은 0부터 maximum까지이며 두 끝값을 포함합니다. 감소는 0에서, 증가는 maximum에서 비활성화합니다. maximum=0도 지원하세요. 범위를 벗어나는 수량이 표시되면 안 됩니다. maximum은 음이 아닌 값으로 전달됩니다.',{'lib/main.dart':H01SRC},TEST+'''void main(){testWidgets('inclusive boundaries',(t) async {for(final max in [0,1,4]){await t.pumpWidget(MaterialApp(home:QuantityPage(maximum:max)));expect(t.widget<TextButton>(find.byKey(const Key('minus'))).onPressed,isNull);for(var i=0;i<max;i++){await t.tap(find.byKey(const Key('plus')));await t.pump();}expect(find.text('수량 $max'),findsOneWidget);expect(t.widget<TextButton>(find.byKey(const Key('plus'))).onPressed,isNull);for(var i=0;i<max;i++){await t.tap(find.byKey(const Key('minus')));await t.pump();}expect(find.text('수량 0'),findsOneWidget);await t.pumpWidget(const SizedBox());}});}
''',{'lib/main.dart':H01REF})
H02MODEL='''import 'package:flutter/foundation.dart';
class Product {final String sku;final String name;final int cents;const Product(this.sku,this.name,this.cents);}
class Basket extends ChangeNotifier {final Map<String,int> counts={};final List<Product> products;Basket(this.products);void add(String sku){}int get totalCents=>0;}
'''
H02CAT=IMP+'''import 'basket.dart';
class ProductList extends StatelessWidget {final Basket basket;const ProductList({super.key,required this.basket});@override Widget build(BuildContext context)=>Column(children:[for(final product in basket.products)TextButton(key:ValueKey('add-${product.sku}'),onPressed:()=>basket.add(product.sku),child:Text(product.name))]);}
'''
H02SUMMARY=IMP+'''import 'basket.dart';
class BasketSummary extends StatelessWidget {final Basket basket;const BasketSummary({super.key,required this.basket});@override Widget build(BuildContext context)=>AnimatedBuilder(animation:basket,builder:(_,_)=>Column(children:[for(final product in basket.products)if((basket.counts[product.sku] ?? 0)>0)Text('${product.name} x${basket.counts[product.sku]}'),Text('총액 ${basket.totalCents} 센트')]));}
'''
H02MAIN=IMP+'''import 'basket.dart';import 'catalog.dart';import 'summary.dart';export 'basket.dart';
void main()=>runApp(ShopApp(basket:Basket(const [Product('one','노트',300)])));
class ShopApp extends StatelessWidget {final Basket basket;const ShopApp({super.key,required this.basket});@override Widget build(BuildContext context)=>MaterialApp(home:Scaffold(body:Column(children:[ProductList(basket:basket),BasketSummary(basket:basket)])));}
'''
H02REF=H02MODEL.replace('void add(String sku){}int get totalCents=>0;',"void add(String sku){if(!products.any((p)=>p.sku==sku))return;counts[sku]=(counts[sku] ?? 0)+1;notifyListeners();}int get totalCents=>products.fold(0,(sum,p)=>sum+p.cents*(counts[p.sku] ?? 0));")
case('H02','heldout_cross_module_feature','상품 목록과 장바구니 요약을 연결하세요. 상품 버튼을 누를 때마다 SKU별 수량이 1 증가하며 요약에 상품명 x수량과 센트 단위 합계를 즉시 표시합니다. 알 수 없는 SKU를 Basket.add에 넘기면 무시합니다. 동일 이름의 다른 SKU는 별도 상품입니다. Basket을 유지한 채 앱을 다시 생성해도 수량이 보존되어야 합니다. 기존 catalog/summary/basket 모듈을 활용하세요.',{'lib/main.dart':H02MAIN,'lib/basket.dart':H02MODEL,'lib/catalog.dart':H02CAT,'lib/summary.dart':H02SUMMARY},TEST+'''void main(){testWidgets('sku quantities total across modules',(t) async {final b=Basket(const [Product('a','노트',125),Product('b','노트',250)]);await t.pumpWidget(ShopApp(basket:b));for(final sku in ['a','a','b']){await t.tap(find.byKey(ValueKey('add-$sku')));await t.pump();}expect(b.counts,{'a':2,'b':1});expect(find.text('노트 x2'),findsOneWidget);expect(find.text('노트 x1'),findsOneWidget);expect(find.text('총액 500 센트'),findsOneWidget);b.add('missing');await t.pump();expect(b.totalCents,500);await t.pumpWidget(const SizedBox());await t.pumpWidget(ShopApp(basket:b));expect(find.text('총액 500 센트'),findsOneWidget);});}
''',{'lib/basket.dart':H02REF})
H03SERVICE='''import 'dart:convert';
abstract class StatusTransport {Future<String> request();}
class SampleTransport implements StatusTransport {@override Future<String> request() async=>' {"status":"정상"} ';}
class StatusAdapter {final StatusTransport transport;StatusAdapter(this.transport);Future<String> fetch() async {final data=jsonDecode(await transport.request()) as Map<String,dynamic>;return data['status'] as String;}}
'''
H03SRC=IMP+'''import 'adapter.dart';export 'adapter.dart';
void main()=>runApp(MaterialApp(home:StatusPage(adapter:StatusAdapter(SampleTransport()))));
class StatusPage extends StatefulWidget {final StatusAdapter adapter;const StatusPage({super.key,required this.adapter});@override State<StatusPage> createState()=>_StatusPageState();}
class _StatusPageState extends State<StatusPage> {String status='';bool busy=false;@override void initState(){super.initState();refresh();}Future<void> refresh() async {status=await widget.adapter.fetch();if(mounted)setState((){});}@override Widget build(BuildContext context)=>Scaffold(body:Column(children:[Text(status),TextButton(key:const Key('refresh'),onPressed:refresh,child:const Text('새로고침'))]));}
'''
H03REF=H03SRC.replace("Future<void> refresh() async {status=await widget.adapter.fetch();if(mounted)setState((){});}","Future<void> refresh() async {if(busy)return;setState((){busy=true;status='확인 중';});try{final value=await widget.adapter.fetch();if(mounted)setState(()=>status=value);}catch(_){if(mounted)setState(()=>status='상태 확인 실패');}finally{if(mounted)setState(()=>busy=false);}}") .replace('onPressed:refresh','onPressed:busy?null:refresh')
H03AREF=H03SERVICE.replace("final data=jsonDecode(await transport.request()) as Map<String,dynamic>;return data['status'] as String;","final data=jsonDecode(await transport.request());if(data is! Map || data['status'] is! String || (data['status'] as String).trim().isEmpty)throw const FormatException('invalid status');return data['status'] as String;")
case('H03','heldout_adapter_recovery','상태 화면과 JSON 어댑터의 오류 복구를 구현하세요. StatusAdapter.fetch는 status가 비어 있지 않은 문자열인 JSON 객체만 받아들이며 잘못된 응답은 FormatException입니다. 네트워크 예외나 JSON 오류는 화면에서 "상태 확인 실패"로 표시합니다. 초기 요청 및 새로고침 동안 "확인 중"과 비활성화된 버튼을 표시하고 성공 시 서버의 원문 상태를 표시합니다. 실패 후 새로고침으로 복구할 수 있어야 합니다.',{'lib/main.dart':H03SRC,'lib/adapter.dart':H03SERVICE},TEST+"import 'dart:async';\n"+'''class SequenceTransport implements StatusTransport {int calls=0;final pending=Completer<String>();@override Future<String> request() async {calls++;if(calls==1)return '{"status":null}';return pending.future;}}
class ValueTransport implements StatusTransport {final String value;ValueTransport(this.value);@override Future<String> request() async=>value;}
void main(){test('adapter shape validation',() async {for(final value in ['[]','{"status":2}','{"status":"  "}','{}']){await expectLater(StatusAdapter(ValueTransport(value)).fetch(),throwsFormatException);}});testWidgets('malformed then recovered',(t) async {final service=SequenceTransport();await t.pumpWidget(MaterialApp(home:StatusPage(adapter:StatusAdapter(service))));await t.pump();expect(find.text('상태 확인 실패'),findsOneWidget);await t.tap(find.byKey(const Key('refresh')));await t.pump();expect(find.text('확인 중'),findsOneWidget);expect(t.widget<TextButton>(find.byKey(const Key('refresh'))).onPressed,isNull);service.pending.complete('{"status":"  정상  "}');await t.pump();expect(find.text('  정상  '),findsOneWidget);expect(service.calls,2);});}
''',{'lib/main.dart':H03REF,'lib/adapter.dart':H03AREF})
H04SRC='''import 'dart:convert';
class Preferences {final String theme;final double scale;const Preferences(this.theme,this.scale);String encode()=>jsonEncode({'version':2,'theme':theme,'scale':scale});}
Preferences readPreferences(String data){final m=jsonDecode(data) as Map<String,dynamic>;return Preferences(m['theme'] as String,(m['scale'] as num).toDouble());}
'''
H04REF=H04SRC[:H04SRC.index('Preferences readPreferences')]+'''Preferences readPreferences(String data){
 final m=jsonDecode(data);if(m is! Map)throw const FormatException('expected object');
 final version=m['version'];if(m.containsKey('version') && version!=1 && version!=2)throw const FormatException('unsupported version');
 final theme=m.containsKey('theme') ? m['theme'] : (m.containsKey('mode') ? m['mode'] : 'system');final scale=m.containsKey('scale') ? m['scale'] : 1.0;
 if(theme is! String || !['light','dark','system'].contains(theme) || scale is! num || !scale.isFinite || scale<0.5 || scale>2.0)throw const FormatException('invalid preferences');
 return Preferences(theme,scale.toDouble());
}
'''
case('H04','heldout_data_compatibility','설정 JSON을 이전 버전과 호환되게 읽으세요. version 누락 또는 1은 mode 필드를 사용할 수 있으며 theme이 있으면 우선합니다. theme/mode 누락은 system, scale 누락은 1.0입니다. version 2도 같은 기본값을 적용합니다. 저장은 항상 version 2/theme/scale입니다. 허용 theme은 light/dark/system, scale은 0.5~2.0의 유한한 숫자입니다. 잘못된 루트, 값 또는 지원하지 않는 version은 FormatException입니다.',{'lib/main.dart':H04SRC},"import 'dart:convert';\nimport 'package:flutter_test/flutter_test.dart';\nimport 'package:fixture_app/main.dart';\n"+'''void main(){test('legacy and current migration',(){final defaults=readPreferences('{}');expect(defaults.theme,'system');expect(defaults.scale,1.0);final old=readPreferences('{"version":1,"mode":"dark","scale":2}');expect(old.theme,'dark');expect(old.scale,2.0);final current=readPreferences('{"version":2,"theme":"light","mode":"dark","scale":0.5}');expect(current.theme,'light');expect(jsonDecode(current.encode()),{'version':2,'theme':'light','scale':0.5});expect(readPreferences(current.encode()).scale,0.5);});test('invalid values rejected',(){for(final value in ['[]','{"version":9}','{"theme":"other"}','{"scale":0.49}','{"scale":2.01}','{"scale":"1"}','{"theme":4}','{"theme":null}','{"scale":null}','broken']){expect(()=>readPreferences(value),throwsFormatException,reason:value);}});}
''',{'lib/main.dart':H04REF})

def build(ids):
 for id in ids:
  c=CASES[id];base=ROOT/'fixtures'/id;base.mkdir(parents=True,exist_ok=True)
  for name in ('repo','reference'):
   folder=base/name
   if folder.exists():shutil.rmtree(folder)
   files={'pubspec.yaml':PUB,**c['files']}
   if name=='reference':files.update(c['reference'])
   for path,content in files.items():
    target=folder/path;target.parent.mkdir(parents=True,exist_ok=True);target.write_text(content)
  (base/'oracle'/'test').mkdir(parents=True,exist_ok=True)
  (base/'oracle'/'test'/'acceptance_test.dart').write_text(c['tests'])
  (base/'task.md').write_text('# '+id+'\n\n'+c['task']+'\n\n허용: lib/ 내부 구현 변경과 새로운 test/ 회귀 테스트 추가. 보호: pubspec.yaml, 사전 존재하는 사용자 파일. 공개 클래스와 생성자 계약을 유지하세요. 기존 테스트나 검증 도구를 약화해서 통과시키지 마세요.\n')
  metadata={'id':id,'type':c['kind'],'framework':'flutter','command':['flutter','test','test/acceptance_test.dart'],'allowed_paths':['lib/**','test/**'],'protected_paths':['pubspec.yaml'],'oracle_path':'oracle/test','solution_path':'reference','requirements_disclosed':True,**c['extra']}
  (base/'metadata.json').write_text(json.dumps(metadata,ensure_ascii=False,indent=2)+'\n')
  paths=[str(path) for path in base.rglob('*.dart') if path.name!='user_banner.dart']
  subprocess.run([str(pathlib.Path(FLUTTER).with_name('dart')),'format',*paths],check=True,stdout=subprocess.DEVNULL)
def verify(ids):
 results=[]
 for id in ids:
  base=ROOT/'fixtures'/id
  for variant in ('repo','reference'):
   with tempfile.TemporaryDirectory(prefix='codify-fixture-') as temp:
    dst=pathlib.Path(temp);shutil.copytree(base/variant,dst,dirs_exist_ok=True);shutil.copytree(base/'oracle'/'test',dst/'test',dirs_exist_ok=True)
    commands=[[FLUTTER,'pub','get','--offline'],[FLUTTER,'test','test/acceptance_test.dart']]
    if variant=='reference':commands.append([FLUTTER,'analyze','--no-pub'])
    record={'id':id,'variant':variant,'runtime':'host Flutter 3.47.2 / Dart 3.13.2','checks':[]}
    for command in commands:
     p=subprocess.run(command,cwd=dst,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
     record['checks'].append({'command':command[1:],'exit_code':p.returncode,'output':p.stdout[-5000:]})
     if p.returncode and command[1]=='pub':break
    results.append(record);print(id,variant,[(x['command'][0],x['exit_code']) for x in record['checks']],flush=True)
  (base/'evidence.json').write_text(json.dumps([r for r in results if r['id']==id],ensure_ascii=False,indent=2)+'\n')
 return all(r['checks'][0]['exit_code']==0 and (r['checks'][1]['exit_code']!=0 if r['variant']=='repo' else all(x['exit_code']==0 for x in r['checks'])) for r in results)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('operation',choices=['build','verify']);p.add_argument('--ids',nargs='*');a=p.parse_args();ids=a.ids or sorted(CASES)
 if a.operation=='build':build(ids)
 else:raise SystemExit(0 if verify(ids) else 1)
