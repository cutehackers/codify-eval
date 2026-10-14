import 'package:flutter_test/flutter_test.dart';
import 'package:fixture_app/api.dart';
import 'package:fixture_app/implementation.dart';
class Fixed implements Clock {int calls=0;DateTime value=DateTime.utc(2026,10,11,12);DateTime now(){calls++;return value;}}
class Disk implements JournalDisk {
 List<JournalRecord> rows=[]; int reads=0,deletes=0; Set<String>? removed;bool fail=false;bool readFail=false;
 Future<List<JournalRecord>> readAll()async {reads++;if(readFail)throw StateError("read failure");return rows;}
 Future<void> deleteIds(Set<String> ids)async {deletes++;if(fail)throw StateError('atomic failure');removed=Set.of(ids);}
}
void main(){
 test('registered policy eligibility boundary and UTC instants',()async{
  final c=Fixed();final d=Disk();final cutoff=c.value.subtract(const Duration(days:30));
  d.rows=[JournalRecord('old',cutoff.subtract(const Duration(microseconds:1)),completed:true),JournalRecord('edge',cutoff,completed:true),JournalRecord('recent',cutoff.add(const Duration(microseconds:1)),completed:true),JournalRecord('pending',DateTime.utc(2000),completed:false),JournalRecord('future',c.value.add(const Duration(days:1)),completed:true),JournalRecord('offset',DateTime.parse('2026-09-11T20:59:59+09:00'),completed:true),JournalRecord('old',DateTime.utc(2000),completed:true)];
  final p=await RetentionService(d,c).preview();expect(p.ids,{'old','offset'});expect(p.evaluatedAt,c.value);expect(p.evaluatedAt.isUtc,true);expect(c.calls,1);expect(d.deletes,0);expect(()=>p.ids.add('x'),throwsUnsupportedError);
 });
 test('apply respects frozen preview and does not reevaluate',()async{
  final c=Fixed();final d=Disk()..rows=[JournalRecord('old',DateTime.utc(2000),completed:true)];final s=RetentionService(d,c);final p=await s.preview();
  d.rows=[JournalRecord('new',DateTime.utc(1999),completed:true)];c.value=DateTime.utc(2030);expect(await s.apply(p),1);expect(d.removed,{'old'});expect(d.deletes,1);expect(d.reads,1);expect(c.calls,1);
 });
 test('empty preview avoids disk and deletion failure propagates',()async{
  final d=Disk();final s=RetentionService(d,Fixed());expect(await s.apply(RetentionPreview({},DateTime.utc(2026))),0);expect(d.deletes,0);expect(d.reads,0);
  d.fail=true;await expectLater(s.apply(RetentionPreview({'a','b'},DateTime.utc(2026))),throwsStateError);expect(d.deletes,1);expect(d.removed,isNull);
 });
 test('local supplied clock becomes UTC and read errors propagate with recovery',()async{
  final c=Fixed()..value=DateTime(2026,10,11,12);final d=Disk()..readFail=true;final s=RetentionService(d,c);
  await expectLater(s.preview(),throwsStateError);expect(d.deletes,0);d.readFail=false;d.rows=[JournalRecord('old',c.value.subtract(const Duration(days:31)),completed:true)];
  final p=await s.preview();expect(p.evaluatedAt,c.value.toUtc());expect(p.evaluatedAt.isUtc,true);expect(p.ids,{'old'});expect(d.deletes,0);
 });
 test('failed apply can be retried without rereading or reporting early success',()async{
  final c=Fixed();final d=Disk()..fail=true;final s=RetentionService(d,c);final p=RetentionPreview({'a','b'},DateTime.utc(2026));
  await expectLater(s.apply(p),throwsStateError);expect(d.removed,isNull);expect(d.reads,0);expect(c.calls,0);
  d.fail=false;expect(await s.apply(p),2);expect(d.removed,{'a','b'});expect(d.deletes,2);expect(d.reads,0);expect(c.calls,0);
 });

}
