"""Prospective additive recovery: preserve v1 failure and recheck safe appends.

No source from a frozen control is changed. Same original actors, commitment,
registry and 1200-second clock are retained. No actor dispatch or new grading.
"""
import improvement_optional_deadline_close_v1 as previous

Path, time = previous.Path, previous.time
inputs, aggregate, original = previous.inputs, previous.aggregate, previous.original
identity, capture_family = previous.identity, previous.capture_family
CONTROL, CONTROL_ACTOR = previous.CONTROL, previous.CONTROL_ACTOR
commit = previous.commit


def coordinator_fence(config, proof, committed, committed_parent, committed_sources,
                      captured_parent, current_parent, sources):
    original.require(current_parent.startswith(captured_parent),
                     'Original coordinator prefix replaced or truncated')
    # The already-authenticated family/source proof remains bound to its
    # immutable prefix. Revalidate every actual interruption/latest inventory
    # and deny postcommit allocations or member deliveries on the full append.
    # Ordinary tool outputs and observation calls do not reopen actors.
    return aggregate.verify(config, proof, committed, committed_parent,
                            committed_sources, current_parent, sources)


def close(folder, coordinator_source):
    folder = Path(folder).resolve(); row = identity(folder)
    output = folder / 'deadline-close-v1'
    committed = original.audit.inventory.decoded(original.broker.original(output / 'commitment.json'))
    current = output / 'current-v2'; current.mkdir()
    record = {'software_pass': None, 'owned_cleanup_verified': False, 'status': 'awaiting_terminal_authority',
              'usage': None, 'comparison_admitted': False, 'superiority_proven': False}
    try:
        config, snapshot, proof, parent, sources, locators = capture_family(folder, coordinator_source, current)
        committed_parent = original.broker.original(output / 'coordinator.jsonl')
        committed_sources = {path: original.broker.original(output / ('root.jsonl' if path == row['actor_path']
                             else path.rsplit('/', 1)[-1] + '.jsonl')) for path in committed['member_prefixes']}
        authority = aggregate.verify(config, proof, committed, committed_parent, committed_sources, parent, sources)
        original.atomic_json(current / 'terminal-authority.json', authority, exclusive=True)
        record['usage'] = original.audit.cost.usage_members(proof, sources, locators)
        def fence():
            original.require(all(original.capture(locators[path], 256 * 1024 * 1024) == raw
                                 for path, raw in sources.items()), 'Member appended after interruption authority')
            original.require(aggregate.membership.reservation_prefix(folder / 'registry') == snapshot,
                             'Registry changed after interruption authority')
            coordinator_fence(config, proof, committed, committed_parent, committed_sources,
                              parent, original.capture(coordinator_source, 256 * 1024 * 1024), sources)
            original.require(original.broker.original(folder / 'native-dispatch/configuration.json')
                             == original.broker.original(current / 'dispatch-configuration.json'),
                             'Original dispatch changed after interruption authority')
        fence()
        original.runtime.failure(folder, TimeoutError('Original 1200-second deadline reached'))
        cleaned = original.runtime.cleanup(folder)
        fence()
        record['owned_cleanup_verified'] = bool(cleaned['jobs']) and all(
            job['status'] == 'removed' for job in cleaned['jobs'].values())
        original.require(record['owned_cleanup_verified'], 'Owned deadline preservation/removal incomplete')
        record['status'] = 'preserved_interrupted_failure'
        record['original_started_at'] = config['started_at']
        record['original_deadline'] = config['deadline']
    except BaseException as error:
        record['closure_error'] = {'type': type(error).__name__, 'message': str(error)}
        if 'authority' in locals(): record['status'] = 'closure_incomplete'
    record['finished_at'] = time.time()
    if 'config' in locals(): record['whole_observed_seconds'] = record['finished_at'] - config['started_at']
    original.atomic_json(current / 'outcome.json', record, exclusive=True)
    return record
