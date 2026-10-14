import asyncio

class RecordService:
    def __init__(self, loader):
        self.loader = loader
        self._tasks = {}
        self._closed = False
        self._close_task = None

    @property
    def pending_count(self):
        return sum(not task.done() for task in self._tasks.values())

    async def _load(self, key):
        try:
            return await self.loader(key)
        finally:
            if self._tasks.get(key) is asyncio.current_task():
                self._tasks.pop(key, None)

    async def get(self, key):
        if self._closed:
            raise RuntimeError("service closed")
        task = self._tasks.get(key)
        if task is None:
            task = asyncio.create_task(self._load(key))
            # Consume failures even if every caller abandons the load.
            task.add_done_callback(lambda done: None if done.cancelled() else done.exception())
            self._tasks[key] = task
        return await asyncio.shield(task)

    async def get_many(self, keys):
        if self._closed:
            raise RuntimeError("service closed")
        callers = [asyncio.create_task(self.get(key)) for key in keys]
        try:
            return await asyncio.gather(*callers)
        finally:
            for caller in callers:
                if not caller.done():
                    caller.cancel()
            await asyncio.gather(*callers, return_exceptions=True)

    async def _finish_close(self):
        tasks = list(self._tasks.values())
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        self._tasks.clear()

    async def close(self):
        if self._close_task is None:
            self._closed = True
            self._close_task = asyncio.create_task(self._finish_close())
        await asyncio.shield(self._close_task)
