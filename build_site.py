"""
build_site.py - vygeneruje statický webový portál ze srsni.db.

Čte data přes db.py/aggregate.py/stats.py/lineups.py a vyrenderuje
statické HTML stránky (šablony v templates/, styl v static/) do
adresáře dist/ - ten se dá nasadit kamkoliv (GitHub Pages, jakýkoliv
statický hosting), žádný server na běh nepotřebuje.

Stránky:
- index.html            - přehled (aktuální sezóna, poslední/příští zápas)
- sezona/<slug>.html    - detail sezóny (bilance, zápasy, žebříčky, kombinace)
- zapasy/<nbl_id>.html  - detail zápasu (boxscore, kombinace jen za tenhle zápas)
- hraci/index.html      - seznam hráčů
- hraci/<slug>.html     - kariérní profil hráče

Spuštění: uv run python3 build_site.py
"""

from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from jinja2 import Environment, FileSystemLoader, select_autoescape

import aggregate
import db
import lineups
import stats

ROOT_DIR = Path(__file__).parent
OUTPUT_DIR = ROOT_DIR / "dist"
TEMPLATES_DIR = ROOT_DIR / "templates"
STATIC_DIR = ROOT_DIR / "static"

PRAGUE_TZ = ZoneInfo("Europe/Prague")

# Kolik pokusů ze hry musí hráč mít, aby se počítal do žebříčku
# efektivity střelby (ať tam nejsou náhodná 100 % ze dvou pokusů).
MIN_ATTEMPTS_FOR_SHOOTING_LEADERBOARD = 30


def season_slug(season: str) -> str:
    return season.replace("/", "-")


def fmt_date(iso: str | None) -> str:
    if not iso:
        return "?"
    dt = datetime.fromisoformat(iso).astimezone(PRAGUE_TZ)
    return dt.strftime("%-d. %-m. %Y %H:%M")


def opponent_name(match: db.Match) -> str:
    home = match.home_team or ""
    if "sršni" in home.lower():
        return match.away_team or "?"
    return home or "?"


def render(env: Environment, template_name: str, ctx: dict, out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    template = env.get_template(template_name)
    out_path.write_text(template.render(**ctx), encoding="utf-8")


def build_index_page(env: Environment, conn, current_season_ctx: dict, seasons_ctx: list[dict]) -> None:
    season_label = current_season_ctx["label"]
    record = aggregate.team_record(conn, season_label)
    for g in record.games:
        g.date_fmt = fmt_date(g.date_utc)
    last_result = record.games[-1] if record.games else None

    upcoming = sorted(
        (m for m in db.list_matches(conn, season=season_label) if m.status == "upcoming"),
        key=lambda m: m.date_utc or "",
    )
    next_match = None
    if upcoming:
        m = upcoming[0]
        next_match = {"nbl_id": m.nbl_id, "date_fmt": fmt_date(m.date_utc), "opponent": opponent_name(m)}

    top_scorers = aggregate.player_stats(conn, season_label)[:5]

    render(
        env,
        "index.html",
        {
            "root": "",
            "current_season": current_season_ctx,
            "all_seasons": seasons_ctx,
            "seasons": seasons_ctx,
            "record": record,
            "next_match": next_match,
            "last_result": last_result,
            "top_scorers": top_scorers,
        },
        OUTPUT_DIR / "index.html",
    )


def build_season_page(env: Environment, conn, season: str, current_season_ctx: dict, seasons_ctx: list[dict]) -> None:
    record = aggregate.team_record(conn, season)
    for g in record.games:
        g.date_fmt = fmt_date(g.date_utc)

    upcoming_ctx = sorted(
        (
            {"nbl_id": m.nbl_id, "date_fmt": fmt_date(m.date_utc), "opponent": opponent_name(m)}
            for m in db.list_matches(conn, season=season)
            if m.status == "upcoming"
        ),
        key=lambda u: u["date_fmt"],
    )

    players = aggregate.player_stats(conn, season)
    leaderboards = {
        "points": players[:10],
        "assists": sorted(players, key=lambda p: p.assists, reverse=True)[:10],
        "rebounds": sorted(players, key=lambda p: p.rebounds_total, reverse=True)[:10],
        "ts_pct": sorted(
            (p for p in players if p.field_goals_attempted >= MIN_ATTEMPTS_FOR_SHOOTING_LEADERBOARD),
            key=lambda p: p.true_shooting_pct or 0,
            reverse=True,
        )[:10],
    }

    lstats = aggregate.season_lineup_stats(conn, season)
    combos = {
        "pairs": lineups.top_combos(lstats.combo_points, size=2, limit=10),
        "trios": lineups.top_combos(lstats.combo_points, size=3, limit=10),
        "fives": lineups.top_combos(lstats.combo_points, size=5, limit=5),
        "assists": [
            (pair, count, lstats.assist_points.get(pair, 0))
            for pair, count in lineups.top_assist_pairs(lstats.assist_counts, limit=10)
        ],
    }

    render(
        env,
        "season.html",
        {
            "root": "../",
            "current_season": current_season_ctx,
            "all_seasons": seasons_ctx,
            "season": {"slug": season_slug(season), "label": season},
            "record": record,
            "games": record.games,
            "upcoming": upcoming_ctx,
            "leaderboards": leaderboards,
            "combos": combos,
        },
        OUTPUT_DIR / "sezona" / f"{season_slug(season)}.html",
    )


def build_match_page(env: Environment, conn, match: db.Match, current_season_ctx: dict, seasons_ctx: list[dict]) -> None:
    raw = db.get_latest_snapshot(conn, match.nbl_id)

    ctx = {
        "root": "../",
        "current_season": current_season_ctx,
        "all_seasons": seasons_ctx,
        "match": {
            "nbl_id": match.nbl_id,
            "home_team": match.home_team or "?",
            "away_team": match.away_team or "?",
            "season": match.season,
            "date_fmt": fmt_date(match.date_utc),
        },
        "final_score": None,
        "won": None,
        "teams": [],
        "match_combos": None,
    }

    if raw is not None:
        box = stats.parse_boxscore(raw)
        ordered_teams = sorted(box.teams, key=lambda t: 0 if t.name == match.home_team else 1)
        teams_ctx = []
        for team in ordered_teams:
            for p in team.players:
                p.slug = aggregate.slugify(p.full_name)
            teams_ctx.append({"name": team.name, "score": raw["tm"][team.team_id].get("score"), "players": team.players})
        ctx["teams"] = teams_ctx

        if len(teams_ctx) == 2 and (stats.is_match_finished(raw) or match.status == "finished"):
            srsni_team = next((t for t in teams_ctx if "sršni" in t["name"].lower()), None)
            opp_team = next((t for t in teams_ctx if t is not srsni_team), None)
            if srsni_team and opp_team:
                ctx["final_score"] = f"{srsni_team['score']}:{opp_team['score']}"
                ctx["won"] = srsni_team["score"] > opp_team["score"]

        lstats = lineups.analyze_pbp(raw)
        if lstats is not None and lstats.combo_points:
            ctx["match_combos"] = {
                "pairs": lineups.top_combos(lstats.combo_points, size=2, limit=5),
                "assists": [
                    (pair, count, lstats.assist_points.get(pair, 0))
                    for pair, count in lineups.top_assist_pairs(lstats.assist_counts, limit=5)
                ],
            }

    render(env, "match.html", ctx, OUTPUT_DIR / "zapasy" / f"{match.nbl_id}.html")


def build_player_pages(env: Environment, conn, current_season_ctx: dict, seasons: list[str], seasons_ctx: list[dict]) -> None:
    career_players = aggregate.player_stats(conn, season=None)
    slug_by_name = {p.name: p.player_id for p in career_players}
    career_lineup = aggregate.season_lineup_stats(conn, season=None)

    for p in career_players:
        seasons_data = []
        for season in seasons:
            season_players = aggregate.player_stats(conn, season)
            found = next((sp for sp in season_players if sp.name == p.name), None)
            if found:
                seasons_data.append((season, found))

        game_log = aggregate.player_game_log(conn, p.name, season=None)
        for g in game_log:
            g.date_fmt = fmt_date(g.date_utc)
        best_game = max(game_log, key=lambda g: g.points) if game_log else None
        recent_games = list(reversed(game_log))[:10]

        partner_points = sorted(
            (
                (combo[0] if combo[1] == p.name else combo[1], pts)
                for combo, pts in career_lineup.combo_points.items()
                if len(combo) == 2 and p.name in combo
            ),
            key=lambda item: item[1],
            reverse=True,
        )

        assist_links = sorted(
            (
                (pair[0] if pair[1] == p.name else pair[1], count, career_lineup.assist_points.get(pair, 0))
                for pair, count in career_lineup.assist_counts.items()
                if p.name in pair
            ),
            key=lambda item: item[1],
            reverse=True,
        )

        render(
            env,
            "player.html",
            {
                "root": "../",
                "current_season": current_season_ctx,
                "all_seasons": seasons_ctx,
                "player_name": p.name,
                "career": p,
                "seasons": seasons_data,
                "best_game": best_game,
                "recent_games": recent_games,
                "top_partners": partner_points[:8],
                "top_assist_links": assist_links[:8],
                "partner_slugs": slug_by_name,
            },
            OUTPUT_DIR / "hraci" / f"{p.player_id}.html",
        )

    render(
        env,
        "players_index.html",
        {
            "root": "../",
            "current_season": current_season_ctx,
            "all_seasons": seasons_ctx,
            "players": career_players,
        },
        OUTPUT_DIR / "hraci" / "index.html",
    )


def main() -> None:
    if OUTPUT_DIR.exists():
        shutil.rmtree(OUTPUT_DIR)
    OUTPUT_DIR.mkdir(parents=True)
    shutil.copytree(STATIC_DIR, OUTPUT_DIR / "static")

    env = Environment(loader=FileSystemLoader(TEMPLATES_DIR), autoescape=select_autoescape())

    with db.connect() as conn:
        seasons = aggregate.list_seasons(conn)
        if not seasons:
            print("Databáze neobsahuje žádnou sezónu, není co generovat.")
            return

        current_season_ctx = {"slug": season_slug(seasons[0]), "label": seasons[0]}
        seasons_ctx = [{"slug": season_slug(s), "label": s} for s in seasons]

        build_index_page(env, conn, current_season_ctx, seasons_ctx)

        for season in seasons:
            build_season_page(env, conn, season, current_season_ctx, seasons_ctx)

        for match in db.list_matches(conn):
            build_match_page(env, conn, match, current_season_ctx, seasons_ctx)

        build_player_pages(env, conn, current_season_ctx, seasons, seasons_ctx)

    print(f"Portál vygenerován do {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
