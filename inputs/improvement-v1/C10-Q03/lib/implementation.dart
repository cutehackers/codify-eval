import 'api.dart';
class RetentionService {
 final JournalDisk disk; final Clock clock;
 RetentionService(this.disk,this.clock);
 Future<RetentionPreview> preview()async=>RetentionPreview({},clock.now());
 Future<int> apply(RetentionPreview preview)async=>0;
}
