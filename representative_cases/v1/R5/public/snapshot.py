class ConflictError(ValueError):
    pass

class IntegrityError(ValueError):
    pass

def publish_snapshot(root, snapshot_id, entries):
    raise NotImplementedError
