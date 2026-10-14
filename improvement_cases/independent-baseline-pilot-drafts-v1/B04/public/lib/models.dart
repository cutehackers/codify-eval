class Rider {
 final String id,region; final bool active,wheelchair;
 const Rider(this.id,this.region,{this.active=true,this.wheelchair=false});
}
class Leg {
 final String line; final int minutes; final bool accessible,cancelled;
 const Leg(this.line,this.minutes,{this.accessible=true,this.cancelled=false});
}
class Journey {
 final String riderId,region,origin,destination; final int fetchedAt; final List<Leg> legs;
 Journey(this.riderId,this.region,this.origin,this.destination,this.fetchedAt,List<Leg> legs):legs=List.unmodifiable(legs);
}
abstract class JourneyApi {
 Future<Journey> fetch(Rider rider,String origin,String destination);
}
abstract class JourneyCache {
 Future<String?> read(String key);
 Future<void> write(String key,String json);
}
class JourneyView {
 final String code; final Journey? journey; final bool persisted;
 const JourneyView(this.code,{this.journey,this.persisted=true});
}
