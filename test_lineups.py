"""Testy pro lineups.py na vymyšleném pbp (bez sítě)."""

from lineups import analyze_pbp, merge_lineup_stats, top_assist_pairs, top_combos

# Zjednodušený zápas: tým "Sršni" (tno=1) má 5 hráčů (Adam, Bedřich,
# Cyril, David, Emil), soupeř (tno=2) jednoho hráče. Sestava na startu:
# Adam, Bedřich, Cyril, David, Emil. Průběh:
#  - Adam dá 2 body (asistence od Bedřicha) -> celá pětka i všechny
#    podmnožiny +2
#  - substituce: Emil ven, Filip dovnitř
#  - Cyril dá 3 body (asistence od Bedřicha) -> teď hraje Adam, Bedřich,
#    Cyril, David, Filip -> +3 těmhle kombinacím
#  - soupeřův koš se nepočítá do žádné kombinace Sršňů
#
# Výstupy analyze_pbp jsou klíčované JMÉNY (ne "pno" z JSONu), protože
# to číslo je stabilní jen v rámci jednoho zápasu - viz komentář u
# LineupStats v lineups.py.

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

ADAM, BEDRICH, CYRIL, DAVID, EMIL, FILIP = "Adam A", "Bedřich B", "Cyril C", "David D", "Emil E", "Filip F"


def test_combo_points_before_substitution():
    result = analyze_pbp(RAW_JSON)
    assert result is not None
    full_five = tuple(sorted((ADAM, BEDRICH, CYRIL, DAVID, EMIL)))
    assert result.combo_points[full_five] == 2
    pair_a_b = tuple(sorted((ADAM, BEDRICH)))
    # Adam+Bedřich jsou spolu na hřišti v obou úsecích (pred i po substituci) -> 2 + 3
    assert result.combo_points[pair_a_b] == 5


def test_combo_points_after_substitution():
    result = analyze_pbp(RAW_JSON)
    five_after_sub = tuple(sorted((ADAM, BEDRICH, CYRIL, DAVID, FILIP)))
    assert result.combo_points[five_after_sub] == 3
    five_before_sub = tuple(sorted((ADAM, BEDRICH, CYRIL, DAVID, EMIL)))
    assert five_before_sub in result.combo_points
    assert five_before_sub != five_after_sub


def test_opponent_points_not_counted():
    result = analyze_pbp(RAW_JSON)
    known_names = {ADAM, BEDRICH, CYRIL, DAVID, EMIL, FILIP}
    for combo in result.combo_points:
        assert all(name in known_names for name in combo)


def test_assist_pairs():
    result = analyze_pbp(RAW_JSON)
    pair = tuple(sorted((BEDRICH, ADAM)))  # Bedřich nahrál Adamovi
    assert result.assist_counts[pair] == 1
    pair2 = tuple(sorted((BEDRICH, CYRIL)))  # Bedřich nahrál Cyrilovi na trojku
    assert result.assist_counts[pair2] == 1
    assert result.assist_points[pair2] == 3


def test_top_combos_and_assist_pairs():
    result = analyze_pbp(RAW_JSON)
    top_pairs = top_combos(result.combo_points, size=2, limit=1)
    assert top_pairs[0][0] == tuple(sorted((ADAM, BEDRICH)))
    assert top_pairs[0][1] == 5

    top_assists = top_assist_pairs(result.assist_counts, limit=5)
    assert len(top_assists) == 2


def test_merge_lineup_stats():
    result = analyze_pbp(RAW_JSON)
    merged = merge_lineup_stats([result, result])
    assert merged.combo_points[tuple(sorted((ADAM, BEDRICH)))] == 10
    assert merged.assist_counts[tuple(sorted((BEDRICH, ADAM)))] == 2


def test_no_pbp_returns_none():
    assert analyze_pbp({"tm": {}, "pbp": []}) is None
    assert analyze_pbp({"tm": {"1": {"name": "Sršni", "pl": {}}}}) is None


def test_names_stay_correct_across_different_pno_numbering():
    """
    Klíčová regrese: pokud stejné pno v jiném zápase patří jinému
    hráči, výsledky se přesto nesmí zamíchat - protože se klíčuje
    jménem, ne číslem.
    """
    other_game = {
        "tm": {
            "1": {
                "name": "Sršni Photomate Písek",
                "pl": {
                    # stejná čísla (pno) jako v RAW_JSON, ale JINÍ lidé
                    "1": {"firstName": "Zoe", "familyName": "Z", "starter": 1},
                    "2": {"firstName": "Adam", "familyName": "A", "starter": 1},
                    "3": {"firstName": "Ivo", "familyName": "I", "starter": 1},
                    "4": {"firstName": "Petr", "familyName": "P", "starter": 1},
                    "5": {"firstName": "Karel", "familyName": "K", "starter": 1},
                },
            },
            "2": {"name": "Soupeř", "pl": {}},
        },
        "pbp": [
            # "pno": 2 je tady Adam, stejně jako v prvním zápase byl "pno": 1
            {"actionNumber": 1, "actionType": "2pt", "tno": 1, "pno": 2, "success": 1},
        ],
    }
    result_a = analyze_pbp(RAW_JSON)
    result_b = analyze_pbp(other_game)
    merged = merge_lineup_stats([result_a, result_b])

    # Adamovy body z obou zápasů se musí sečíst k NĚMU, ne k někomu
    # jinému jen proto, že měl v druhém zápase jiné číslo dresu.
    combo_with_adam_first_game = tuple(sorted((ADAM, BEDRICH)))
    assert merged.combo_points[combo_with_adam_first_game] == 5  # beze změny z prvního zápasu


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
