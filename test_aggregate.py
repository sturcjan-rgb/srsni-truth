"""Testy pro aggregate.py na dočasné DB s vymyšlenými zápasy (bez sítě)."""

import tempfile
from pathlib import Path

import aggregate
import db

GAME_1 = {
    "clock": "00:00",
    "period": 4,
    "inOT": False,
    "tm": {
        "1": {
            "name": "Sršni Photomate Písek",
            "score": 80,
            "pl": {
                "1": {"firstName": "Adam", "familyName": "A", "sMinutes": "20:00", "sPoints": "20",
                      "sFieldGoalsAttempted": "15", "sFieldGoalsMade": "8", "sFreeThrowsAttempted": "4",
                      "sAssists": "3", "sTurnovers": "1", "sReboundsTotal": "5", "starter": 1},
                "2": {"firstName": "Bedřich", "familyName": "B", "sMinutes": "20:00", "sPoints": "10",
                      "sAssists": "6", "sTurnovers": "2", "starter": 1},
            },
        },
        "2": {"name": "Soupeř", "score": 70, "pl": {}},
    },
    "pbp": [],
}

GAME_2 = {
    "clock": "00:00",
    "period": 4,
    "inOT": False,
    "tm": {
        "1": {
            "name": "Sršni Photomate Písek",
            "score": 60,
            "pl": {
                "1": {"firstName": "Adam", "familyName": "A", "sMinutes": "18:00", "sPoints": "10",
                      "sFieldGoalsAttempted": "10", "sFieldGoalsMade": "4", "sFreeThrowsAttempted": "2",
                      "sAssists": "1", "sTurnovers": "0", "sReboundsTotal": "3", "starter": 1},
                "3": {"firstName": "Cyril", "familyName": "C", "sMinutes": "00:00", "sPoints": "0", "starter": 0},
            },
        },
        "2": {"name": "Jiny soupeř", "score": 65, "pl": {}},
    },
    "pbp": [],
}


def _setup_db(tmp_path):
    with db.connect(tmp_path) as conn:
        db.upsert_match(conn, 1, season="2025/26", date_utc="2025-10-01T17:00:00+00:00", status="finished")
        db.upsert_match(conn, 2, season="2025/26", date_utc="2025-10-08T17:00:00+00:00", status="finished")
        db.add_snapshot(conn, 1, GAME_1)
        db.add_snapshot(conn, 2, GAME_2)


def test_player_stats_aggregates_across_games_and_skips_dnp():
    tmp = Path(tempfile.mktemp(suffix=".db"))
    _setup_db(tmp)
    with db.connect(tmp) as conn:
        players = aggregate.player_stats(conn, "2025/26")
    tmp.unlink()

    by_name = {p.name: p for p in players}
    assert by_name["Adam A"].games == 2
    assert by_name["Adam A"].points == 30
    assert by_name["Adam A"].points_per_game == 15.0
    # Bedřich hral jen v prvním zápase
    assert by_name["Bedřich B"].games == 1
    # Cyril mel 0 minut ve druhem zapase -> nema se pocitat vubec
    assert "Cyril C" not in by_name


def test_team_record_wins_and_losses():
    tmp = Path(tempfile.mktemp(suffix=".db"))
    _setup_db(tmp)
    with db.connect(tmp) as conn:
        record = aggregate.team_record(conn, "2025/26")
    tmp.unlink()

    assert record.wins == 1
    assert record.losses == 1
    assert record.points_for == 140
    assert record.points_against == 135
    assert len(record.games) == 2
    assert record.games[0].nbl_id == 1
    assert record.games[0].won is True
    assert record.games[1].won is False


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
