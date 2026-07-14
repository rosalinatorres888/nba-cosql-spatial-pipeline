"""
NBA CSV → PostgreSQL Loader
Purpose: Read Craig's CSV outputs from NBA_LoadData.ipynb and insert into PostgreSQL.
Usage:   python load_csvs_to_db.py --season 2023-24 --season-type "Regular Season"
         python load_csvs_to_db.py --season 2024-25 --season-type Playoffs
"""

import os
import argparse
import pandas as pd
import psycopg2
from psycopg2.extras import execute_values
from dotenv import load_dotenv

load_dotenv()

DB_HOST     = os.getenv("DB_HOST", "localhost")
DB_PORT     = os.getenv("DB_PORT", "5432")
DB_NAME     = os.getenv("DB_NAME", "nba_spatial")
DB_USER     = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")


def connect():
    conn = psycopg2.connect(
        host=DB_HOST, port=DB_PORT,
        database=DB_NAME, user=DB_USER, password=DB_PASSWORD
    )
    print(f"✅ Connected to {DB_NAME} on {DB_HOST}:{DB_PORT}")
    return conn


def csv_path(name, season, season_type):
    """Build filename matching Craig's naming convention."""
    return f"{name}_{season}_{season_type}.csv"


def load_players(cursor, season, season_type):
    path = csv_path("players", season, season_type)
    if not os.path.exists(path):
        print(f"⚠️  {path} not found — skipping players")
        return 0

    df = pd.read_csv(path)
    # Craig's static players CSV: id, full_name, first_name, last_name, is_active
    rows = [
        (
            row["id"],
            row["full_name"],
            None,   # team not in static players list
            None,   # position not in static players list
            None,   # height
            None,   # weight
            None,   # draft_year
        )
        for _, row in df.iterrows()
    ]
    execute_values(cursor,
        """INSERT INTO players (player_id, name, team, position, height, weight, draft_year)
           VALUES %s ON CONFLICT (player_id) DO NOTHING""",
        rows)
    print(f"  ✅ players: {len(rows)} rows")
    return len(rows)


def load_games(cursor, season, season_type):
    path = csv_path("games", season, season_type)
    if not os.path.exists(path):
        print(f"⚠️  {path} not found — skipping games")
        return 0

    df = pd.read_csv(path)
    df["GAME_ID"] = df["GAME_ID"].astype(str).str.zfill(10)

    # Derive season_type label from GAME_ID prefix: 002 = Regular, 004 = Playoffs
    def season_label(gid):
        if gid.startswith("004"):
            return "Playoffs"
        elif gid.startswith("002"):
            return "Regular Season"
        return season_type

    rows = [
        (
            row["GAME_ID"],
            row.get("GAME_DATE"),
            row.get("TEAM_NAME"),           # home/away not always distinct in LeagueGameFinder
            row.get("MATCHUP", "").replace(row.get("TEAM_ABBREVIATION", ""), "").strip("@ vs. "),
            "TBD",                          # venue not in API
            row.get("PTS"),
            season_label(row["GAME_ID"]),
        )
        for _, row in df.iterrows()
    ]
    execute_values(cursor,
        """INSERT INTO games (game_id, date, home_team, away_team, venue, score, season_type)
           VALUES %s ON CONFLICT (game_id) DO NOTHING""",
        rows)
    print(f"  ✅ games: {len(rows)} rows")
    return len(rows)


def load_shot_charts(cursor, season, season_type):
    path = csv_path("shot_charts", season, season_type)
    if not os.path.exists(path):
        print(f"⚠️  {path} not found — skipping shot_charts")
        return 0

    df = pd.read_csv(path)
    df["GAME_ID"] = df["GAME_ID"].astype(str).str.zfill(10)

    rows = [
        (
            row.get("GAME_EVENT_ID"),       # natural key with game_id — makes re-runs idempotent
            row.get("PLAYER_ID"),
            row["GAME_ID"],
            row.get("SHOT_TYPE"),
            row.get("LOC_X"),
            row.get("LOC_Y"),
            row.get("SHOT_DISTANCE"),
            row.get("SHOT_MADE_FLAG"),
            None,                           # defender not in shot chart API
            row.get("MINUTES_REMAINING"),   # clock queries need minutes_remaining * 60 + period_seconds_remaining
            row.get("SECONDS_REMAINING"),   # period time remaining — NOT shot clock
            row.get("PERIOD"),
        )
        for _, row in df.iterrows()
    ]
    execute_values(cursor,
        """INSERT INTO shot_charts
               (event_id, player_id, game_id, shot_type, x, y, distance,
                made_flag, defender, minutes_remaining, period_seconds_remaining, period)
           VALUES %s ON CONFLICT (game_id, event_id) DO NOTHING""",
        rows)
    print(f"  ✅ shot_charts: {len(rows)} rows")
    return len(rows)


def load_play_by_play(cursor, season, season_type):
    path = csv_path("playbyplay", season, season_type)
    if not os.path.exists(path):
        print(f"⚠️  {path} not found — skipping play_by_play")
        return 0

    df = pd.read_csv(path)
    df["GAME_ID"] = df["GAME_ID"].astype(str).str.zfill(10)

    rows = [
        (
            row.get("EVENTNUM"),
            row["GAME_ID"],
            row.get("ACTION_TYPE"),
            row.get("PCTIMESTRING"),        # game clock "MM:SS"
            str(row.get("PLAYER_ID", "")),
            None,                           # lineups not in API
            row.get("SCORE"),
        )
        for _, row in df.iterrows()
    ]
    execute_values(cursor,
        """INSERT INTO play_by_play
               (event_id, game_id, event_type, game_clock, player_ids, lineups, running_score)
           VALUES %s ON CONFLICT (game_id, event_id) DO NOTHING""",
        rows)
    print(f"  ✅ play_by_play: {len(rows)} rows")
    return len(rows)


def validate(cursor):
    print("\n📊 Row count validation:")
    for table in ["players", "games", "shot_charts", "play_by_play"]:
        cursor.execute(f"SELECT COUNT(*) FROM {table};")
        count = cursor.fetchone()[0]
        print(f"  {table}: {count:,} rows")


def main():
    parser = argparse.ArgumentParser(description="Load Craig's NBA CSVs into PostgreSQL")
    parser.add_argument("--season",      default="2023-24",        help='e.g. 2023-24')
    parser.add_argument("--season-type", default="Regular Season", help='Regular Season or Playoffs')
    parser.add_argument("--csv-dir",     default=".",              help="Directory containing Craig's CSVs")
    args = parser.parse_args()

    os.chdir(args.csv_dir)
    season      = args.season
    season_type = args.season_type

    print(f"\n{'='*60}")
    print(f"Loading {season} {season_type} into {DB_NAME}")
    print(f"{'='*60}\n")

    conn = connect()
    cursor = conn.cursor()

    try:
        load_players(cursor, season, season_type)
        load_games(cursor, season, season_type)
        load_shot_charts(cursor, season, season_type)
        load_play_by_play(cursor, season, season_type)
        conn.commit()
        validate(cursor)
        print("\n✅ Load complete")
    except Exception as e:
        conn.rollback()
        print(f"\n❌ Load failed: {e}")
        raise
    finally:
        cursor.close()
        conn.close()


if __name__ == "__main__":
    main()
