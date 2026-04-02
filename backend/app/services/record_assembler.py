"""Record assembler: merge per-endpoint transformed outputs into a single Qualys payload.

Pure function with no database access or side effects.  Takes a TraversalRecord
(which accumulates transformed field dicts per canvas-endpoint during tree
traversal) and produces a single flat dict ready for Qualys submission.

Design decisions (from 59-CONTEXT.md):
- D-04: Iterate endpoints in tree order (upstream -> base -> downstream)
- D-05: Multi-record downstream uses first-match (first record's fields win)
- D-06: Pure assembly function, no DB access
"""

from __future__ import annotations

from app.services.fan_out_executor import TraversalRecord


def assemble_qualys_record(
    record: TraversalRecord,
    endpoint_order: list[str],
) -> dict:
    """Merge per-endpoint transformed outputs into a single Qualys payload dict.

    Args:
        record: A TraversalRecord whose ``endpoint_outputs`` maps
            canvas_endpoint_id -> list of transformed field dicts.
        endpoint_order: Ordered list of canvas_endpoint IDs
            (upstream first, then base, then downstream).

    Returns:
        Flat dict of ``{qualys_target_field: value}`` ready for submission.
    """
    merged: dict = {}

    for ep_id in endpoint_order:
        outputs = record.endpoint_outputs.get(ep_id, [])
        if not outputs:
            # Enrichment gap or empty result -- skip gracefully
            continue
        # First-match: always use the first record (D-05)
        merged.update(outputs[0])

    return merged
