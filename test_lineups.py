"""Testy pro lineups.py na vymyšleném pbp (bez sítě)."""

from lineups import analyze_pbp, merge_lineup_stats, top_assist_pairs, top_combos

# Zjednodušený zápas: tým "Sršni" (tno=1) má 5 hráčů (A-E), soupeř (tno=2)
# jednoho hráče (X). Sestava na startu: A,B,C,D,E. Průběh:
#  - A dá 2 body (assist od B) -> combo (A,B,C,D,E) i všechny podmnožiny +2
#  - substituce: E ven, F dovnitř
#  - C dá 3 body (assist od B) -> teď hraje A,B,C,D,F -> +3 těmhle kombinacím
#  - soupeřův koš se nepočítá do žádné kombinace Sršňů

RAW_JSON = {
    "tm": {
        "1": {
            "name": "Sršni Photomate Písek",
            "pl": {
                "1": {"firstName": "Adam", "familyName": "A", "starter": 1},
                "2": {"firstName": "Bedřich", "familyName": "B", "starter": 1},
                "3": {"firstName": "Cyril", "familyName": "C", "starter": 1},
                "4": {"firstName": "David", "familyName": "D", "starter": 1},
                "5": {"firstName": "Emil", "familyName": "E", "starter": 1},
                "6": {"firstName": "Filip", "familyName": "F", "starter": 0},
            },
        },
        "2": {
            "name": "Soupeř",
            "pl": {"1": {"firstName": "X", "familyName": "Y", "starter": 1}},
        },
    },
    "pbp": [
        {"actionNumber": 5, "actionType": "assist", "tno": 1, "pno": 2, "previousAction": 4, "success": 1},
        {"actionNumber": 4, "actionType": "2pt", "tno": 1, "pno": 1, "success": 1},
        {"actionNumber": 3, "actionType": "2pt", "tno": 2, "pno": 1, "success": 1},
        {"actionNumber": 10, "actionType": "substitution", "tno": 1, "pno": 5, "subType": "out"},
        {"actionNumber": 11, "actionType": "substitution", "tno": 1, "pno": 6, "subType": "in"},
        {"actionNumber": 15, "actionType": "assist", "tno": 1, "pno": 2, "previousAction": 14, "success": 1},
        {"actionNumber": 14, "actionType": "3pt", "tno": 1, "pno": 3, "success": 1},
    ],
}


def test_combo_points_before_substitution():
    result = analyze_pbp(RAW_JSON)
    assert result is not None
    full_five = ("1", "2", "3", "4", "5")
    assert result.combo_points[full_five] == 2
    pair_a_b = ("1", "2")
    # A+B jsou spolu na hřišti v obou úsecích (pred i po substituci) -> 2 + 3
    assert result.combo_points[pair_a_b] == 5


def test_combo_points_after_substitution():
    result = analyze_pbp(RAW_JSON)
    five_after_sub = ("1", "2", "3", "4", "6")
    assert result.combo_points[five_after_sub] == 3
    # puvodni petka uz nema dalsi body po substituci
    five_before_sub = ("1", "2", "3", "4", "5")
    assert five_before_sub in result.combo_points
    assert five_before_sub != five_after_sub


def test_opponent_points_not_counted():
    result = analyze_pbp(RAW_JSON)
    # soupeřův koš by neměl vytvořit žádnou kombinaci se hráčem tno=2 pno=1
    for combo in result.combo_points:
        assert all(pid in {"1", "2", "3", "4", "5", "6"} for pid in combo)


def test_assist_pairs():
    result = analyze_pbp(RAW_JSON)
    pair = tuple(sorted(("2", "1")))  # B nahral A
    assert result.assist_counts[pair] == 1
    pair2 = tuple(sorted(("2", "3")))  # B nahral C na trojku
    assert result.assist_counts[pair2] == 1
    assert result.assist_points[pair2] == 3


def test_top_combos_and_assist_pairs():
    result = analyze_pbp(RAW_JSON)
    top_pairs = top_combos(result.combo_points, size=2, limit=1)
    assert top_pairs[0][0] == ("1", "2")
    assert top_pairs[0][1] == 5

    top_assists = top_assist_pairs(result.assist_counts, limit=5)
    assert len(top_assists) == 2


def test_merge_lineup_stats():
    result = analyze_pbp(RAW_JSON)
    merged = merge_lineup_stats([result, result])
    assert merged.combo_points[("1", "2")] == 10
    assert merged.assist_counts[tuple(sorted(("2", "1")))] == 2


def test_no_pbp_returns_none():
    assert analyze_pbp({"tm": {}, "pbp": []}) is None
    assert analyze_pbp({"tm": {"1": {"name": "Sršni", "pl": {}}}}) is None


if __name__ == "__main__":
    import sys

    failures = 0
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"OK   {name}")
            except AssertionError:
                failures += 1
                print(f"FAIL {name}")
    sys.exit(1 if failures else 0)
