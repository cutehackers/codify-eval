class Staff {
 final String id,venue,role; final bool active;
 const Staff(this.id,this.venue,this.role,{this.active=true});
}
class Pass {
 final String id,venue; final int validThrough; final bool used;
 const Pass(this.id,this.venue,this.validThrough,{this.used=false});
}
abstract class GateBackend {
 Future<Staff?> staff(String staffId);
 Future<Pass?> pass(String passId);
 // Atomically rechecks current staff active/role/venue, pass venue/expiry/used.
 // Returns entered, denied, expired, used, or missing. Throws on network failure.
 Future<String> enter(String staffId,String passId,String venue,int now);
}
abstract class GateHistory {
 Future<void> append(String venue,String staffId,String passId,int now);
}
class GateDecision {
 final String code; final bool historySaved;
 const GateDecision(this.code,{this.historySaved=true});
}
