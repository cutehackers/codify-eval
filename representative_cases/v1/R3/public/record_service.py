class RecordService:
    def __init__(self, loader):
        self.loader = loader
    @property
    def pending_count(self):
        return 0
    async def get(self, key):
        raise NotImplementedError
    async def get_many(self, keys):
        raise NotImplementedError
    async def close(self):
        raise NotImplementedError
