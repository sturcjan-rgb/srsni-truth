"""
aggregate.py - sezónní a kariérní statistiky napříč více zápasy.

Skládá dohromady to, co je už stažené v databázi (db.py): součty a
průměry hráčů za sezónu (nebo přes všechny sezóny = "kariéra"), bilanci
týmu (výhry/prohry, dané/obdržené body) a sezónní lineup kombinace +
asistenční dvojice (viz lineups.py).

Bez síťové závislosti - pracuje jen s tím, co je v DB.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import db
import lineups
import stats

SRSNI_NAME_SUBSTRING = "sršni"


def _num(value, default: int = 0) -> int:
    """Bezpečně převede hodnotu z JSONu na celé číslo."""
    if value is None:
        return default
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _srsni_tno(raw_json: dict) -> str | None:
    return lineups.find_team_number(raw_json, SRSNI_NAME_SUBSTRING)


def _opponent_tno(raw_json: dict, srsni_tno: str) -> str | None:
    for tno in raw_json.get("tm", {}):
        if tno != srsni_tno:
            return tno
    return None


def _finished_snapshots(conn, season: str | None) -> list[tuple[db.Match, dict]]:
    """Vrátí (zápas, poslední snapshot) pro každý DOHRANÝ zápas dané sezóny."""
    results = []
    for match in db.list_matches(conn, season=season):
        raw = db.get_latest_snapshot(conn, match.nbl_id)
        if raw is None or not stats.is_match_finished(raw):
            continue
        results.append((match, raw))
    return results


@dataclass
class PlayerSeasonStats:
    """Součtové statistiky jednoho hráče Sršňů za sezónu (nebo kariéru)."""

    player_id: str
    name: str
    games: int = 0
    points: int = 0
    rebounds_total: int = 0
    rebounds_offensive: int = 0
    rebounds_defensive: int = 0
    assists: int = 0
    steals: int = 0
    blocks: int = 0
    turnovers: int = 0
    fouls: int = 0
    field_goals_made: int = 0
    field_goals_attempted: int = 0
    two_pt_made: int = 0
    two_pt_attempted: int = 0
    three_pt_made: int = 0
    three_pt_attempted: int = 0
    free_throws_made: int = 0
    free_throws_attempted: int = 0

    @property
    def true_shooting_pct(self) -> float | None:
        return stats.true_shooting_pct(self.points, self.field_goals_attempted, self.free_throws_attempted)

    @property
    def effective_fg_pct(self) -> float | None:
        return stats.effective_fg_pct(self.field_goals_made, self.three_pt_made, self.field_goals_attempted)

    @property
    def assist_to_turnover_ratio(self) -> float | None:
        return stats.assist_to_turnover_ratio(self.assists, self.turnovers)

    @property
    def points_per_game(self) -> float | None:
        return self.points / self.games if self.games else None

    @property
    def rebounds_per_game(self) -> float | None:
        return self.rebounds_total / self.games if self.games else None

    @property
    def assists_per_game(self) -> float | None:
        return self.assists / self.games if self.games else None


def player_stats(conn, season: str | None = None) -> list[PlayerSeasonStats]:
    """
    Sezónní (nebo kariérní, pro season=None) statistiky hráčů Sršňů,
    seřazené sestupně podle celkových bodů.
    """
    totals: dict[str, PlayerSeasonStats] = {}

    for _match, raw in _finished_snapshots(conn, season):
        tno = _srsni_tno(raw)
        if tno is None:
            continue
        team = raw["tm"][tno]
        for pid, p in team.get("pl", {}).items():
            minutes = p.get("sMinutes") or "00:00"
            if minutes in ("00:00", "0:00", ""):
                continue  # hráč se zápasu nezúčastnil

            entry = totals.setdefault(
                pid,
                PlayerSeasonStats(player_id=pid, name=f"{p.get('firstName', '')} {p.get('familyName', '')}".strip()),
            )
            entry.games += 1
            entry.points += _num(p.get("sPoints"))
            entry.rebounds_total += _num(p.get("sReboundsTotal"))
            entry.rebounds_offensive += _num(p.get("sReboundsOffensive"))
            entry.rebounds_defensive += _num(p.get("sReboundsDefensive"))
            entry.assists += _num(p.get("sAssists"))
            entry.steals += _num(p.get("sSteals"))
            entry.blocks += _num(p.get("sBlocks"))
            entry.turnovers += _num(p.get("sTurnovers"))
            entry.fouls += _num(p.get("sFoulsPersonal"))
            entry.field_goals_made += _num(p.get("sFieldGoalsMade"))
            entry.field_goals_attempted += _num(p.get("sFieldGoalsAttempted"))
            entry.two_pt_made += _num(p.get("sTwoPointersMade"))
            entry.two_pt_attempted += _num(p.get("sTwoPointersAttempted"))
            entry.three_pt_made += _num(p.get("sThreePointersMade"))
            entry.three_pt_attempted += _num(p.get("sThreePointersAttempted"))
            entry.free_throws_made += _num(p.get("sFreeThrowsMade"))
            entry.free_throws_attempted += _num(p.get("sFreeThrowsAttempted"))

    return sorted(totals.values(), key=lambda e: e.points, reverse=True)


@dataclass
class GameResult:
    """Výsledek jednoho zápasu z pohledu Sršňů."""

    nbl_id: int
    date_utc: str | None
    opponent: str
    home_team: str | None
    away_team: str | None
    our_score: int
    opp_score: int
    won: bool


@dataclass
class TeamSeasonRecord:
    """Bilance týmu za sezónu (nebo kariéru)."""

    wins: int = 0
    losses: int = 0
    points_for: int = 0
    points_against: int = 0
    games: list[GameResult] = field(default_factory=list)

    @property
    def games_played(self) -> int:
        return self.wins + self.losses

    @property
    def points_for_per_game(self) -> float | None:
        return self.points_for / self.games_played if self.games_played else None

    @property
    def points_against_per_game(self) -> float | None:
        return self.points_against / self.games_played if self.games_played else None


def team_record(conn, season: str | None = None) -> TeamSeasonRecord:
    """Bilance Sršňů (výhry/prohry, skóre) za sezónu, seřazená podle data."""
    record = TeamSeasonRecord()

    for match, raw in _finished_snapshots(conn, season):
        tno = _srsni_tno(raw)
        opp_tno = _opponent_tno(raw, tno) if tno else None
        if tno is None or opp_tno is None:
            continue

        our_score = _num(raw["tm"][tno].get("score"))
        opp_score = _num(raw["tm"][opp_tno].get("score"))
        won = our_score > opp_score

        record.points_for += our_score
        record.points_against += opp_score
        if won:
            record.wins += 1
        else:
            record.losses += 1

        record.games.append(
            GameResult(
                nbl_id=match.nbl_id,
                date_utc=match.date_utc,
                opponent=raw["tm"][opp_tno].get("name", ""),
                home_team=match.home_team,
                away_team=match.away_team,
                our_score=our_score,
                opp_score=opp_score,
                won=won,
            )
        )

    record.games.sort(key=lambda g: g.date_utc or "")
    return record


def season_lineup_stats(conn, season: str | None = None) -> lineups.LineupStats:
    """Sečte lineup/asistenční statistiky (lineups.py) přes celou sezónu."""
    results = []
    for _match, raw in _finished_snapshots(conn, season):
        result = lineups.analyze_pbp(raw)
        if result is not None:
            results.append(result)
    return lineups.merge_lineup_stats(results)
