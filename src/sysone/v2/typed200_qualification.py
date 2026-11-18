"""Offline artifact/review completeness gate. Never contacts or authorizes hardware."""
import hashlib
import json
from pathlib import Path

ARTIFACTS = ('recovery', 'typed_dcp', 'a53', 'r5', 'model', 'contract',
             'ps_init', 'fsbl', 'pmu', 'boot_relay', 'fsbl_macros', 'pmu_macros',
             'pm_config', 'typed_bitstream', 'boot_recipe')
PREPARATION = ('boot_memory_map', 'fsbl_handoff', 'pmu_ownership', 'csu_idle',
               'debug_policy', 'power_permissions', 'recovery_procedure', 'physical_checks')
FUNCTIONAL = ('cold_start', 'reset_clock_faults', 'exclusive_access', 'target_numerics',
              'typed_outcomes', 'fresh_session_recovery')
TIMING = ('clock_calibration', 'passive_observation', 'memory_service_bounds',
          'arm_phase_bounds', 'deadline_composition')


def assess_preparation(profile, root):
    """Require hash-bound evidence for each stage; return deficiencies, not authority.

    Review receipts are trusted human/tool conclusions, not cryptographic proof.
    A passing synthetic receipt is not proof that a board ran or was isolated.
    """
    root = Path(root).resolve()
    if profile.get('schema') != 'sysone.typed200.qualification-preparation.v1':
        raise ValueError('Unknown preparation schema')
    if set(profile.get('artifacts', {})) != set(ARTIFACTS):
        raise ValueError('Artifact role set must match the reviewed schema')
    scopes = PREPARATION + FUNCTIONAL + TIMING
    if set(profile.get('reviews', {})) != set(scopes):
        raise ValueError('Review scope set must match the reviewed schema')
    missing, bindings = [], {}

    def verified(item):
        if not isinstance(item, dict) or set(item) != {'path', 'sha256'}:
            return None
        name, digest = item['path'], item['sha256']
        if not isinstance(name, str) or not name or not isinstance(digest, str) or len(digest) != 64:
            return None
        try:
            int(digest, 16)
            p = (root / name).resolve()
            p.relative_to(root)
            with p.open('rb') as f:
                actual = hashlib.file_digest(f, 'sha256').hexdigest()
            return p if actual == digest else None
        except (ValueError, OSError):
            return None

    for role in ARTIFACTS:
        item = profile['artifacts'][role]
        if verified(item) is None:
            missing.append('artifact:' + role)
        else:
            bindings[role] = item['sha256']
    review_ok = {}
    for scope in scopes:
        p = verified(profile['reviews'][scope])
        ok = False
        if p is not None:
            try:
                r = json.loads(p.read_text(encoding='utf-8'))
                if not isinstance(r, dict):
                    raise ValueError('Review must be an object')
                ok = (isinstance(r, dict) and r.get('schema') == 'sysone.typed200.qualification-review.v1'
                      and r.get('scope') == scope and r.get('verdict') == 'pass'
                      and len(bindings) == len(ARTIFACTS)
                      and r.get('artifact_sha256') == bindings
                      and isinstance(r.get('evidence'), list) and len(r['evidence']) > 0
                      and all(verified(e) is not None for e in r['evidence']))
                if scope in FUNCTIONAL + TIMING:
                    ok = ok and r.get('run_id') == profile.get('target_run_id') and bool(r.get('run_id'))
                if scope in TIMING:
                    ok = ok and r.get('instrumentation') == 'reviewed_noninterfering'
            except (ValueError, OSError, TypeError):
                ok = False
        review_ok[scope] = bool(ok)
        if not ok:
            missing.append('review:' + scope)
    prepared = len(bindings) == len(ARTIFACTS) and all(review_ok[k] for k in PREPARATION)
    functional = prepared and all(review_ok[k] for k in FUNCTIONAL)
    timing = functional and all(review_ok[k] for k in TIMING)
    return {'artifact_review_complete': prepared, 'functional_receipts_complete': functional,
            'timing_receipts_complete': timing, 'missing_or_invalid': missing,
            'hardware_action_authorized': False, 'target_execution_verified': False,
            'wcet_certified': False,
            'scope': 'Offline completeness/hash consistency; trusted reviews, no deployment or hardware proof'}
