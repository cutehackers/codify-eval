class ConflictError(ValueError):
    pass

class Outbox:
    def __init__(self, path):
        raise NotImplementedError
    def enqueue(self, tenant, key, payload):
        raise NotImplementedError
    def claim(self, tenant, now, lease_seconds, limit):
        raise NotImplementedError
    def complete(self, tenant, message_id):
        raise NotImplementedError
    def retry(self, tenant, message_id, available_at):
        raise NotImplementedError
    def close(self):
        raise NotImplementedError
