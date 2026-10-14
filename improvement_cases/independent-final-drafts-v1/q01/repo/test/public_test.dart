import 'package:test/test.dart';
import 'package:quota_fixture/models.dart';
import 'package:quota_fixture/implementation.dart';
void main() {
  for (final policy in ShortagePolicy.values) {
    test('under capacity example ${policy.name}', () {
      final s=MemoryLedgerStore(LedgerState('t',10,4,{'alice':2}));
      final r=AllocationService(s,policy:policy).allocate(const RequestContext('t','owner'),Batch('b1','t',4,[const Allocation('alice',3),const Allocation('bob',2)]));
      expect(r.granted,{'alice':3,'bob':2});expect(r.revision,5);
      expect(s.state.allocations,{'alice':5,'bob':2});expect(s.state.remaining,3);
    });
  }
  test('invalid duplicate is atomic', () {
    final s=MemoryLedgerStore(LedgerState('t',10,0,{}));
    expect(()=>AllocationService(s,policy:ShortagePolicy.atomic).allocate(const RequestContext('t','a'),Batch('x','t',0,[const Allocation('m',1),const Allocation('m',1)])),throwsA(isA<AllocationException>().having((e)=>e.code,'code','invalid')));
    expect(s.state.revision,0);
  });
  test('denied context never allocates', () {
    final s=MemoryLedgerStore(LedgerState('t',10,0,{}));
    expect(()=>AllocationService(s,policy:ShortagePolicy.partial).allocate(const RequestContext('t','a',canAllocate:false),Batch('x','t',0,[const Allocation('m',1)])),throwsA(isA<AllocationException>().having((e)=>e.code,'code','forbidden')));
    expect(s.state.allocations,isEmpty);
  });
}
