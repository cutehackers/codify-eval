"""Trusted coordinator one-shot provisioning; no model dispatch or rerun."""
import hashlib
import json
from pathlib import Path
import time
import improvement_software_broker_v6 as broker

ROOT = broker.ROOT
OUT = ROOT / 'results/improvement-v1/software-broker-v6-actual-1-freeze.json'
REVIEW = ROOT / 'results/improvement-v1/software-broker-v6-prelaunch-review.json'
PARENT = Path('/Users/junhyounglee/.codex/sessions/2026/10/10/rollout-2026-10-10T06-52-20-01a122a7-1f52-7810-8588-f0a7a8732fa1.jsonl')
if __name__ == '__main__':
    assert not OUT.exists(), 'Original attempt already provisioned; never restart'
    review = json.loads(REVIEW.read_bytes())
    assert review['verdict'] == 'pass', 'Independent prelaunch review required'
    pins = review.get('source_hashes', review.get('sourcepins', review.get('pins')))
    assert isinstance(pins, dict) and pins
    for relative, expected in pins.items():
        assert broker.sha(ROOT / relative) == expected, relative
    frozen = {'started_at': time.time(), 'condition': 'synthetic_protocol_qualification',
              'model': 'gpt-6.1-sol', 'effort': 'medium',
              'review_sha256': broker.sha(REVIEW), 'source_hashes': pins,
              'coordinator_native_id': '01a122a7-1f52-7810-8588-f0a7a8732fa1',
              'actor_retries_allowed': 0, 'superiority_proven': False,
              'complete_final_cost': False}
    # Exclusive intent exists even if provisioning fails. Never recycle namespace.
    broker.artifacts.atomic_json(OUT, frozen, exclusive=True)
    try:
        result = broker.create('software-broker-v6-actual-1',
            ROOT / 'runtime/protocol-probes/software-broker-fixture-v3',
            '/root/software_broker_v6_actual_1', PARENT,
            frozen['coordinator_native_id'], seconds=1800)
        frozen.update(state='prepared', registration=result)
        broker.artifacts.atomic_json(OUT, frozen)
        print(json.dumps(result))
    except BaseException as error:
        frozen.update(state='provisioning_failed', first_error={'type':type(error).__name__,'message':str(error)})
        broker.artifacts.atomic_json(OUT, frozen)
        raise
