"""Pure all-member terminal failure gate without route/integration requirements.

This accepts genuine normally completed actors whose product/protocol failed.
Interrupted/failed API states remain outside this gate. Caller must separately
preserve first errors, authenticate disk ownership and fence live sources and
delivery before any cleanup. This function has no cleanup/admission authority.
"""
import improvement_optional_native_audit_v4 as original


def verify(config, state, root_intent, worker_intents, coordinator_raw,
           root_raw, worker_raw_by_path, provision, registry_folder,
           locators, inventory_call_id, commitment):
    proof = original.membership.reconcile_membership(
        config, state, root_intent, worker_intents, coordinator_raw,
        root_raw, worker_raw_by_path, provision, registry_folder)
    original.require(proof['provided_allocation_joins_complete'],
                     'Unknown cumulative allocation prevents terminal failure closure')
    sources = {proof['root_path']: root_raw, **worker_raw_by_path}
    members = {member['agent_path']: member for member in proof['members']}
    original.require(set(sources) == set(members) == set(locators),
                     'Every actual member source and locator required')
    completions = {}
    for path, member in members.items():
        _, turns = original.inventory.lifecycle.lifecycle(
            sources[path], original.lifecycle_binding(member), 1,
            worker_raw_by_path if path == proof['root_path'] else {})
        completions[path] = turns[0]['completed_at']
    inventory = original.inventory.completed_inventory(
        coordinator_raw, proof['coordinator_native_id'], completions,
        inventory_call_id, commitment, root_raw, worker_raw_by_path)
    usage = original.cost.usage_members(proof, sources, locators)
    return {'membership': proof, 'current_inventory': inventory,
            'completions': completions, 'usage': usage,
            'original_no_more_delivery_commitment': commitment,
            'normal_terminal_failure_gate_pass': True,
            'software_pass': None, 'cleanup_authorized': False,
            'interrupted_branch_qualified': False,
            'comparison_admitted': False, 'superiority_proven': False}
