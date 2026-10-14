import 'models.dart';
class GateService {
 final GateBackend backend; final GateHistory history;
 GateService(this.backend,this.history);
 Future<GateDecision> scan(String raw,Staff session,int now) async => const GateDecision('unavailable');
}
