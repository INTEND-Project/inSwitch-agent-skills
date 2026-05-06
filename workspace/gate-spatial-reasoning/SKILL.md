---
name: gate-spatial-reasoning
description: Resolve natural-language spatial references (e.g. "south approach", "west exit", "the crosswalk near the metro") into the canonical zone identifiers used by the Sofia intersection LiDAR pipeline. Use when a user intent involves zones but does not name them explicitly.
---

# GATE Spatial Reasoning

This skill maps human spatial language to the canonical zone identifiers of the Sofia intersection (Cherni Vruh × Sreburna), as defined in `sofia_intersection_zones.yaml`.

## When to use

Invoke this skill whenever a deployment intent references zones implicitly through:

- Cardinal directions ("south approach", "from the north", "westbound")
- Functional roles ("the crosswalk", "the bus bay", "the intersection center")
- Movement patterns ("turn left from south to west", "cross from C5 to the island")

Do NOT invoke this skill if the user already provides canonical zone IDs (e.g. `L12_s_e`, `C5_w`).

## Input

A free-text description of one or more spatial roles. Example inputs:

- "south approach toward the west exit"
- "the western crosswalk and its two approach lanes"
- "vehicles entering the intersection from the east"

## Output

Always return a single JSON object with this shape:

```json
{
  "resolved": {
    "FROM_ZONE": "L12_s_e",
    "TO_ZONE": "C5_w"
  },
  "alternatives": {
    "FROM_ZONE": ["L13_s_n", "L14_s_n"],
    "TO_ZONE": ["L7_e_w", "L21_ne_w"]
  },
  "rationale": "Most likely interpretation: a left turn from L12_s_e (south-incoming, canonical exit east) ending at C5_w (western crosswalk). Alternatives are listed in descending plausibility."
}
```

The `resolved` field MUST contain the single most plausible mapping. The `alternatives` field is for cases where multiple interpretations are reasonable; cap each list at 3 items.

When ranking candidates:
- For wrong-turn candidates, prefer lanes whose canonical exit direction is most cardinally opposite to the wrong-turn destination, using the `opposite()` table in "Wrong-turn detection logic" (a wrong left turn to west is more telling from a "go-east" lane than from a "go-north" straight lane).
- Prefer crosswalks over traversing lanes when the user says "exit" — a crosswalk is a physical edge of the intersection.
- Prefer the lowest-numbered zone when truly tied (deterministic tiebreak).

If a role is genuinely unresolvable, return `{"error": "<role> could not be resolved", "available_zones": [...]}` instead of guessing.

## Path resolution

The agent's working directory is already `/workspace/gate-spatial-reasoning/`. When reading files, use BARE filenames (e.g. `sofia_intersection_zones.yaml`), NOT paths prefixed with `gate-spatial-reasoning/`. Do not prepend the skill folder name to file paths.

## Reasoning steps (FOLLOW EXACTLY)

1. Load `sofia_intersection_zones.yaml` from the same directory as this skill.
2. Parse the user spatial description into roles. Common roles: `from_zone`, `to_zone`, `crosswalk`, `safety_zone`, `approach_zones`.
3. For each role, filter the zone catalogue using the rules below.
4. If exactly one zone matches, return it. If several match, return all candidates with a one-line rationale.
5. If no zone matches, return `{"error": "<role> could not be resolved", "available_zones": [...]}` listing zones of the most plausible type.
6. Do NOT invent zone IDs. Only return values present in the YAML.

## Anti-hallucination rules

Only use geometric and relational attributes that are explicitly encoded as fields in `sofia_intersection_zones.yaml`.

- MUST NOT invent geometric, ordinal, or relative-position attributes such as left/right, east-of, west-of, north-of, south-of, first/second from a side, inner/outer, near/far, north-east/north-west sub-position, or "eastern of two" unless that distinction is directly derivable from YAML fields.
- Same-side zones with the same type are peers unless the YAML gives an explicit distinguishing field or link. For example, `C1_n` and `C2_n` are both north crosswalks; the YAML does not encode which is eastern, western, first, second, left, or right.
- If the user provides a disambiguator that is not derivable from the YAML:
  1. State explicitly in `rationale` that the requested distinction is not encoded in the data.
  2. Apply the documented deterministic tiebreak: choose the lowest-numbered matching zone.
  3. List remaining same-side candidate zones under `alternatives` for that role, capped at 3.
- Do not convert an unsupported disambiguator into a fabricated label. For "north crosswalk, but the eastern of the two", resolve `C1_n` by deterministic tiebreak and list `C2_n` as an alternative; do not describe `C1_n` as north-west or `C2_n` as north-east.

## Naming conventions (from the YAML)

- Lanes: `L<id>_<from_side>_<to_sides>` — e.g. `L12_s_e` = lane #12, from south, to east.
- Crosswalks: `C<id>_<side>` — e.g. `C5_w` = crosswalk #5, west side.
- Subway exits: `SE<id>_<side>`. Islands: `IS<id>_<side>`. Bus bay: `BB<id>_<side>`.
- Side codes: `n` north, `s` south, `e` east, `w` west, `ne` north-east, `all` any approach.
- Compound `to_sides`: a multi-letter suffix is a list of permitted exits without separator. `L1_n_ws` = from north, may exit west or south.

## Filtering rules per role

**from_zone / "approach" / "incoming"**

- Type must be `lane`.
- `from_side` must match the cardinal direction in the intent.

**to_zone / "exit" / "outgoing" / "destination"**

- Type can be `lane` (canonical outgoing lane: `L<id>_all_<side>`) or `crosswalk` if the intent mentions pedestrians or zebra crossings.
- For "exit toward <side>" or "destination on <side>", a candidate lane must satisfy `<side>` in `exit_sides` or `exit_side`. The lane's `from_approach` is irrelevant for exit/destination semantics.
- NEVER include a lane whose `from_approach` matches the destination side unless that same side is also explicitly present in its `exit_sides` or `exit_side`.
- For lanes, match the destination side against `exit_sides` or `exit_side`. For crosswalks, match against `side`.
- Prefer crosswalks over traversing lanes when the user says "exit" — a crosswalk is a physical edge of the intersection.
- For movement-pattern intents (FROM_ZONE and TO_ZONE both requested), the resolved TO_ZONE MUST NOT equal the resolved FROM_ZONE, and the TO_ZONE alternatives list MUST NOT include the FROM_ZONE or any zone present in the FROM_ZONE alternatives. A transition where FROM == TO is degenerate and must be rejected.
- Enumerate TO_ZONE candidates by scanning the FULL zone catalogue, not by starting from the FROM_ZONE candidate set or filtering by from_approach. The TO_ZONE filter is a property of the candidate zone alone (its exit_sides for lanes, side for crosswalks), independent of which lane was chosen as FROM_ZONE.
- If after applying all filters and the FROM/TO disjointness rule the TO_ZONE candidate set is empty, return `{"error": "TO_ZONE could not be resolved", "available_zones": [...]}` instead of falling back to the FROM_ZONE.
- Worked example: `L18_w_es` has `from_approach=w` but `exit_sides=[e,s]`. It is a valid `TO_ZONE` for east-bound movements (`e` in `exit_sides`) and south-bound movements (`s` in `exit_sides`), NOT for west-bound movements (`w` not in `exit_sides`). `L19_w_e` has `from_approach=w` and `exit_side=e`, so it is also valid for east-bound movements, NOT for west-bound movements.
- Worked example for "east to west through movement":
  - FROM candidates (lanes with from_approach=e and w in exit_sides): L7_e_w (exit_side=w), L8_e_sw (exit_sides=[s,w]).
  - TO candidates: scan the full catalogue for any lane with w in exit_sides or exit_side, then exclude any zone present in the FROM candidate set. Raw matches: L1_n_ws, L7_e_w, L8_e_sw, L21_ne_w, L22_ne_w. After excluding FROM candidates: L1_n_ws, L21_ne_w, L22_ne_w. L18_w_es and L19_w_e are excluded because they have from_approach=w without w in their exit_sides.
  - Resolve FROM_ZONE = L7_e_w (lowest numbered), TO_ZONE = L1_n_ws (lowest numbered).
  - alternatives.FROM_ZONE = [L8_e_sw], alternatives.TO_ZONE = [L21_ne_w, L22_ne_w].

**crosswalk**

- Type must be `crosswalk`.
- If a side is mentioned, `side` must match.

**safety_zone**

- The YAML lists explicit safety zones (prefix `S_`) linked to crosswalks. Match by linked crosswalk.

**approach_zones (plural, for crosswalk safety)**

- All lane zones whose `to_sides` includes the crosswalk's side, OR explicitly linked in the YAML.

## Ranking rules for legal movements (FROM -> TO)

When the requested movement is legal (destination side is in the source lane's `exit_sides`), rank candidates as follows.

For FROM_ZONE:
- PRIMARY rank: lanes whose normalized `exit_sides` has a single element exactly equal to the destination side (single-purpose lane for this movement).
- SECONDARY rank: lanes whose `exit_sides` includes the destination side among others (multi-purpose lane).
- Within ties, lowest-numbered zone wins.

For TO_ZONE:
- PRIMARY rank: canonical outgoing lanes named `L<id>_all_<side>` matching the destination side. These are by construction the destinations of any legal movement toward `<side>`.
- SECONDARY rank: any other lane with the destination side in its `exit_sides` (typically incoming lanes from another approach that also exit toward this side).
- TERTIARY rank: crosswalks on the destination side (only if the intent mentions pedestrians or "exit").
- Within ties, lowest-numbered zone wins.
- Apply the FROM/TO disjointness rule defined in the `to_zone` filtering section.

## Wrong-turn detection logic

A "wrong turn" intent is structurally defined as: a movement whose destination side is not in the source lane's `exit_sides`.

Use this explicit cardinal opposite table when ranking wrong-turn candidates:

- `opposite(n) = s`
- `opposite(s) = n`
- `opposite(e) = w`
- `opposite(w) = e`
- `opposite(ne) = sw` (compound: opposite of `n` plus opposite of `e`)

Resolution procedure:
1. From the cardinal direction in the source description, list all `lane` zones with matching `from_approach`.
2. For each candidate, read `exit_sides`; if the YAML uses singular `exit_side`, treat it as a one-item `exit_sides` list. The destination side from the user intent must NOT be in that normalized list (otherwise it's a legal turn, not a wrong turn).
3. Among remaining candidates, RANK them:
   - PRIMARY rank: candidates whose `exit_sides` is most cardinally opposite to the wrong destination: the normalized `exit_sides` list contains `opposite(wrong_destination)`. Within this group, lanes with a single `exit_side` exactly equal to `opposite(wrong_destination)` outrank lanes with multiple `exit_sides` that include `opposite(wrong_destination)`.
   - SECONDARY rank: candidates whose `exit_sides` is perpendicular to `wrong_destination`.
   - Within ties, lowest-numbered zone wins.
4. Return the top-ranked candidate as `resolved.FROM_ZONE`. List the others under `alternatives.FROM_ZONE`, capped at 3.

Worked example for "wrong U-turn from north back to north":

- Source side is `n`; wrong destination is `n`; `opposite(n) = s`.
- North incoming candidates whose legal exits do not include `n`: `L1_n_ws` (`exit_sides=[w,s]`), `L2_n_s` (`exit_side=s`), and `L3_n_e` (`exit_side=e`).
- Rank `L2_n_s` highest because it has a single `exit_side=s`, the strict opposite of `n`.
- Rank `L1_n_ws` next because it includes `s` but also includes `w`.
- Rank `L3_n_e` after those because `e` is perpendicular to `n`.
- Therefore resolve `FROM_ZONE` to `L2_n_s` and list `L1_n_ws`, then `L3_n_e`, in `alternatives.FROM_ZONE`.

## Output format

Always return a single JSON object. No prose around it. The orchestrator will parse it.
