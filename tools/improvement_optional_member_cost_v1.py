"""Bind whole-session counters to supplied allocation proof prefixes.

This does not authenticate the proof, discover allocations, enforce delivery or
qualify final cost. Unknown attempted slots and unbound sources are preserved.
"""
import hashlib
import re
from pathlib import PurePosixPath

import improvement_optional_usage_v2 as usage
import improvement_optional_inventory_v3 as strict


def usage_members(proof, full_raw_by_path, source_locators):
    require = strict.core.require
    require(isinstance(proof, dict) and isinstance(proof.get('members'), list)
            and isinstance(proof.get('observed_unbound_sources'), list)
            and isinstance(proof.get('pending_allocation_slots'), list), 'Allocation proof rows required')
    members = proof['members']; unbound = proof['observed_unbound_sources']; pending = proof['pending_allocation_slots']
    require(type(proof.get('provided_allocation_joins_complete')) is bool
            and proof['provided_allocation_joins_complete'] == (not pending), 'Allocation unknown state changed')
    root_path = proof.get('root_path')
    require(isinstance(root_path, str) and re.fullmatch('/root/[A-Za-z0-9_]+', root_path), 'Bound root path required')
    rows = []
    for member in members + unbound:
        require(isinstance(member, dict), 'Invalid prefix proof')
        path = member.get('agent_path')
        role = 'root' if path == root_path else (path.removeprefix(root_path + '/') if isinstance(path, str) else None)
        require(role in ('root', 'worker1', 'worker2') and
                path == (root_path if role == 'root' else root_path + '/' + role), 'Unknown allocation role/path')
        if member in unbound:
            require(role in pending, 'Unbound source cannot become reconciled allocation')
        require(member.get('job', role) == role, 'Allocation job/path changed')
        require(isinstance(member.get('native_session_id'), str) and member['native_session_id'], 'Native UUID required')
        rows.append({'agent_path':path, 'native_session_id':member['native_session_id'], 'role':role,
                     'proof':member})
    require(isinstance(full_raw_by_path, dict) and isinstance(source_locators, dict)
            and set(full_raw_by_path) == {r['agent_path'] for r in rows}
            and set(source_locators) == set(full_raw_by_path), 'Every bound and unbound observed prefix required')
    registered = []
    for row in rows:
        path = row['agent_path']; raw = full_raw_by_path[path]; locator = source_locators[path]; pin = row['proof']
        require(isinstance(raw, bytes) and len(raw) == pin.get('raw_bytes')
                and hashlib.sha256(raw).hexdigest() == pin.get('raw_sha256'), 'Allocation/native prefix changed')
        require(isinstance(locator, str) and locator.startswith('/') and
                PurePosixPath(locator).as_posix() == locator and '..' not in PurePosixPath(locator).parts,
                'Exact absolute native source locator required')
        strict.finite(strict.core.parse(raw))
        registered.append({k:row[k] for k in ('agent_path','native_session_id','role')} | {'source':locator})
    value = usage.summarize(registered, full_raw_by_path, pending_slots=pending)
    observed = {k:sum(r['usage'][k] for r in value['members'] if r['usage'] is not None) for k in usage.FIELDS}
    value.update({'allocation_proof_prefixes_matched':True,
                  'known_valid_prefix_category_totals':observed,
                  'known_valid_prefix_totals_are_partial':bool(pending or value['unknown_usage_paths']),
                  'unbound_observed_native_paths':[r['agent_path'] for r in unbound],
                  'membership_authenticity_qualified':False, 'native_qualified':False,
                  'whole_final_cost_qualified':False, 'external_research_cost_included':False,
                  'comparison':False, 'superiority':False})
    return value
