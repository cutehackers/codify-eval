import 'package:test/test.dart';
import 'package:b02/models.dart';
import 'package:b02/pass_parser.dart';
import 'package:b02/gate_service.dart';
import 'package:b02/labels.dart';
class Backend implements GateBackend {
 Staff? current=const Staff('s','v','gate'); Pass? ticket=const Pass('p','v',100);
 String result='entered',fail=''; final List<String> calls=[]; List<Object>? args;
 Future<Staff?> staff(String id) async {calls.add('staff');if(fail=='staff')throw StateError('secret');return current;}
 Future<Pass?> pass(String id) async {calls.add('pass');if(fail=='pass')throw StateError('secret');return ticket;}
 Future<String> enter(String s,String p,String v,int n) async {calls.add('enter');args=[s,p,v,n];if(fail=='enter')throw StateError('secret');return result;}
}
class History implements GateHistory {
 bool fail=false; final List<List<Object>> rows=[];
 Future<void> append(String v,String s,String p,int n) async { if(fail)throw StateError('secret');rows.add([v,s,p,n]); }
}
const session=Staff('s','v','admin');
void main(){
 test('r1 malformed QR has no side effects',()async{
  for(final raw in ['museum-pass:','museum-pass:'+('a'*97),'museum-pass:a%2Fb','museum-pass:a/b','museum-pass:a?x=1','museum-pass:a b','museum-pass:a\n','http:p']){
   final b=Backend(); final h=History();expect(parsePass(raw),null);expect((await GateService(b,h).scan(raw,session,99)).code,'invalid');expect(b.calls,isEmpty);expect(h.rows,isEmpty);
  }
 });
 test('r2 current staff controls authorization before pass lookup',()async{
  for(final staff in <Staff?>[null,const Staff('s','v','gate',active:false),const Staff('s','v','viewer'),const Staff('s','other','gate')]){
   final b=Backend()..current=staff;final h=History();expect((await GateService(b,h).scan('museum-pass:p',session,99)).code,'denied');expect(b.calls,['staff']);expect(h.rows,isEmpty);
  }
  final b=Backend()..fail='staff';expect((await GateService(b,History()).scan('museum-pass:p',session,99)).code,'unavailable');expect(b.calls,['staff']);
 });
 test('r3 venue expiry and replay precedence',()async{
  final scenarios=<Pass?,String>{null:'missing',const Pass('p','other',0,used:true):'denied',const Pass('p','v',98,used:true):'expired',const Pass('p','v',99,used:true):'used'};
  for(final e in scenarios.entries){final b=Backend()..ticket=e.key; final h=History();expect((await GateService(b,h).scan('museum-pass:p',session,99)).code,e.value);expect(b.calls,['staff','pass']);expect(h.rows,isEmpty);}
  final b=Backend()..ticket=const Pass('p','v',99);expect((await GateService(b,History()).scan('museum-pass:p',session,99)).code,'entered');
 });
 test('r4 authoritative atomic response and typed failure',()async{
  for(final code in ['denied','used','expired','missing','internal stack token']){
   final b=Backend()..result=code;final h=History(); final d=await GateService(b,h).scan('museum-pass:p',session,99);
   expect(d.code,code=='internal stack token'?'unavailable':code);expect(b.args,['s','p','v',99]);expect(h.rows,isEmpty);
  }
  for(final fail in ['pass','enter']){final b=Backend()..fail=fail;expect((await GateService(b,History()).scan('museum-pass:p',session,99)).code,'unavailable');}
 });
 test('r5 successful remote entry survives local storage failure',()async{
  final b=Backend();final h=History();expect((await GateService(b,h).scan('museum-pass:p',session,99)).historySaved,true);expect(h.rows,[['v','s','p',99]]);
  h.fail=true; final d=await GateService(b,h).scan('museum-pass:p',session,99);expect(d.code,'entered');expect(d.historySaved,false);expect(gateLabel(d),'입장 완료 · 기기 기록 저장 실패');
 });
 test('r6 fixed public labels redact unknown diagnostics',(){
  const labels={'invalid':'입장권을 다시 스캔하세요.','denied':'이 입장권을 처리할 권한이 없습니다.','expired':'입장 시간이 지났습니다.','used':'이미 사용한 입장권입니다.','missing':'입장권을 찾을 수 없습니다.','unavailable':'연결을 확인하고 다시 시도하세요.'};
  for(final e in labels.entries)expect(gateLabel(GateDecision(e.key)),e.value);
  expect(gateLabel(const GateDecision('token=private')) ,labels['unavailable']);
 });
}
