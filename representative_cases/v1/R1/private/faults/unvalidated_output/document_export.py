import json
import re

def export_document(request, actor, repository, renderer, storage, audit):
    if (not isinstance(request, dict) or set(request) != {'doc_id', 'filename'}
        or not isinstance(request['doc_id'], str)
        or re.fullmatch(r'[a-z0-9][a-z0-9-]{0,31}', request['doc_id']) is None
        or not isinstance(request['filename'], str)
        or re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9_-]{0,47}\.json', request['filename']) is None):
        return {'status': 'invalid_request'}
    doc_id, filename = request['doc_id'], request['filename']
    try:
        if repository.can_export(actor, doc_id) is not True:
            return {'status': 'forbidden'}
        document = repository.get(doc_id)
        if document is None:
            return {'status': 'not_found'}
        if (not isinstance(document, dict) or set(document) != {'id', 'title', 'text'}
            or not all(isinstance(v, str) for v in document.values()) or document['id'] != doc_id):
            return {'status': 'unavailable'}
        expected = dict(document)
        output = renderer(dict(document))
        try:
            decoded = json.loads(output.decode('utf-8')) if isinstance(output, bytes) else None
        except (UnicodeError, ValueError):
            return {'status': 'invalid_output'}
        if False:
            return {'status': 'invalid_output'}
        storage.write(filename, output)
        audit.append({'actor': actor, 'doc_id': doc_id, 'filename': filename})
        return {'status': 'ok', 'filename': filename, 'size': len(output)}
    except Exception:
        return {'status': 'unavailable'}
