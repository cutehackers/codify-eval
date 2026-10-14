"""Post-review diagnostic; does not change the frozen representative grader."""
import asyncio
import hashlib
import importlib.util
import json
from pathlib import Path


BASE = Path(__file__).resolve().parents[1]


async def observe(service_type, mode):
    started = asyncio.Event()
    cleaned = asyncio.Event()

    async def loader(key):
        started.set()
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            # Cooperate with shutdown and finish cleanup before returning/raising.
            await asyncio.sleep(0)
            cleaned.set()
            if mode == "return_after_cleanup":
                return "late value"
            raise ValueError("cleanup finished")

    service = service_type(loader)
    waiter = asyncio.create_task(service.get("key"))
    try:
        async with asyncio.timeout(2):
            await started.wait()
            await service.close()
            try:
                value = await waiter
                observed = {"kind": "returned", "value": value}
            except BaseException as error:
                observed = {"kind": "raised", "exception": type(error).__name__}
            return {
                "mode": mode,
                "observed": observed,
                "cleanup_finished": cleaned.is_set(),
                "pending_count": service.pending_count,
                "contract_pass": observed == {
                    "kind": "raised", "exception": "CancelledError"
                } and cleaned.is_set() and service.pending_count == 0,
            }
    finally:
        await service.close()
        if not waiter.done():
            waiter.cancel()
        await asyncio.gather(waiter, return_exceptions=True)


async def main():
    rows = []
    for condition in ("A", "C0", "C24"):
        path = BASE / f"runtime/representative-v1/R3-{condition}-1/repo/record_service.py"
        before = hashlib.sha256(path.read_bytes()).hexdigest()
        spec = importlib.util.spec_from_file_location(f"diagnostic_{condition}", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        for mode in ("return_after_cleanup", "raise_after_cleanup"):
            rows.append({"condition": condition, "source_sha256": before,
                         **await observe(module.RecordService, mode)})
        assert hashlib.sha256(path.read_bytes()).hexdigest() == before
    output = BASE / "results/improvement-v1/representative-R3-close-diagnostic-v1.json"
    report = {
        "schema_version": 1,
        "scope": "Supplementary post-review counterexample, outside frozen72checks",
        "selection": "Independent review noticed different closed checks in original outputs",
        "public_contract": "close waits for cooperative cleanup; waiting gets observe CancelledError",
        "new_model_runs": 0,
        "source_unchanged": True,
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "rows": rows,
        "limits": ["Post-hoc diagnostic, not an independent new cohort",
                   "Cannot establish population or skill-caused superiority"],
    }
    with output.open("x") as file:
        json.dump(report, file, ensure_ascii=False, indent=2)
        file.write("\n")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
