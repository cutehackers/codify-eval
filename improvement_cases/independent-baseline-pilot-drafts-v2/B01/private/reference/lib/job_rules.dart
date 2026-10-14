import 'models.dart';
bool validJob(Job j) => j.id.trim().isNotEmpty && j.tenant.trim().isNotEmpty &&
    RegExp(r'^EQ-[0-9]{4}$').hasMatch(j.asset) && j.revision > 0 &&
    j.note.trim().isNotEmpty && j.note.length <= 240 &&
    !j.note.contains(RegExp(r'[\x00-\x08\x0B\x0C\x0E-\x1F]'));
String deliveryKey(Job j) => '${Uri.encodeComponent(j.tenant)}/${Uri.encodeComponent(j.id)}/${j.revision}';
