"""Export one real Victoria 3 save's checkpoint rows for the ten core countries.

Gate 4 needs ten countries x three years x fifteen runs of measured data.  The
release gate rejects invented evidence, so this tool does not accept numbers
from the operator: it reads them out of a save the game itself wrote, and it
refuses rather than guesses whenever a field is missing.

What it derives, and from where in the save:

===================  ==========================================================
``rank``             ``country_rankings.country_rankings`` entry for the country
``population``       ``country_manager`` -> country -> ``pop_statistics``
                     (lower + middle + upper strata, i.e. the country panel's
                     own figure), cross-checked against the sum of
                     ``pops.database`` workforce + dependents per owned state
``market``           the tag of the country that owns the market this country
                     belongs to (``market_manager.database`` -> ``owner``)
``wars``             ongoing ``war_manager`` wars the country participates in
``subjects``         subject-type pacts where the country is the overlord
``error_count``      line count of the run's ``error.log``
===================  ==========================================================

The output is a JSON document with a full provenance block (save path, size,
sha256, in-game date, game version, mounted mods) plus rows, or a CSV the
existing ``record_checkpoint.py`` accepts directly::

    python tools/save_checkpoint_export.py --save <autosave.v3> ^
        --game-root '<...>/Victoria 3/game' ^
        --error-log <userdir>/logs/error.log ^
        --config none --seed 11 --output 1846.csv

``--year`` may be supplied to assert the checkpoint year; the tool never
rewrites a save's own date to match it.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.summarize_observation import (  # noqa: E402
    CHECKPOINT_YEARS,
    CORE_COUNTRIES,
)

# 0xFFFFFFFF marks "no country" in a save; it must never be reported as one.
NO_COUNTRY = 4294967295
# A war without a peace date is still being fought: the save writes 1.1.1.
ONGOING_WAR_PEACE_DATE = "1.1.1"
# The two population methods disagree only by pop-accounting rounding in
# practice (below 0.01% on a real 1836 save); a larger gap means a section was
# misread, so it is reported instead of being averaged away.
POPULATION_TOLERANCE = 0.005

# `^}` at column zero closes a database entry; nested blocks are indented.
ENTRY = re.compile(r"^([0-9]+)=\{\n(.*?)^\}", re.S | re.M)
CSV_COLUMNS = ("year", "country", "rank", "population", "market", "wars", "subjects", "error_count")


class SaveExportError(Exception):
    """Raised when a save cannot produce trustworthy checkpoint rows."""


def _scalar(body: str, key: str) -> str | None:
    """Read a depth-1 scalar of a database entry body."""

    match = re.search(rf"(?m)^\t{re.escape(key)}=(.*)$", body)
    if match is None:
        return None
    return match.group(1).strip()


def _integer(body: str, key: str) -> int | None:
    value = _scalar(body, key)
    if value is None or not value.lstrip("-").isdigit():
        return None
    return int(value)


def _block(body: str, key: str) -> str | None:
    """Return the matching-brace contents of a depth-1 ``key={...}`` block."""

    match = re.search(rf"(?m)^\t{re.escape(key)}=\{{", body)
    if match is None:
        return None
    opening = body.index("{", match.start())
    depth = 0
    index = opening
    while index < len(body):
        char = body[index]
        if char == '"':
            index = body.find('"', index + 1)
            if index == -1:
                return None
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return body[opening + 1 : index]
        index += 1
    return None


class PdxSave:
    """Minimal reader for the subset of a Victoria 3 save the export needs."""

    def __init__(self, path: Path) -> None:
        self.path = path
        if not path.is_file():
            raise SaveExportError(f"save does not exist: {path}")
        self.text = path.read_text("utf-8", errors="replace")

    # -- sections -----------------------------------------------------------

    def section(self, name: str) -> str:
        """Body of a top-level ``name={...}`` section."""

        start = self.text.find(f"\n{name}={{")
        if start == -1:
            raise SaveExportError(f"{self.path}: no top-level section {name!r}")
        opening = self.text.index("{", start)
        depth = 0
        index = opening
        while index < len(self.text):
            char = self.text[index]
            if char == '"':
                index = self.text.find('"', index + 1)
                if index == -1:
                    break
            elif char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    return self.text[opening + 1 : index]
            index += 1
        raise SaveExportError(f"{self.path}: unbalanced braces in section {name!r}")

    def database(self, section_name: str) -> dict[int, str]:
        """``<id>={...}`` entries of a section's ``database={...}`` child."""

        body = self.section(section_name)
        start = body.find("database={")
        if start == -1:
            raise SaveExportError(f"{self.path}: section {section_name!r} has no database block")
        return {int(key): entry for key, entry in ENTRY.findall(body[start:])}

    # -- metadata -----------------------------------------------------------

    def meta_data(self) -> dict[str, str]:
        body = self.section("meta_data")
        fields: dict[str, str] = {}
        for key in ("version", "game_date", "real_date", "name", "rank"):
            match = re.search(rf'(?m)^\t{key}="?([^"\n]*)"?$', body)
            if match:
                fields[key] = match.group(1).strip()
        for key in ("mods", "dlcs"):
            match = re.search(rf"(?m)^\t{key}=\{{([^}}]*)\}}", body)
            if match:
                fields[key] = " ".join(re.findall(r'"([^"]+)"', match.group(1)))
        return fields

    def game_date(self) -> str:
        """The save's own date, from the top-level ``date=`` line."""

        match = re.search(r"(?m)^date=(\d+\.\d+\.\d+)", self.text)
        meta = self.meta_data()
        if match is None:
            if "game_date" not in meta:
                raise SaveExportError(f"{self.path}: no game date found")
            return meta["game_date"]
        return match.group(1)

    def digest(self) -> tuple[int, str]:
        sha = hashlib.sha256()
        with self.path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1 << 20), b""):
                sha.update(chunk)
        return self.path.stat().st_size, sha.hexdigest()


def load_subject_actions(game_root: Path) -> set[str]:
    """Pact actions that denote a subject relationship, per the installed game.

    ``common/subject_types/*.txt`` names the diplomatic action implementing each
    subject type, so the set is derived rather than guessed.
    """

    directory = Path(game_root) / "common/subject_types"
    if not directory.is_dir():
        raise SaveExportError(
            f"{game_root}: common/subject_types is missing; --game-root must point at the game's data folder"
        )
    actions: set[str] = set()
    for path in sorted(directory.rglob("*.txt")):
        text = path.read_text("utf-8-sig", errors="replace")
        actions.update(re.findall(r"(?m)^\s*diplomatic_action\s*=\s*([a-z_]+)", text))
    if not actions:
        raise SaveExportError(f"{directory}: no diplomatic_action entries found")
    return actions


def country_ids(save: PdxSave) -> dict[str, int]:
    """Map every tag present in the save to its runtime country id."""

    mapping: dict[str, int] = {}
    for identifier, body in save.database("country_manager").items():
        match = re.search(r'definition="([A-Z0-9]{3})"', body)
        if match:
            mapping[match.group(1)] = identifier
    return mapping


def ranks(save: PdxSave) -> dict[int, str]:
    body = save.section("country_rankings")
    start = body.find("country_rankings={")
    if start == -1:
        raise SaveExportError(f"{save.path}: country_rankings has no ranking list")
    found: dict[int, str] = {}
    for block in re.findall(r"\{\s*(.*?)\s*\}", body[start:], re.S):
        country = re.search(r"\bcountry=(\d+)", block)
        rank = re.search(r"\brank=([a-z_]+)", block)
        if country and rank:
            found[int(country.group(1))] = rank.group(1)
    return found


def market_owners(save: PdxSave) -> dict[int, int]:
    owners: dict[int, int] = {}
    for identifier, body in save.database("market_manager").items():
        owner = _integer(body, "owner")
        if owner is not None:
            owners[identifier] = owner
    return owners


def state_owners(save: PdxSave) -> dict[int, int]:
    owners: dict[int, int] = {}
    for identifier, body in save.database("states").items():
        country = _integer(body, "country")
        if country is not None:
            owners[identifier] = country
    return owners


def population_by_state(save: PdxSave) -> dict[int, int]:
    """State id -> workforce + dependents of the pops the save places there."""

    totals: dict[int, int] = {}
    for _identifier, body in save.database("pops").items():
        workforce = _integer(body, "workforce")
        dependents = _integer(body, "dependents")
        location = _integer(body, "location")
        if workforce is None or dependents is None or location is None:
            continue
        totals[location] = totals.get(location, 0) + workforce + dependents
    return totals


def ongoing_wars(save: PdxSave) -> dict[int, int]:
    """Country id -> number of wars it is currently fighting."""

    counts: dict[int, int] = {}
    for _identifier, body in save.database("war_manager").items():
        if _scalar(body, "peace_date") != ONGOING_WAR_PEACE_DATE:
            continue
        participants = _block(body, "war_participants")
        if participants is None:
            continue
        for country in {
            int(value) for value in re.findall(r"\bcountry=(\d+)", participants)
        }:
            if country == NO_COUNTRY:
                continue
            counts[country] = counts.get(country, 0) + 1
    return counts


def subject_counts(save: PdxSave, subject_actions: set[str]) -> dict[int, int]:
    """Country id -> number of subject relationships it is the overlord of.

    ``pacts`` stores ``targets={ first=... second=... }`` where ``first`` is the
    overlord: vanilla's ``c:CHI ?= { create_diplomatic_pact = { country = c:TIB
    type = vassal } }`` appears in a real save as ``vassal first=156 second=167``
    (156=CHI, 167=TIB).
    """

    counts: dict[int, int] = {}
    for _identifier, body in save.database("pacts").items():
        action = _scalar(body, "action")
        if action not in subject_actions:
            continue
        targets = _block(body, "targets")
        if targets is None:
            continue
        first = re.search(r"\bfirst=(\d+)", targets)
        if first is None:
            continue
        overlord = int(first.group(1))
        if overlord == NO_COUNTRY:
            continue
        counts[overlord] = counts.get(overlord, 0) + 1
    return counts


def strata_population(body: str) -> int | None:
    """The country panel's population: lower + middle + upper strata.

    The three counters live inside the country's nested ``pop_statistics`` block
    rather than at the country's own level, so they are read from there.
    """

    statistics = _block(body, "pop_statistics")
    if statistics is None:
        return None
    total = 0
    for stratum in ("lower", "middle", "upper"):
        match = re.search(rf"(?m)^\s*population_{stratum}_strata=(\d+)\s*$", statistics)
        if match is None:
            return None
        total += int(match.group(1))
    return total


def count_log_lines(path: Path | None) -> int:
    """Line count of a run's error log, which is the checkpoint error counter."""

    if path is None:
        return 0
    if not path.is_file():
        raise SaveExportError(f"error log does not exist: {path}")
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        return sum(1 for line in handle if line.strip())


def export(
    save_path: Path,
    game_root: Path,
    error_log: Path | None = None,
    year: int | None = None,
    cross_check_population: bool = True,
    allow_any_date: bool = False,
) -> dict:
    """Build the export document for one save without modifying anything.

    A checkpoint save must be dated in a checkpoint year, so ``--year`` both
    asserts the year and is checked against the save's own date; a save taken at
    any other date is refused unless ``allow_any_date`` is set for diagnosis, in
    which case the document records itself as not checkpoint-eligible.
    """

    save = PdxSave(save_path)
    game_date = save.game_date()
    save_year = int(game_date.split(".")[0])
    if year is not None:
        if save_year != year:
            raise SaveExportError(
                f"{save_path}: save is dated {game_date} (year {save_year}) but --year {year} was asserted"
            )
        if year not in CHECKPOINT_YEARS:
            raise SaveExportError(f"--year {year} is not one of the checkpoint years {list(CHECKPOINT_YEARS)}")
        checkpoint_year = year
    elif allow_any_date:
        checkpoint_year = save_year
    elif save_year in CHECKPOINT_YEARS:
        checkpoint_year = save_year
    else:
        raise SaveExportError(
            f"{save_path}: game date {game_date} does not fall in a checkpoint year "
            f"{list(CHECKPOINT_YEARS)}; take the checkpoint save at a checkpoint year "
            "(use --any-date only to diagnose a save that is not checkpoint material)"
        )

    subject_actions = load_subject_actions(game_root)
    ids = country_ids(save)
    rank_by_country = ranks(save)
    owner_of_market = market_owners(save)
    owner_of_state = state_owners(save)
    war_counts = ongoing_wars(save)
    overlord_counts = subject_counts(save, subject_actions)
    row_error_count = count_log_lines(error_log)

    missing_tags = [tag for tag in CORE_COUNTRIES if tag not in ids]
    if missing_tags:
        raise SaveExportError(
            f"{save_path}: core countries absent from this save: {', '.join(missing_tags)}. "
            "A checkpoint needs all ten; record the run as an anomaly instead of inventing a row."
        )

    tag_of_country = {identifier: tag for tag, identifier in ids.items()}
    countries = save.database("country_manager")

    state_totals: dict[int, int] | None = None
    if cross_check_population:
        state_totals = population_by_state(save)
        by_country: dict[int, int] = {}
        for state, total in state_totals.items():
            country = owner_of_state.get(state)
            if country is None:
                continue
            by_country[country] = by_country.get(country, 0) + total

    rows: list[dict] = []
    warnings: list[str] = []
    population_sources: dict[str, str] = {}
    for tag in CORE_COUNTRIES:
        country = ids[tag]
        body = countries[country]

        rank = rank_by_country.get(country)
        if rank is None:
            raise SaveExportError(f"{save_path}: country {tag} has no entry in country_rankings")

        population = strata_population(body)
        population_source = "pop_statistics_strata"
        if population is None:
            if state_totals is None:
                state_totals = population_by_state(save)
            population = sum(
                total
                for state, total in state_totals.items()
                if owner_of_state.get(state) == country
            )
            population_source = "pops_by_state_workforce_and_dependents"
            warnings.append(f"{tag}: pop_statistics has no strata totals; used the pops sum instead")
        elif cross_check_population:
            expected = by_country.get(country, 0)
            if expected and abs(population - expected) > max(1, int(expected * POPULATION_TOLERANCE)):
                warnings.append(
                    f"{tag}: pop_statistics strata {population} differs from the pops-by-state sum "
                    f"{expected} by more than {POPULATION_TOLERANCE:.1%}; re-check the save"
                )
        population_sources[tag] = population_source

        market_id = _integer(body, "market")
        market_owner = owner_of_market.get(market_id) if market_id is not None else None
        market_tag = tag_of_country.get(market_owner)
        if market_tag is None:
            raise SaveExportError(
                f"{save_path}: country {tag} has market {market_id} with no owner in market_manager"
            )

        rows.append(
            {
                "year": checkpoint_year,
                "country": tag,
                "rank": rank,
                "population": population,
                "market": market_tag,
                "wars": war_counts.get(country, 0),
                "subjects": overlord_counts.get(country, 0),
                "error_count": row_error_count,
            }
        )

    size, sha256 = save.digest()
    meta = save.meta_data()
    return {
        "schema_version": 1,
        "checked_at_source": str(save_path),
        "save": {
            "path": str(save_path),
            "size_bytes": size,
            "sha256": sha256,
            "game_date": game_date,
            "game_version": meta.get("version"),
            "played_country": meta.get("name"),
            "mods": meta.get("mods", ""),
            "dlcs": meta.get("dlcs", ""),
        },
        "checkpoint_year": checkpoint_year,
        "checkpoint_eligible": checkpoint_year in CHECKPOINT_YEARS,
        "population_source": population_sources,
        "error_log": str(error_log) if error_log is not None else None,
        "error_count": row_error_count,
        "warnings": warnings,
        "rows": rows,
    }


def write_csv(document: dict, path: Path) -> None:
    lines = [",".join(CSV_COLUMNS)]
    for row in document["rows"]:
        lines.append(",".join(str(row[column]) for column in CSV_COLUMNS))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--save", type=Path, required=True, help="a real .v3 save file")
    parser.add_argument("--game-root", type=Path, required=True, help="the game's data directory")
    parser.add_argument(
        "--error-log",
        type=Path,
        help="the run's logs/error.log; its line count becomes error_count",
    )
    parser.add_argument("--year", type=int, choices=list(CHECKPOINT_YEARS))
    parser.add_argument(
        "--any-date",
        action="store_true",
        help="diagnose a save taken outside a checkpoint year; the export records itself as not checkpoint-eligible",
    )
    parser.add_argument("--output", type=Path, help="write rows here (see --format)")
    parser.add_argument("--format", choices=("json", "csv"), default="json")
    parser.add_argument(
        "--no-cross-check-population",
        action="store_true",
        help="skip the pops-by-state cross-check (faster, less verification)",
    )
    args = parser.parse_args()

    try:
        document = export(
            args.save,
            args.game_root,
            args.error_log,
            args.year,
            cross_check_population=not args.no_cross_check_population,
            allow_any_date=args.any_date,
        )
    except (OSError, ValueError, SaveExportError) as error:
        print(error)
        return 1

    for warning in document["warnings"]:
        print(f"warning: {warning}")
    if args.output is not None:
        if args.format == "csv":
            write_csv(document, args.output)
        else:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(
                json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )
        print(f"Wrote {args.format} export: {args.output}")
    else:
        print(json.dumps(document, ensure_ascii=False, indent=2))

    print(
        f"\ncheckpoint {document['checkpoint_year']} from {document['save']['game_date']}: "
        f"{len(document['rows'])} countries, error_count={document['error_count']}, "
        f"checkpoint_eligible={document['checkpoint_eligible']}"
    )
    for row in document["rows"]:
        print(
            f"  {row['country']:4} rank={row['rank']:<28} population={row['population']:>12,} "
            f"market={row['market']:<4} wars={row['wars']} subjects={row['subjects']}"
        )
    if not document["checkpoint_eligible"]:
        print("\nNot checkpoint material: the save is dated outside a checkpoint year.")
        return 1
    if document["error_count"]:
        print(f"\n{Path(document['error_log']).name}: {document['error_count']} lines; fix the run before recording.")
        return 1
    print("\nFeed this to record_checkpoint.py; it does not accept a run with script errors.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
