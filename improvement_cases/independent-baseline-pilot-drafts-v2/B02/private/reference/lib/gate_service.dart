import 'models.dart';
import 'pass_parser.dart';
class GateService {
 final GateBackend backend; final GateHistory history;
 GateService(this.backend,this.history);
 Future<GateDecision> scan(String raw,Staff session,int now) async {
  final id=parsePass(raw); if(id==null) return const GateDecision('invalid');
  try {
   final fresh=await backend.staff(session.id);
   if(fresh==null || !fresh.active || fresh.role!='gate' || fresh.venue!=session.venue) return const GateDecision('denied');
   final pass=await backend.pass(id);
   if(pass==null) return const GateDecision('missing');
   if(pass.venue!=fresh.venue) return const GateDecision('denied');
   if(pass.validThrough<now) return const GateDecision('expired');
   if(pass.used) return const GateDecision('used');
   final code=await backend.enter(fresh.id,id,fresh.venue,now);
   if(!{'entered','denied','expired','used','missing'}.contains(code)) return const GateDecision('unavailable');
   if(code!='entered') return GateDecision(code);
   try { await history.append(fresh.venue,fresh.id,id,now); }
   catch (_) { return const GateDecision('entered',historySaved:false); }
   return const GateDecision('entered');
  } catch (_) { return const GateDecision('unavailable'); }
 }
}
