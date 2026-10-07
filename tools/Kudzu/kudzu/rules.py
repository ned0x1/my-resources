"""Mutation rule engine: expands a seed password into variants.

Pipeline, in order:
  1. Number handling: a 4-digit year (1800..current_year) in the password is
     expanded to the full range up to current_year + future_offset, with
     2-digit short forms and a separator inserted right before the year.
     A non-year digit run is replaced by every value within +/- spread of
     it, keeping the same zero-padded width. If there's no digit run at
     all, this stage is a no-op (just the original password).
  2. Case powerset: every upper/lower combination of each letter.
  3. Leet speak: full-string substitution on top of each case variant.
  4. Symbol wrap: prepend / append a symbol to each variant so far.

Each stage is individually toggleable in config.yaml. Intermediate sets are
trimmed against a generous internal ceiling between stages so a long,
letter-heavy password can't make the pipeline blow up in time/memory before
the final output cap is applied.
"""

from __future__ import annotations

import heapq
import re
from datetime import datetime
from typing import Any

NUMBER_RE = re.compile(r"\d+")

# Safety ceiling applied *between* pipeline stages (independent of the
# final, user-configurable max_variants_per_password cap) so an unusually
# long password can't make an intermediate set explode before trimming.
_STAGE_CEILING = 20000

# The letter pool (case powerset x leet) is trimmed to this size before
# being fanned out across every year/digit-range number variant, since
# fanning a large pool out is the expensive step. Keeping this close to the
# final output cap avoids doing (large pool) x (dozens of number variants)
# worth of work just to throw most of it away at the final selection step.
_LETTER_POOL_CEILING = 6000


def _trim(items: set[str], limit: int) -> set[str]:
    if len(items) <= limit:
        return items
    # nsmallest avoids a full O(n log n) sort when limit << len(items).
    return set(heapq.nsmallest(limit, items, key=lambda s: (len(s), s)))


def _is_year(run: str) -> bool:
    if len(run) != 4:
        return False
    year = int(run)
    return 1800 <= year <= datetime.now().year


def _year_variants_from_parts(prefix: str, year_str: str, suffix: str, year_cfg: dict[str, Any]) -> set[str]:
    start_year = int(year_str)
    end_year = datetime.now().year + year_cfg.get("future_offset", 2)
    short_form = year_cfg.get("short_form", True)
    separators = year_cfg.get("separators", [])

    variants = set()
    for y in range(start_year, end_year + 1):
        y4 = str(y)
        y2 = y4[-2:]
        variants.add(f"{prefix}{y4}{suffix}")
        if short_form:
            variants.add(f"{prefix}{y2}{suffix}")
        if prefix and separators:
            for sep in separators:
                variants.add(f"{prefix}{sep}{y4}{suffix}")
                if short_form:
                    variants.add(f"{prefix}{sep}{y2}{suffix}")
    return variants


def _year_variants(password: str, match: re.Match, year_cfg: dict[str, Any]) -> set[str]:
    prefix = password[: match.start()]
    suffix = password[match.end():]
    return _year_variants_from_parts(prefix, match.group(), suffix, year_cfg)


def _digit_range_variants_from_parts(prefix: str, run: str, suffix: str, digits_cfg: dict[str, Any]) -> set[str]:
    spread = digits_cfg.get("spread", 10)
    width = len(run)
    base = int(run)

    variants = set()
    for v in range(max(0, base - spread), base + spread + 1):
        s = str(v).zfill(width)
        variants.add(f"{prefix}{s}{suffix}")
    return variants


def _digit_range_variants(password: str, match: re.Match, digits_cfg: dict[str, Any]) -> set[str]:
    prefix = password[: match.start()]
    suffix = password[match.end():]
    return _digit_range_variants_from_parts(prefix, match.group(), suffix, digits_cfg)


def _number_variants(password: str, config: dict[str, Any]) -> set[str]:
    rules = config["rules"]
    matches = list(NUMBER_RE.finditer(password))
    if not matches:
        return {password}

    variants: set[str] = {password}
    for match in matches:
        if _is_year(match.group()):
            if rules.get("year_range"):
                variants |= _year_variants(password, match, config["year"])
        else:
            if rules.get("digit_range"):
                variants |= _digit_range_variants(password, match, config["digits_range"])
    return variants


def _number_variants_for_spans(word: str, matches: list[re.Match], config: dict[str, Any]) -> set[str]:
    """Like _number_variants, but reuses digit-run positions already found
    on the original password instead of re-scanning `word`. Valid because
    case-toggling and leet substitution never change string length or touch
    digit characters, so the same (start, end) spans still point at the
    same digit run (now possibly surrounded by re-cased/leeted letters)."""
    rules = config["rules"]
    if not matches:
        return {word}

    variants: set[str] = {word}
    for match in matches:
        start, end = match.start(), match.end()
        run = word[start:end]
        prefix = word[:start]
        suffix = word[end:]
        if _is_year(run):
            if rules.get("year_range"):
                variants |= _year_variants_from_parts(prefix, run, suffix, config["year"])
        else:
            if rules.get("digit_range"):
                variants |= _digit_range_variants_from_parts(prefix, run, suffix, config["digits_range"])
    return variants


def _case_powerset(word: str, max_length: int) -> set[str]:
    letter_positions = [i for i, c in enumerate(word) if c.isalpha()]
    if not letter_positions:
        return {word}
    if len(letter_positions) > max_length:
        return {word}

    variants = set()
    n = len(letter_positions)
    chars = list(word)
    for bitmask in range(2 ** n):
        for j, idx in enumerate(letter_positions):
            chars[idx] = chars[idx].upper() if (bitmask >> j) & 1 else chars[idx].lower()
        variants.add("".join(chars))
    return variants


def _leet_full(word: str, mapping: dict[str, str]) -> str:
    return "".join(mapping.get(ch.lower(), ch) for ch in word)


def generate_variants(
    password: str,
    config: dict[str, Any],
    keyword: str | None = None,
) -> list[str]:
    """Generate mutation variants for a single stored password according to
    the active ruleset in `config`. Returns a deduplicated, deterministically
    ordered list (seed password always included).

    The direct output of rule 1 (year range / non-year digit range, plus
    keyword-combo year combinations) is treated as "core": it is never
    dropped by the output cap, since it's the explicit, bounded result of a
    rule the person asked for. Only the combinatorial case-powerset /
    leet-speak / symbol-wrap expansion on top of it is trimmed against the
    cap, since that's the part that can blow up in size.
    """
    rules = config["rules"]
    cap = config["limits"].get("max_variants_per_password") or 5000
    matches = list(NUMBER_RE.finditer(password))

    # 1. "core" = the direct, bounded output of the year-range / digit-range
    #    rule applied to the password's original casing, plus keyword
    #    combos. This is the explicit result of a rule someone asked for,
    #    so it is always kept in full and never dropped by the output cap.
    core = _number_variants(password, config)
    active_keyword = keyword or config.get("keyword")
    if rules.get("keyword_combo") and active_keyword:
        core |= _keyword_combos(password, active_keyword, config)
    core.add(password)
    core = _trim(core, _STAGE_CEILING)

    # 2. Case powerset + leet, computed ONCE on the password's letters
    #    (not once per number variant - that's what made long passwords
    #    slow). Digit positions are untouched by both, so the match spans
    #    found above stay valid on every result.
    letter_pool = {password}
    if rules.get("case_powerset"):
        letter_pool = _case_powerset(password, config["case"].get("max_length", 15))
    if rules.get("leet_speak"):
        mapping = config["leet"]["mapping"]
        letter_pool = letter_pool | {_leet_full(w, mapping) for w in letter_pool}
    letter_pool = _trim(letter_pool, _LETTER_POOL_CEILING)

    # 3. Fan the number-range rule out over every case/leet variant, reusing
    #    the original digit-run positions (cheap slicing, no recomputation).
    working = set(core)
    for w in letter_pool:
        working |= _number_variants_for_spans(w, matches, config)
    working = _trim(working, _STAGE_CEILING)

    # 4. Symbol wrap: prepend / append a symbol.
    if rules.get("symbol_wrap"):
        symbols = config["symbols"]
        wrapped = set(working)
        for w in working:
            for s in symbols:
                wrapped.add(f"{s}{w}")
                wrapped.add(f"{w}{s}")
        working = _trim(wrapped, _STAGE_CEILING)

    # -- final selection: core is always kept in full; the rest of the cap
    #    budget is filled with the combinatorial expansion, deterministically.
    core = _trim(core, cap)  # only trims core in the pathological case it alone exceeds cap
    remaining_budget = max(0, cap - len(core))
    extra_candidates = working - core
    extra_sorted = sorted(extra_candidates, key=lambda s: (len(s), s))[:remaining_budget]

    final_set = core | set(extra_sorted)
    ordered = sorted(final_set, key=lambda s: (s != password, len(s), s))
    return ordered


def _keyword_combos(password: str, keyword: str, config: dict[str, Any]) -> set[str]:
    k = keyword.strip()
    if not k:
        return set()

    variants = {k, k.capitalize(), k.upper(), k.lower(), f"{k}{password}", f"{password}{k}"}

    # If the stored password contains a year, combine the keyword with the
    # same expanded year range (Shinra2022 -> Shinra2022..Shinra2028,
    # Shinra_2022, Shinra22, ...).
    year_match = next((m for m in NUMBER_RE.finditer(password) if _is_year(m.group())), None)
    if year_match:
        for cap_form in {k, k.capitalize(), k.upper(), k.lower()}:
            variants |= _year_variants_from_parts(cap_form, year_match.group(), "", config["year"])

    return variants
