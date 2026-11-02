"""Strict old-three scope for legacy NMG fixtures, with explicit school proof.

These fixtures predate typed-state school business. The current mixed scheduler
and school story remain covered by test_v03_nmg_school_adapter; this helper
never makes an unknown middle arc disappear from a legacy test silently.
"""
import copy
from functools import lru_cache
import json
from pathlib import Path

from tools.v03_inline_delivery_adapter import (validate_inline_catalog, _nmg_school_native_receipt,
                                               _nmg_bay_native_receipt, _nmg_validate_bay_foreign_reply)

ROOT = Path(__file__).resolve().parents[1]
FOUNDATION = ("v03_nmg_land_arbitration", "v03_nmg_bilingual_office", "v03_nmg_autonomy_revenue")
SCHOOL = "v03_nmg_parish_school"
BAY = "v03_nmg_bay_ports"
BAY_JES = ("ywc_je_v03_nmg_bay_charter", "ywc_je_v03_nmg_bay_operations")
JES = ("ywc_je_v03_nmg_parish_school", "ywc_je_v03_nmg_parish_settlement")


@lru_cache(maxsize=1)
def _validated_projection(raw):
    current = json.loads(raw.decode("utf-8-sig"))
    if [a["slug"] for a in current["arcs"]] != [*FOUNDATION, SCHOOL, BAY]:
        raise AssertionError("legacy NMG projection requires exactly the three foundations, school and bay")
    if any(a.get("era") != "foundation" for a in current["arcs"][:3]):
        raise AssertionError("legacy NMG root slugs must retain their foundation era")
    school = current["arcs"][3]
    if school.get("era") != "middle" or [j["id"] for j in school["journals"]] != list(JES):
        raise AssertionError("registered school must retain its ordered two-JE responsibility split")
    if [e["id"] for e in school["events"]] != [f"ywc_nmg.{n}" for n in range(1110, 1118)]:
        raise AssertionError("registered school must retain exactly its eight native events")
    for number, event in enumerate(school["events"], 1):
        if _nmg_school_native_receipt(event) != ("ywc_v03_nmg_v03_nmg_parish_school_last_event", number):
            raise AssertionError("registered school native ordinal receipt changed")
    proof = school["inline_delivery_adapter"]
    if proof["schema"] != "v03.foundation_inline_adapter.v2" or proof["direct_adds"] != []:
        raise AssertionError("registered school requires strict v2 and no direct journal addition")
    if len(proof["branches"]) != 8:
        raise AssertionError("registered school requires eight source-bound sender sites")
    for number, branch in enumerate(proof["branches"], 1110):
        if branch["journal"] != JES[0 if number < 1114 else 1] or branch["event"] != f"ywc_nmg.{number}":
            raise AssertionError("registered school source partition changed")
        if branch["candidates"] != [{"queue": "ywc_nmg_school_pending_event", "kind": "normal",
                                     "mode": "exact", "value": number}]:
            raise AssertionError("registered school private queue changed")
    bay = current["arcs"][4]
    if bay.get("era") != "middle" or [j["id"] for j in bay["journals"]] != list(BAY_JES):
        raise AssertionError("registered bay must retain its ordered two-JE split")
    if [e["id"] for e in bay["events"]] != [f"ywc_nmg.{n}" for n in range(1100, 1109)]:
        raise AssertionError("registered bay must retain its eight local events and foreign reply")
    for number, event in enumerate(bay["events"][:8], 1):
        if _nmg_bay_native_receipt(event) != ("ywc_v03_nmg_v03_nmg_bay_ports_last_event", number):
            raise AssertionError("registered bay native receipt changed")
    _nmg_validate_bay_foreign_reply(bay["events"][8])
    proof = bay["inline_delivery_adapter"]
    if proof["schema"] != "v03.foundation_inline_adapter.v2" or proof["direct_adds"] != [] or len(proof["branches"]) != 8:
        raise AssertionError("registered bay requires strict v2 and eight bound senders")
    for number, branch in enumerate(proof["branches"], 1100):
        if branch["journal"] != BAY_JES[0 if number < 1104 else 1] or branch["event"] != f"ywc_nmg.{number}":
            raise AssertionError("registered bay source partition changed")
        if branch["candidates"] != [{"queue": "ywc_nmg_bay_pending_event", "kind": "normal", "mode": "exact", "value": number}]:
            raise AssertionError("registered bay private queue changed")
    # Validate the whole current document before restricting this fixture's
    # admitted scope. Bad source hashes/unknown arcs cannot hide in projection.
    validate_inline_catalog(current)
    projected = copy.deepcopy(current)
    projected["arcs"] = projected["arcs"][:3]
    return projected


def foundation_catalog():
    return copy.deepcopy(_validated_projection((ROOT / "data/content/v03/countries/nmg.json").read_bytes()))
