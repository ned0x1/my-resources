from kudzu.config import DEFAULT_CONFIG
from kudzu.rules import generate_variants


def test_generate_variants_includes_seed():
    variants = generate_variants("Ete2026", DEFAULT_CONFIG)
    assert "Ete2026" in variants


def test_generate_variants_caps_output_size():
    config = DEFAULT_CONFIG.copy()
    config["limits"] = {**DEFAULT_CONFIG["limits"], "max_variants_per_password": 25}
    variants = generate_variants("password", config)
    assert len(variants) <= 25


def test_year_range_covers_full_span():
    from datetime import datetime
    config = DEFAULT_CONFIG.copy()
    # Isolate the year-range rule so the cap/other stages don't crowd out
    # the longer full-length-year variants we're checking for here.
    config["rules"] = {**DEFAULT_CONFIG["rules"], "leet_speak": False, "case_powerset": False,
                        "symbol_wrap": False, "digit_range": False}
    config["limits"] = {**DEFAULT_CONFIG["limits"], "max_variants_per_password": 100000}
    variants = generate_variants("Shinra2020", config)
    current = datetime.now().year
    for y in range(2020, current + 3):
        assert f"Shinra{y}" in variants


def test_non_year_digit_range():
    variants = generate_variants("Ete202", DEFAULT_CONFIG)
    assert "Ete192" in variants
    assert "Ete212" in variants
    assert "Ete222" not in variants


def test_case_powerset_full_combinations():
    config = DEFAULT_CONFIG.copy()
    config["rules"] = {**DEFAULT_CONFIG["rules"], "leet_speak": False, "symbol_wrap": False,
                        "year_range": False, "digit_range": False}
    variants = generate_variants("Ete", config)
    expected = {"ete", "Ete", "eTe", "etE", "EtE", "ETe", "eTE", "ETE"}
    assert expected.issubset(variants)


def test_symbol_wrap_prefix_and_suffix():
    config = DEFAULT_CONFIG.copy()
    config["rules"] = {**DEFAULT_CONFIG["rules"], "leet_speak": False, "case_powerset": False,
                        "year_range": False, "digit_range": False}
    variants = generate_variants("Ete", config)
    assert "Ete!" in variants
    assert "!Ete" in variants


def test_keyword_combo_requires_keyword():
    without_keyword = generate_variants("Shinra2022", DEFAULT_CONFIG)
    with_keyword = generate_variants("Shinra2022", DEFAULT_CONFIG, keyword="ACME")
    assert any(v.startswith("Acme") or v.startswith("ACME") or v.startswith("acme") for v in with_keyword)
