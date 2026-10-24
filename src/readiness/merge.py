"""Identity resolution across data sources.

VALD calls him "Silva, D.", the wearable calls him "D Silva", the wellness
form calls him "Diego S.". Real teams merge on a roster map, not on hope.
resolve_roster rewrites each Reading's athlete_id/name to the canonical id
so every downstream step sees one athlete. Unmapped readings pass through
unchanged (a new athlete simply isn't in the map yet).
"""

from __future__ import annotations

from .models import Reading


def resolve_roster(readings: list[Reading],
                   roster_map: dict[str, tuple[str, str]]) -> list[Reading]:
    """roster_map: source-name -> (canonical_id, canonical_name)."""
    out: list[Reading] = []
    for r in readings:
        if r.athlete_id in roster_map:
            cid, cname = roster_map[r.athlete_id]
            out.append(r.model_copy(update={"athlete_id": cid, "name": cname}))
        else:
            out.append(r)
    return out
