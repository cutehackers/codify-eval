import 'models.dart';
import 'export_selection.dart';
import 'export_encoding.dart';

Outcome exportTextBundle({required ExportRequest request, required PermissionProvider permissions,
    required DocumentReader reader, required BundleStore store,
    TextBundle? Function(String,List<Document>)? encoder}) {
  if (!permissions.canAccess(request.workspaceId is String ? request.workspaceId as String : '')) return Outcome('forbidden', null);
  if (!validExportRequest(request)) return Outcome('invalid_request', null);
  try {
    final selected = selectDocuments(request, reader);
    if (selected.code != null) return Outcome(selected.code!, null);
    // Normal length/shape failures are invalid requests even with an injected encoder.
    if (selected.documents.any((d) => d.title.length > 80 || d.body.length > 100000)) return Outcome('invalid_request', null);
    final bundle = (encoder ?? encodeTextBundle)(request.workspaceId as String, selected.documents);
    if (bundle == null) return Outcome('invalid_request', null);
    final snapshot = store.load(request.workspaceId as String, request.bundleId as String);
    if (snapshot.revision != request.expectedRevision) return Outcome('conflict', null);
    if (sameBundle(snapshot.bundle,bundle)) return Outcome('unchanged', snapshot.revision,bundle.report);
    if (!store.compareAndReplace(request.workspaceId as String,request.bundleId as String,snapshot.revision,bundle)) return Outcome('conflict',null);
    return Outcome('applied',snapshot.revision+1,bundle.report);
  } catch (_) { return Outcome('storage_failure',null); }
}
