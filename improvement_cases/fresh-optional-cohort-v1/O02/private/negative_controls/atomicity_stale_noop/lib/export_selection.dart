import 'models.dart';

bool validExportRequest(ExportRequest request) => validId(request.workspaceId) && validId(request.bundleId) &&
    validRevision(request.expectedRevision) && request.ids.isNotEmpty && request.ids.length <= 100 &&
    request.ids.every(validId) && request.ids.toSet().length == request.ids.length;
Selection selectDocuments(ExportRequest request, DocumentReader reader) {
  final docs = <Document>[];
  for (final id in request.ids) {
    final doc = reader.read(request.workspaceId as String, id as String);
    if (doc == null) return Selection('not_found', []);
    if (doc.workspaceId != request.workspaceId || doc.id != id) return Selection('forbidden', []);
    docs.add(doc);
  }
  return Selection(null, docs);
}
