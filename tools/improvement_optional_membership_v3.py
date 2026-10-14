"""Registry-v4 final-release join to the original complete native allocation audit.

Filesystem namespace ownership and native delivery fences are caller authority.
A lease release never removes reserved, rejected or failed actors from costs.
No actors, containers or cleanup are dispatched by this adapter.
"""
import copy
from pathlib import Path

import improvement_optional_membership_v2 as original
import improvement_optional_registry_v4 as registry
import improvement_optional_checkout_artifacts_v2 as checkout

require = original.require


def reservation_prefix(folder):
    """Snapshot validated v4 events under its lock, including original file pins."""
    folder = Path(folder)
    require(folder.is_dir() and not folder.is_symlink(), 'Original registry directory required')
    require((folder / 'events').is_dir() and not (folder / 'events').is_symlink(),
            'Original events directory required')
    with registry.locked(folder):
        config_pin = checkout.file_pin(folder / 'configuration.json')
        state = registry.read(folder)
        paths = sorted((folder / 'events').iterdir())
        pins = [checkout.file_pin(path) for path in paths]
        events = [registry.strict.decoded(path.read_bytes()) for path in paths]
        require(checkout.file_pin(folder / 'configuration.json') == config_pin
                and all(checkout.file_pin(path) == pin for path, pin in zip(paths, pins)),
                'Registry changed during snapshot')
        full_raw = b''.join(registry.encoded(event) + b'\n' for event in events)
        before = copy.deepcopy(state)
        released = before.pop('integration_release', None)
        if released is not None:
            require(events and events[-1]['operation'] == 'integration_release',
                    'Final release must be last')
            before['event_count'] -= 1
            before['head_sha256'] = events[-1]['previous_sha256']
            before['active_leases'] = {path: slot for slot, row in before['workers'].items()
                                      for path in row['scope']}
            prefix_events = events[:-1]
        else:
            prefix_events = events
        prefix_raw = b''.join(registry.encoded(event) + b'\n' for event in prefix_events)
        original.validate_reservations(state['configuration'], before, prefix_raw)
        return {'state': state, 'reservation_state': before, 'reservation_events_raw': prefix_raw,
                'full_events_raw': full_raw, 'configuration_pin': config_pin,
                'event_pins': pins, 'integration_release': released}


def reconcile_membership(config, registry_state, root_intent, worker_intents,
                         coordinator_raw, product_root_raw, member_raw_by_path,
                         provision_ledger, registry_folder):
    snapshot = reservation_prefix(registry_folder)
    require(registry.encoded(snapshot['state']) == registry.encoded(registry_state)
            and registry.encoded(config) == registry.encoded(registry_state['configuration']),
            'Supplied state/configuration differs from original v4 replay')
    proof = original.reconcile_membership(config, snapshot['reservation_state'], root_intent,
        worker_intents, coordinator_raw, product_root_raw, member_raw_by_path, provision_ledger,
        snapshot['reservation_events_raw'])
    proof.update({'registry_head_sha256': registry_state['head_sha256'],
                  'reservation_registry_head_sha256': snapshot['reservation_state']['head_sha256'],
                  'registry_configuration_pin': snapshot['configuration_pin'],
                  'registry_event_pins': snapshot['event_pins'],
                  'full_registry_events': {'bytes': len(snapshot['full_events_raw']),
                                          'sha256': original.core.digest(snapshot['full_events_raw'])},
                  'final_integration_release': snapshot['integration_release'],
                  'reserved_workers_retained_after_release': True,
                  'registry_namespace_authenticity_qualified': False})
    return proof
