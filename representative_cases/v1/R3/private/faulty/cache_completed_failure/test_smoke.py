import unittest
from record_service import RecordService
class Smoke(unittest.IsolatedAsyncioTestCase):
    async def test_single_and_order(self):
        async def loader(key): return key.upper()
        service = RecordService(loader)
        self.assertEqual(await service.get("a"), "A")
        self.assertEqual(await service.get_many(["b", "a"]), ["B", "A"])
        await service.close()
