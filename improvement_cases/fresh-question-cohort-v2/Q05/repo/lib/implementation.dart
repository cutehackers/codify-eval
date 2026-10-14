import 'models.dart';
class ReservationService {
  final MemoryStore store;
  final Identity identity;
  ReservationService(this.store, this.identity);
  Outcome reserve(Request request) => throw UnimplementedError();
}
