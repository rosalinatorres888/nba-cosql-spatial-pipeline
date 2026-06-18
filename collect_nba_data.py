"""
CoSQL NBA Data Collection Script
Purpose: Fetch Celtics 2023-24 data from nba_api and load into PostgreSQL
Owner: Craig Habel
Due: Jun 5, 2026 (T2)

TODO:
1. Install nba_api: pip install nba-api
2. Set up PostgreSQL database (T1 prerequisite)
3. Fill in DATABASE_URL below
4. Run this script
5. Verify row counts match expectations (T3 gate)
"""

import os
import time
from dotenv import load_dotenv
import psycopg2
from psycopg2.extras import execute_values
import pandas as pd
from nba_api.stats.endpoints import shotchartdetail, playbyplayv3, commonteamroster, leaguegamefinder

# Load environment variables
load_dotenv()

# TODO: Set these from .env or hardcode for testing
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "nba_spatial")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")

CELTICS_TEAM_ID = 1610612738  # Boston Celtics
SEASON = '2023-24'  # season string format required by nba_api


def connect_to_db():
    """Connect to PostgreSQL database."""
    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD
        )
        print(f"✅ Connected to {DB_NAME} on {DB_HOST}:{DB_PORT}")
        return conn
    except psycopg2.OperationalError as e:
        print(f"❌ Failed to connect to database: {e}")
        print("Make sure PostgreSQL is running and T1 schema is created.")
        raise


def fetch_games(conn):
    """
    Fetch all Celtics games for 2023-24 season.
    Returns: list of game_ids
    """
    print("\n📥 Fetching Celtics games for 2023-24 season...")

    # TODO: Use nba_api to fetch games where Celtics played
    # Hint: leaguegamefinder endpoint
    # Filter: season=2023, season_type='Regular Season' + 'Playoffs'
    # Save game_ids for later shot chart fetching

    try:
        games = leaguegamefinder.LeagueGameFinder(
            season_nullable=SEASON,
            team_id_nullable=CELTICS_TEAM_ID
        ).get_data_frames()[0]

        # Filter out preseason (GAME_ID prefix '001' = preseason, '002' = regular, '004' = playoffs)
        games = games[games['GAME_DATE'].notna()].copy()
        games['GAME_ID'] = games['GAME_ID'].apply(lambda x: str(x).zfill(10))
        print(f"Found {len(games)} games for Celtics in 2023-24")
        return games
    except Exception as e:
        print(f"❌ Error fetching games: {e}")
        raise


def fetch_players():
    """
    Fetch all NBA players for 2023-24 season using static list.
    Using full league list avoids FK violations when shot charts include opposing players.
    Returns: DataFrame with player info
    """
    print("\n📥 Fetching all NBA players (static list)...")

    try:
        from nba_api.stats.static import players as nba_players
        all_players = nba_players.get_players()
        players = pd.DataFrame(all_players)
        # Static list columns: id, full_name, first_name, last_name, is_active
        players = players.rename(columns={'id': 'PLAYER_ID', 'full_name': 'PLAYER_NAME'})
        players['TEAM'] = None
        players['POSITION'] = None
        players['HEIGHT'] = None
        players['WEIGHT'] = None
        players['DRAFT_YEAR'] = None
        print(f"Found {len(players)} players in NBA static list")
        return players
    except Exception as e:
        print(f"❌ Error fetching players: {e}")
        raise


def fetch_shot_charts(conn, games):
    """
    Fetch shot chart data for all Celtics games.

    Bug 12 (resolved): ShotChartDetail silently returns 0 shots when game_id_nullable
    is a playoff game ID (004xxxxxxx). The fix is to fetch regular season and playoff
    shots in two separate calls using season_type_all_star, then concatenate.
    Do NOT loop over individual game IDs for playoff games.

    Returns: DataFrame with shot-level data
    """
    print("\n📥 Fetching shot charts...")

    all_shots = []

    # Regular season: fetch game-by-game (game_id_nullable works for 002xxxxxxx)
    regular_games = games[games['GAME_ID'].str.startswith('002')]
    print(f"  Fetching {len(regular_games)} regular season games...")
    for i, (_, game) in enumerate(regular_games.iterrows()):
        game_id = game['GAME_ID']
        try:
            shots = shotchartdetail.ShotChartDetail(
                team_id=CELTICS_TEAM_ID,
                player_id=0,
                game_id_nullable=game_id,
                season_nullable=SEASON,
                context_measure_simple='FGA',
            ).get_data_frames()[0]
            all_shots.append(shots)
            time.sleep(0.5)
            if (i + 1) % 10 == 0:
                print(f"  Regular season progress: {i + 1}/{len(regular_games)}...")
        except Exception as e:
            print(f"⚠️  Warning: Could not fetch shots for game {game_id}: {e}")
            continue

    # Playoff shots: must use season_type_all_star='Playoffs' — game_id_nullable blocks results
    playoff_games = games[games['GAME_ID'].str.startswith('004')]
    if len(playoff_games) > 0:
        print(f"  Fetching playoff shots (single call for all {len(playoff_games)} playoff games)...")
        try:
            playoff_shots = shotchartdetail.ShotChartDetail(
                team_id=CELTICS_TEAM_ID,
                player_id=0,
                season_nullable=SEASON,
                season_type_all_star='Playoffs',
                context_measure_simple='FGA',
            ).get_data_frames()[0]
            all_shots.append(playoff_shots)
            print(f"  Found {len(playoff_shots)} playoff shot attempts")
        except Exception as e:
            print(f"⚠️  Warning: Could not fetch playoff shots: {e}")

    shot_data = pd.concat(all_shots, ignore_index=True) if all_shots else pd.DataFrame()
    print(f"Found {len(shot_data)} total shot attempts")
    return shot_data


def fetch_play_by_play(conn, games):
    """
    Fetch play-by-play data for all Celtics games.
    Returns: DataFrame with play-by-play events
    """
    print("\n📥 Fetching play-by-play data...")

    all_plays = []

    for i, (_, game) in enumerate(games.iterrows()):
        game_id = game['GAME_ID']

        try:
            plays = playbyplayv3.PlayByPlayV3(
                game_id=game_id
            ).get_data_frames()[0]

            all_plays.append(plays)
            time.sleep(0.5)  # rate limiting

            if (i + 1) % 10 == 0:
                print(f"  Progress: {i + 1}/{len(games)} games...")
        except Exception as e:
            print(f"⚠️  Warning: Could not fetch plays for game {game_id}: {e}")
            continue

    play_data = pd.concat(all_plays, ignore_index=True) if all_plays else pd.DataFrame()
    print(f"Found {len(play_data)} play-by-play events")
    return play_data


def load_into_db(conn, players, games, shots, plays):
    """
    Load all data into PostgreSQL tables.
    Assumes schema is already created (T1 prerequisite).
    """
    cursor = conn.cursor()

    try:
        print("\n📤 Loading data into PostgreSQL...")

        # Players
        if players is not None and len(players) > 0:
            player_rows = [
                (int(row['PLAYER_ID']), row['PLAYER_NAME'], row.get('TEAM'),
                 row.get('POSITION'), row.get('HEIGHT'), row.get('WEIGHT'), row.get('DRAFT_YEAR'))
                for _, row in players.iterrows()
            ]
            execute_values(cursor,
                """INSERT INTO players (player_id, name, team, position, height, weight, draft_year)
                   VALUES %s ON CONFLICT (player_id) DO NOTHING""",
                player_rows)
            print(f"  Loaded {len(player_rows)} players")

        # Games — MATCHUP format: "BOS vs. LAL" (home) or "BOS @ LAL" (away)
        # home_team/away_team derived from MATCHUP; HOME_TEAM_NAME not in LeagueGameFinder response
        if games is not None and len(games) > 0:
            def parse_teams(row):
                matchup = row.get('MATCHUP', '') or ''
                team = row.get('TEAM_NAME', '') or ''
                if 'vs.' in matchup:
                    opponent = matchup.split('vs.')[-1].strip()
                    return team, opponent  # home, away
                elif '@' in matchup:
                    opponent = matchup.split('@')[-1].strip()
                    return opponent, team  # home, away
                return None, None
            game_rows = [
                (row['GAME_ID'], row.get('GAME_DATE'),
                 parse_teams(row)[0], parse_teams(row)[1],
                 'TBD', row.get('POINTS'),
                 'Regular' if str(row['GAME_ID']).startswith('002') else ('Playoff' if str(row['GAME_ID']).startswith('004') else 'Preseason'))
                for _, row in games.iterrows()
            ]
            execute_values(cursor,
                """INSERT INTO games (game_id, date, home_team, away_team, venue, score, season_type)
                   VALUES %s ON CONFLICT (game_id) DO NOTHING""",
                game_rows)
            print(f"  Loaded {len(game_rows)} games")

        # Shot charts — MINUTES_REMAINING + SECONDS_REMAINING are MM:SS clock components (not shot clock)
        # Total seconds left in period = minutes_remaining * 60 + period_seconds_remaining
        if shots is not None and len(shots) > 0:
            shot_rows = [
                (row['PLAYER_ID'], row['GAME_ID'], row['SHOT_TYPE'],
                 row['LOC_X'], row['LOC_Y'], row['SHOT_DISTANCE'],
                 row['SHOT_MADE_FLAG'], None,  # defender: not in shot chart API
                 row.get('MINUTES_REMAINING'),
                 row.get('SECONDS_REMAINING'),
                 row['PERIOD'])
                for _, row in shots.iterrows()
            ]
            execute_values(cursor,
                """INSERT INTO shot_charts (player_id, game_id, shot_type, x, y, distance, made_flag, defender, minutes_remaining, period_seconds_remaining, period)
                   VALUES %s""",
                shot_rows)
            print(f"  Loaded {len(shot_rows)} shot attempts")

        # Play-by-play
        if plays is not None and len(plays) > 0:
            # PlayByPlayV3 uses camelCase columns: gameId, actionNumber, actionType, clock, personId
            play_rows = [
                (row.get('actionNumber'), str(row.get('gameId', '')).zfill(10),
                 row.get('actionType'), row.get('clock'),
                 str(row.get('personId', '')),
                 None,  # lineups: not in API
                 str(row.get('scoreHome', '')) + '-' + str(row.get('scoreAway', '')))
                for _, row in plays.iterrows()
            ]
            execute_values(cursor,
                """INSERT INTO play_by_play (event_id, game_id, event_type, game_clock, player_ids, lineups, running_score)
                   VALUES %s""",
                play_rows)
            print(f"  Loaded {len(play_rows)} play-by-play events")

        conn.commit()
        print("✅ Data loaded successfully")

    except Exception as e:
        conn.rollback()
        print(f"❌ Error loading data: {e}")
        raise
    finally:
        cursor.close()


def validate_row_counts(conn):
    """
    Verify that row counts match expectations.
    This is the T3 validation gate.
    """
    cursor = conn.cursor()

    print("\n✅ Validating row counts (T3 gate)...")

    try:
        # Expected counts (from PRD):
        expected = {
            'players': 600,        # ~600 players
            'games': 50,           # 50-game subset
            'shot_charts': 25000,  # ~25,000 shots in 50 games
            'play_by_play': 100000 # ~100,000 events in 50 games
        }

        for table, expected_count in expected.items():
            cursor.execute(f"SELECT COUNT(*) FROM {table};")
            actual_count = cursor.fetchone()[0]

            status = "✅" if actual_count >= expected_count * 0.8 else "⚠️"
            print(f"{status} {table}: {actual_count} rows (expected ~{expected_count})")

        cursor.close()

    except Exception as e:
        print(f"❌ Error validating row counts: {e}")
        raise


def main():
    """Main execution flow."""
    print("=" * 70)
    print("CoSQL NBA Data Collection — T2")
    print("=" * 70)

    conn = None
    try:
        # Connect to database
        conn = connect_to_db()

        # Fetch all data
        games = fetch_games(conn)
        players = fetch_players()
        shots = fetch_shot_charts(conn, games)
        plays = fetch_play_by_play(conn, games)

        # Load into database
        load_into_db(conn, players, games, shots, plays)

        # Validate
        validate_row_counts(conn)

        print("\n" + "=" * 70)
        print("✅ T2 COMPLETE — Data collection successful")
        print("Next: T3 (Row count + FK verification) due Jun 8–10")
        print("=" * 70)

    except Exception as e:
        print(f"\n❌ FAILED: {e}")
        raise
    finally:
        if conn:
            conn.close()


if __name__ == "__main__":
    main()
