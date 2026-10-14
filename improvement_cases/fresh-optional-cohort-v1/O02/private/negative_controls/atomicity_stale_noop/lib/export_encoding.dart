import 'dart:convert';
import 'models.dart';

TextBundle? encodeTextBundle(String workspaceId, List<Document> documents) {
  // Validate every record before producing a bundle.
  if (documents.any((d) => !validId(d.id) || d.workspaceId != workspaceId || d.title.length > 80 || d.body.length > 100000)) return null;
  final files = <String,List<int>>{}; final manifestRows = <Map<String,Object>>[]; final report = <Map<String,Object>>[];
  for (final doc in documents) {
    final path = 'documents/${doc.id}.txt'; final bytes = utf8.encode(doc.body);
    files[path] = bytes;
    manifestRows.add({'id':doc.id,'title':doc.title,'path':path,'byteLength':bytes.length});
    report.add({'id':doc.id,'path':path,'byteLength':bytes.length});
  }
  final manifest = utf8.encode('${jsonEncode({'version':1,'workspaceId':workspaceId,'documents':manifestRows})}\n');
  return TextBundle(manifest, files, report);
}
