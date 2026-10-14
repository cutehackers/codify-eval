import 'models.dart';
class JourneyService {
 final JourneyApi api;final JourneyCache cache;
 JourneyService(this.api,this.cache);
 Future<JourneyView> load(Rider r,String from,String to,int now)async=>const JourneyView('decision_required');
}
