# Query Classes & Clarify Templates

**CoSQL NBA Spatial · IE7500 · WOZ Annotation Protocol**

[CoSQL Annotation Guide](https://tinyurl.com/NL-Annotation-Guide)

[CoSQL_NBA_WOZ_Annotation Tracker](https://tinyurl.com/CoSQL-NBA-WOZ-Annotations)

[Annotation Review Tool](https://tinyurl.com/Annotation-Review-Tool)

This document defines the 8 query classes and clarification templates used in annotation. All training pairs (120–150 total) must be distributed across these classes with a minimum of 15 pairs per class.

---

## Part 1: The 8 Query Classes

### **Query Class Distribution Target**
- **Total pairs:** 120–150
- **Per class minimum:** 15 pairs
- **Distribution:** Balanced across all 8 (aim for 18–20 per class if possible)

---

### **Class 1: Spatial Zone**

**Description:** Queries filtered by court location (corner, paint, arc, etc.).

**Natural Language Patterns:**
- "Shots from the left corner"
- "3-pointers above the break"
- "Attempts in the paint"
- "Restricted area layups"
- "Mid-range shots"

**SQL Pattern:**
```sql
-- NOTE: x and y (LOC_X, LOC_Y) are in tenths of feet. distance (SHOT_DISTANCE) is in whole feet.
-- Do NOT mix units — e.g. distance > 22 (feet), not distance > 220.
WHERE (x <= -220 AND y <= 90)              -- Left corner 3  (x/y in tenths of feet)
   OR (x >= 220 AND y <= 90)               -- Right corner 3
   OR (y > 90 AND distance > 22)           -- Above the break (distance in feet)
   OR (ABS(x) <= 80 AND y <= 190)          -- In the paint
   OR (distance BETWEEN 8 AND 22)          -- Mid-range (feet)
```

**Annotation Notes:**
- Validate zone definitions against NBA coordinate system
- Check that x/y bounds match the lexicon
- Common error: confusing "corner 3" (x ≤ −220, y ≤ 90) with "above the break" (y > 90)

**Target: 18 pairs**

---

### **Class 2: Temporal Scope**

**Description:** Queries filtered by time (period, game clock, game date, season type).

**Natural Language Patterns:**
- "In Q4"
- "With less than 1 minute remaining"
- "During the final 2 minutes of the game"
- "In the playoffs"
- "Against the Lakers on December 15th"

**SQL Pattern:**
```sql
WHERE period = 4
   AND game_clock ≤ 60
   AND season_type = 'Playoffs'
   AND DATE(game_date) = '2023-12-15'
```

**Annotation Notes:**
- **Clarify ambiguity:** "In Q4" could mean "Q4 of a specific game" or "all Q4s in the season"
  - Template: "Do you mean Q4 of a specific game or all Q4 periods this season?"
- Shot clock vs. game clock (different columns)
- Period ranges: 1–4 for regulation, 5+ for OT

**Target: 18 pairs**

---

### **Class 3: Player/Entity Filtering**

**Description:** Queries about a specific player or lineup.

**Natural Language Patterns:**
- "Jayson Tatum's shots"
- "By the starting five"
- "Attempts from players with >10 wins shares"
- "Defenders with <2 blocks"

**SQL Pattern:**
```sql
WHERE player_id IN (SELECT player_id FROM players WHERE name = 'Jayson Tatum')
   OR player_id IN (SELECT player_id FROM advanced_stats WHERE win_shares > 10)
```

**Annotation Notes:**
- **Clarify ambiguity:** Player nicknames ("JT", "The Hawk") need resolution
  - Template: "Did you mean [Full Name] or is [Nickname] another name for them?"
- Plural references: "shots by the starting lineup" requires lineup join
- Entity alias: resolve pronouns ("his shots" → identify player from context)

**Target: 18 pairs**

---

### **Class 4: Simple Aggregation**

**Description:** Basic count, sum, or single-metric queries (no grouping or comparison).

**Natural Language Patterns:**
- "How many shots did Tatum take?"
- "Total 3-pointers made"
- "Count of attempts"
- "How many games in the dataset?"

**SQL Pattern:**
```sql
SELECT COUNT(*) FROM shot_charts WHERE player_id = 123
SELECT SUM(CASE WHEN made_flag = 1 THEN 1 ELSE 0 END) FROM shot_charts WHERE shot_type = '3PT'
```

**Annotation Notes:**
- **Clarify ambiguity:** Made vs. attempted
  - Template: "Do you want attempts or only made shots?"
- Distinguish COUNT(*) from COUNT(DISTINCT player_id)
- Check for appropriate aggregate function (COUNT vs. SUM vs. AVG)

**Target: 18 pairs**

---

### **Class 5: Comparative Aggregation**

**Description:** Conditional or comparative queries with grouping, HAVING, or comparison operators.

**Natural Language Patterns:**
- "More made than missed?"
- "Shooting percentage above 40%"
- "Players with >100 attempts"
- "Games where the Celtics won by >10 points"
- "Periods where he shot better than 50%"

**SQL Pattern:**
```sql
SELECT player_id, COUNT(CASE WHEN made_flag = 1 THEN 1 END) as makes
FROM shot_charts
GROUP BY player_id
HAVING COUNT(*) > 100

SELECT period, 
       CAST(SUM(CASE WHEN made_flag = 1 THEN 1 ELSE 0 END) AS FLOAT) / COUNT(*) as pct
FROM shot_charts
GROUP BY period
HAVING CAST(SUM(CASE WHEN made_flag = 1 THEN 1 ELSE 0 END) AS FLOAT) / COUNT(*) > 0.40
```

**Annotation Notes:**
- **Clarify ambiguity:** Percentage vs. raw count
  - Template: "Do you want the percentage (e.g., 45%) or the raw count (e.g., 45 makes)?"
- Verify HAVING clause correctly filters grouped results
- Common error: wrong comparison operator (e.g., `>` vs. `≥`)

**Target: 18 pairs**

---

### **Class 6: Multi-Turn Coreference**

**Description:** Questions that reference prior turns (pronouns, implicit references, clarifications).

**Natural Language Patterns (Turn 2+):**
- Turn 1: "How many shots did Tatum take from the left corner in Q4?"
- Turn 2: "What about his 3-pointers?" (resolve "his" → Tatum, add 3PT filter)
- Turn 3: "In the playoffs?" (resolve temporal context from prior turn)

**SQL Pattern:**
```sql
-- Turn 1:
SELECT COUNT(*) FROM shot_charts 
WHERE player_id = 123 AND x ≤ -220 AND y ≤ 90 AND period = 4

-- Turn 2 (implicit: same player + same period, add 3PT):
SELECT COUNT(*) FROM shot_charts 
WHERE player_id = 123 AND shot_type = '3PT' AND x ≤ -220 AND y ≤ 90 AND period = 4
```

**Annotation Notes:**
- **Requires multi-turn annotation:** Each pair is a (Turn N, Turn N+1) sequence
- Memory manager must inject prior turn context into prompt
- Common error: failing to carry forward player/time filters
- State label: "coreference_resolved" or "coreference_failed"

**Target: 15 pairs** (lower priority; save for final annotation waves)

---

### **Class 7: Game/Matchup Context**

**Description:** Queries about a specific game or opponent.

**Natural Language Patterns:**
- "In the Celtics-Lakers game"
- "Against teams with a winning record"
- "In home games"
- "Against the Heat in 2023"

**SQL Pattern:**
```sql
SELECT * FROM shot_charts 
WHERE game_id IN (
  SELECT game_id FROM games 
  WHERE (home_team = 'BOS' AND away_team = 'LAL') 
    OR (home_team = 'LAL' AND away_team = 'BOS')
)

SELECT * FROM shot_charts 
WHERE game_id IN (
  SELECT game_id FROM games 
  WHERE home_team = 'BOS' AND YEAR(game_date) = 2023
)
```

**Annotation Notes:**
- **Clarify ambiguity:** Team name normalization (Lakers vs. LAL vs. Los Angeles)
  - Template: "Did you mean the Los Angeles Lakers (LAL)?"
- Join required: shots → games table
- Home vs. away: context-dependent ("against" suggests opponent perspective)

**Target: 18 pairs**

---

### **Class 8: Shot Characteristics**

**Description:** Queries filtered by shot properties (contested, distance, defender, clock).

**Natural Language Patterns:**
- "Shots with <5 seconds on the clock"
- "Contested attempts"
- "Shots against a defender"
- "Attempts beyond 30 feet"
- "Undefended attempts"

**SQL Pattern:**
```sql
-- nba_api does NOT provide shot-clock time directly.
-- SECONDS_REMAINING in shot_charts = time left in the PERIOD (not shot clock).
-- Use period_seconds_remaining for period-time filters; no shot_clock column exists.
WHERE period_seconds_remaining < 5 AND defender IS NOT NULL  -- "last 5 seconds of the period"
WHERE shot_distance > 30
WHERE shot_distance BETWEEN 20 AND 25 AND defender IS NULL
```

**Annotation Notes:**
- **CRITICAL: No shot_clock column.** nba_api's `SECONDS_REMAINING` is period time remaining, not shot-clock time. The column is stored as `period_seconds_remaining` in shot_charts. Any NL query referencing "shot clock" must be flagged as `state: clarification_needed` — ask the user whether they mean period time or shot-clock time, and note that shot-clock data is unavailable.
- **Clarify ambiguity:** "Close" shots — distance boundaries
  - Template: "By 'close,' do you mean within 10 feet, 15 feet, or the restricted area?"
- Contested vs. defended: check column definitions
- Common error: confusing period_seconds_remaining (time left in period from nba_api) with shot clock (unavailable in this dataset)

**Target: 18 pairs**

---

## Part 2: Clarify Templates

These are disambiguation questions the system should ask when it detects ambiguity. Use these in prompt engineering.

---

### **Category 1: Entity Alias (Player Names)**

When a player reference is ambiguous or uses alternate forms:

| Ambiguity | Template | Example |
|-----------|----------|---------|
| Nickname vs. full name | "Did you mean [Full Name] or is [Nickname] an alternate name?" | "Did you mean Jayson Tatum, or is JT the same person?" |
| Similar names | "Did you refer to [Player A] or [Player B]?" | "Did you mean Robert Williams III or Robert Williams Jr.?" |
| Team abbreviation | "Did you mean the [Team Name] or a specific player?" | "Did you mean the Celtics or a player on the Celtics?" |
| Plural vs. singular | "Do you mean [Single Player] or the entire [Team]?" | "Do you mean Derrick White or the whole Celtics roster?" |
| Pronoun (he/she/his/her) | "Who does 'his' refer to — [Player Name]?" | "When you say 'his shots,' do you mean Tatum's shots?" |

**Annotation Instruction:** If the NL utterance uses a name not in the players table or a pronoun, mark as `state: "clarification_needed"` until disambiguated.

---

### **Category 2: Temporal Scope (Time References)**

When time reference is unclear or could apply to multiple levels (game vs. season vs. period):

| Ambiguity | Template | Example |
|-----------|----------|---------|
| Game vs. season | "Do you mean in the [Specific Game] or across all [Time Period] games?" | "In the Lakers game or the entire 2023–24 season?" |
| Period vs. game | "Do you mean [Period] only or the entire [Game]?" | "In Q4 only or the whole game?" |
| Specific time range | "Do you mean the last [X] [unit] of [Period] or all of [Period]?" | "Last 2 minutes of Q4 or all of Q4?" |
| Season type (regular vs. playoffs) | "Do you mean [Regular/Playoff] season games or both?" | "In the regular season or including playoffs?" |
| Date or range | "Do you mean [Specific Date] or a date range?" | "On December 15th or the whole month of December?" |

**Annotation Instruction:** If temporal scope is ambiguous, ask for clarification before generating SQL. Mark as `state: "clarification_needed"` until resolved.

---

### **Category 3: Metric Definition (Aggregation Type)**

When the type of aggregation or metric is unclear:

| Ambiguity | Template | Example |
|-----------|----------|---------|
| Made vs. attempted | "Do you want [Attempts/Makes]?" | "How many 3-pointers — attempts or makes?" |
| Percentage vs. count | "Do you want the percentage (e.g., 45%) or the raw count (e.g., 45)?" | "Shooting efficiency — percentage or total makes?" |
| Individual vs. team | "Stats for [Single Player] or the [Team] total?" | "Tatum's points or the whole Celtics team?" |
| Per-game vs. total | "Do you mean per-game average or total for the season?" | "Average points per game or total points?" |
| Unique vs. all | "Do you mean unique [Entities] or all instances?" | "Unique defenders or all defensive instances?" |

**Annotation Instruction:** If metric type is ambiguous, resolve before writing SQL. Mark as `state: "metric_ambiguous"` if unresolved.

---

### **Category 4: Spatial Zone (Court Location)**

When court location is ambiguous or uses informal language:

| Ambiguity | Template | Example |
|-----------|----------|---------|
| Left vs. right | "[Left/Right] corner?" | "Corner 3 — which side?" |
| In the paint vs. restricted area | "Full paint or restricted area under the basket?" | "In the paint — do you mean the full lane or just the restricted zone?" |
| 3-point line vs. beyond arc | "At the 3-point line or beyond it?" | "Above the break or inside the arc?" |
| "Close" or "near" | "Do you mean within [X feet]?" | "By 'close to the basket,' do you mean <10 feet?" |
| "Deep" or "far" | "Do you mean beyond [X feet]?" | "By 'deep 3,' do you mean >28 feet?" |

**Annotation Instruction:** Inject the spatial zone lexicon into the prompt. If the user's phrasing doesn't map cleanly, ask for clarification.

---

## Part 3: Weekly Annotation Checklist

**Every week (starting Jun 15):**

- [ ] Target pairs completed: _____ / 15 pairs (per person this week)
- [ ] Total pairs annotated: _____ / 120–150 (cumulative)
- [ ] Cohen's κ on state labels: _____ (target ≥ 0.75 every 20 pairs)
- [ ] Execution pass rate: _____ % (target ≥ 95%)
- [ ] Distribution balanced? Check counts per query class
- [ ] Any classes behind? (Mark in annotation sheet and redistribute)
- [ ] Review notes for common errors (state: "needs_revision")

**Weekly sync (Mondays 10am ET):**
- Review κ scores and distribution
- Flag classes falling behind
- Redistribute work if needed
- Update annotation tracker

---

## Appendix: NBA Coordinate System Reference

**Court dimensions:**
- X-axis: −250 (left baseline) to +250 (right baseline)
- Y-axis: 0 (baseline) to 470 (far baseline)
- Origin: center court

**Zone boundaries — VERIFIED against live nba_api data:**
- x, y (LOC_X, LOC_Y): tenths of feet | distance (SHOT_DISTANCE): whole feet
- **Left corner 3:** x ≤ −220, y ≤ 90
- **Right corner 3:** x ≥ 220, y ≤ 90
- **Above the break 3:** y > 90, distance > 22  ← feet, NOT tenths
- **Restricted area:** distance ≤ 4 OR (ABS(x) ≤ 80 AND y ≤ 190)
- **Mid-range:** distance BETWEEN 8 AND 22
- **In the paint:** ABS(x) ≤ 80 AND y ≤ 190

**Common distances (NBA standard):**
- 3-point line: ~237 feet from basket (corners ~220 feet)
- Restricted area: 40 feet from basket
- Mid-range typical: 16–24 feet

---

**Document Version:** v1.0  
**Last Updated:** Jun 3, 2026  
**Author:** CoSQL NBA Team  
**Status:** Ready for annotation (Jun 15 kickoff)
