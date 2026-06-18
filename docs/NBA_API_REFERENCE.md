# nba_api Reference Guide for T2

**Purpose:** Help Craig fill in the TODO sections in `collect_nba_data.py`

---

## Installation

```bash
pip install nba-api
```

---

## 1. Fetching Games (LeagueGameFinder)

**What it does:** Get all games for a specific team in a season

```python
from nba_api.stats.endpoints import leaguegamefinder

games = leaguegamefinder.LeagueGameFinder(
    season_nullable=2023,
    team_id_nullable=1610612738  # Celtics
).get_data_frames()[0]

# Returns DataFrame with columns:
# GAME_ID, GAME_DATE, HOME_TEAM_ID, AWAY_TEAM_ID, HOME_TEAM_NAME, AWAY_TEAM_NAME, WL, POINTS, etc.

# Filter to only regular season + playoffs (not preseason)
games = games[games['GAME_DATE'].notna()]
print(f"Found {len(games)} games")
```

---

## 2. Fetching Roster (CommonTeamRoster)

**What it does:** Get all players on a team

```python
from nba_api.stats.endpoints import commonteamroster

roster = commonteamroster.CommonTeamRoster(
    season=2023,
    team_id=1610612738  # Celtics
).get_data_frames()[0]

# Returns DataFrame with columns:
# PLAYER_ID, PLAYER_NAME, NICKNAME, JERSEY_NUMBER, POSITION, HEIGHT, WEIGHT, BIRTHDATE, DRAFT_YEAR, DRAFT_ROUND, DRAFT_NUMBER, etc.

players = roster[['PLAYER_ID', 'PLAYER_NAME', 'POSITION', 'HEIGHT', 'WEIGHT', 'DRAFT_YEAR']]
print(f"Found {len(players)} players")
```

---

## 3. Fetching Shot Charts (ShotChartDetail)

**What it does:** Get all shots for a player in a game (or across season)

```python
from nba_api.stats.endpoints import shotchartdetail

# For a specific game:
shots = shotchartdetail.ShotChartDetail(
    team_id=1610612738,        # Celtics
    player_id=0,               # 0 = all players
    game_id_flag='Y',
    game_id='0022300010',      # Must be 10-digit format
).get_data_frames()[0]

# Returns DataFrame with columns:
# PLAYER_ID, PLAYER_NAME, GAME_ID, GAME_EVENT_ID, PERIOD, MINUTES_REMAINING, SECONDS_REMAINING,
# X, Y, SHOT_TYPE (2PT Field Goal, 3PT Field Goal), SHOT_DISTANCE, SHOT_MADE_FLAG,
# GAME_DATE, HOME_TEAM_ID, AWAY_TEAM_ID, SEASON_ID

# Key columns for your schema:
# x, y: court coordinates (-250 to +250 on each axis)
# shot_type: '2PT Field Goal' or '3PT Field Goal'
# shot_distance: distance in feet
# shot_made_flag: 0 or 1 (missed or made)
# defender: Not directly in shot chart; may be in play-by-play instead

print(f"Found {len(shots)} shots in game")
```

---

## 4. Fetching Play-by-Play (PlayByPlayV3)

**What it does:** Get all events in a game (shots, fouls, turnovers, etc.)

```python
from nba_api.stats.endpoints import playbyplayv3

plays = playbyplayv3.PlayByPlayV3(
    game_id='0022300010'  # 10-digit game ID
).get_data_frames()[0]

# Returns DataFrame with columns:
# GAME_ID, EVENTNUM, PERIOD, WCTIMESTRING (game clock), PCTIMESTRING, 
# ACTION_TYPE, PLAYER_ID, PLAYER_NAME, TEAM_ID, TEAM_NAME, HOME_DESCRIPTION, 
# NEUTRAL_DESCRIPTION, VISITOR_DESCRIPTION, SCORE, etc.

# Game clock format: "MM:SS" (e.g., "11:45" = 11:45 remaining in period)

print(f"Found {len(plays)} events in game")
```

---

## 5. Game ID Format

**Important:** NBA game IDs are 10 digits: `YYYYMMDDXX`

Example: `0022300010`
- `00` = season (2023-24 season ID prefix)
- `223` = season year (2023)
- `00010` = game number

**How to extract from games DataFrame:**

```python
# leaguegamefinder returns GAME_ID as integer
# Convert to 10-digit string:
game_id = str(games.iloc[0]['GAME_ID']).zfill(10)
print(game_id)  # e.g., '0022300010'
```

---

## 6. Celtics Team ID

```python
CELTICS_TEAM_ID = 1610612738
```

---

## 7. Complete Example Loop

```python
from nba_api.stats.endpoints import leaguegamefinder, shotchartdetail

# Get all Celtics games
games = leaguegamefinder.LeagueGameFinder(
    season_nullable=2023,
    team_id_nullable=1610612738
).get_data_frames()[0]

all_shots = []

for i, row in games.iterrows():
    game_id = str(row['GAME_ID']).zfill(10)
    
    try:
        shots = shotchartdetail.ShotChartDetail(
            team_id=1610612738,
            player_id=0,
            game_id_flag='Y',
            game_id=game_id,
        ).get_data_frames()[0]
        
        all_shots.append(shots)
        
        if (i + 1) % 10 == 0:
            print(f"Progress: {i + 1}/{len(games)} games")
    except Exception as e:
        print(f"Warning: Could not fetch game {game_id}: {e}")
        continue

# Combine all shots
import pandas as pd
all_shots_df = pd.concat(all_shots, ignore_index=True)
print(f"Total shots: {len(all_shots_df)}")
```

---

## 8. Rate Limiting

⚠️ **Important:** nba_api has rate limiting. Add delays between requests:

```python
import time

for i, row in games.iterrows():
    # ... fetch data ...
    time.sleep(0.5)  # 0.5 second delay between requests
```

---

## 9. Mapping to Your Schema

**Your tables need:**

```
players (player_id, name, team, position, height, weight, draft_year)
├─ player_id: from roster PLAYER_ID
├─ name: from roster PLAYER_NAME
├─ team: "BOS" (hardcode)
├─ position: from roster POSITION
├─ height: from roster HEIGHT
├─ weight: from roster WEIGHT
└─ draft_year: from roster DRAFT_YEAR

games (game_id, date, home_team, away_team, venue, score, season_type)
├─ game_id: from leaguegamefinder GAME_ID
├─ date: from leaguegamefinder GAME_DATE
├─ home_team: from leaguegamefinder HOME_TEAM_NAME
├─ away_team: from leaguegamefinder AWAY_TEAM_NAME
├─ venue: "TBD" (not in API, use placeholder)
├─ score: from leaguegamefinder POINTS
└─ season_type: "Regular" or "Playoff" (parse from GAME_ID or use context)

shot_charts (player_id, game_id, shot_type, x, y, distance, made_flag, defender, shot_clock, period)
├─ player_id: from shotchartdetail PLAYER_ID
├─ game_id: from shotchartdetail GAME_ID
├─ shot_type: from shotchartdetail SHOT_TYPE
├─ x, y: from shotchartdetail X, Y
├─ distance: from shotchartdetail SHOT_DISTANCE
├─ made_flag: from shotchartdetail SHOT_MADE_FLAG
├─ defender: "TBD" (not in shot chart API, use NULL or extract from play-by-play)
├─ shot_clock: from shotchartdetail SECONDS_REMAINING (in period)
└─ period: from shotchartdetail PERIOD

play_by_play (event_id, game_id, event_type, game_clock, player_ids, lineups, running_score)
├─ event_id: from playbyplayv3 EVENTNUM
├─ game_id: from playbyplayv3 GAME_ID
├─ event_type: from playbyplayv3 ACTION_TYPE
├─ game_clock: from playbyplayv3 WCTIMESTRING (convert to seconds)
├─ player_ids: from playbyplayv3 PLAYER_ID (may be JSON array)
├─ lineups: "TBD" (not directly in API)
└─ running_score: from playbyplayv3 SCORE
```

---

## 10. Debugging Tips

```python
# Check column names
print(games.columns.tolist())

# Check data types
print(games.dtypes)

# Check first few rows
print(games.head())

# Check for nulls
print(games.isnull().sum())

# Check unique values
print(games['SEASON_ID'].unique())
```

---

**Next Step:** Fill in the `TODO` sections in `collect_nba_data.py` using these examples, then run it!
