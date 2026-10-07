"""Configuration handling for kudzu (~/.kudzu/config.yaml)."""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

import yaml

KUDZU_HOME = Path.home() / ".kudzu"
CONFIG_PATH = KUDZU_HOME / "config.yaml"
PASSWORD_DIR = KUDZU_HOME / "password"
PASSWORD_LIST_PATH = PASSWORD_DIR / "list.txt"
PASSWORD_LIST_ENC_PATH = PASSWORD_DIR / "list.txt.gpg"

DEFAULT_CONFIG: dict[str, Any] = {
    "rules": {
        # A 4-digit substring between 1800 and the current year is treated
        # as a year: expand it to every year from itself up to
        # current_year + year.future_offset, plus 2-digit short forms, plus
        # a separator inserted just before the year.
        "year_range": True,
        # Full-string leet substitution (a->4, e->3, s->$...).
        "leet_speak": True,
        # Every upper/lower combination of each letter in the password
        # (skipped above case.max_length letters).
        "case_powerset": True,
        # Prepend / append a symbol.
        "symbol_wrap": True,
        # A digit run that is NOT a plausible year gets replaced by every
        # value within +/- digits_range.spread of it, same zero-padded width.
        "digit_range": True,
        # Combine a stored password with --keyword (or the keyword below).
        "keyword_combo": True,
    },
    "year": {
        "future_offset": 2,      # generate up to current_year + this
        "short_form": True,       # also emit the 2-digit year
        "separators": ["_", "-", "."],  # inserted just before the year
    },
    "digits_range": {
        "spread": 10,  # +/- this many around a non-year number
    },
    "case": {
        # Skip full case-powerset expansion past this many letters
        # (2^16 and up gets slow/huge). The password is still included
        # with its original casing.
        "max_length": 15,
    },
    "symbols": ["!", "@", "#", "$", ".", "?"],
    "leet": {
        "mapping": {
            "a": "4",
            "e": "3",
            "i": "1",
            "o": "0",
            "s": "$",
            "t": "7",
        },
    },
    # Extra word folded into variants alongside each stored password
    # (company name, target name, project codename...). Overridable per
    # run with `--keyword` on create-list.
    "keyword": None,
    "limits": {
        # Safety cap on how many variants a single stored password can expand
        # into. Prevents combinatorial blow-up on large/high-entropy input.
        "max_variants_per_password": 5000,
    },
    "storage": {
        # "none" or "gpg" (symmetric encryption via the system `gpg` binary)
        "encryption": "none",
    },
}


def _deep_merge(base: dict, override: dict) -> dict:
    result = copy.deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def ensure_kudzu_home() -> None:
    KUDZU_HOME.mkdir(parents=True, exist_ok=True)
    PASSWORD_DIR.mkdir(parents=True, exist_ok=True)


def load_config() -> dict[str, Any]:
    """Load config.yaml, creating it with defaults if missing, then merge
    with defaults so new keys introduced by later kudzu versions are always
    present even in an older user config file."""
    ensure_kudzu_home()
    if not CONFIG_PATH.exists():
        save_config(DEFAULT_CONFIG)
        return copy.deepcopy(DEFAULT_CONFIG)

    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        user_config = yaml.safe_load(f) or {}

    return _deep_merge(DEFAULT_CONFIG, user_config)


def save_config(config: dict[str, Any]) -> None:
    ensure_kudzu_home()
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        yaml.safe_dump(config, f, sort_keys=False, allow_unicode=True)
