"""
nl2sql.py — Few-Shot NL→SQL Inference
CoSQL NBA Spatial Pipeline | IE7500 NLP Northeastern EDGE Summer 2026
Author: Rosalina Torres

Method: DIN-SQL-style few-shot prompting (Pourreza & Rafiei, 2023)
  - Schema injected into every prompt
  - 3 in-context examples selected by query_class similarity
  - Coreference handled via prior_sql carry-forward for Turn 2+ utterances
  - No fine-tuning; model = Claude Opus 4.8 with adaptive thinking

Usage:
    from model.nl2sql import NL2SQL
    model = NL2SQL()
    sql = model.predict("How many 3-pointers did Tatum make in Q4?")
    sql = model.predict("What about his made shots only?", prior_sql=sql)
"""

import os
import csv
import random
from pathlib import Path
from typing import Optional
import anthropic
from dotenv import load_dotenv

# pick up ANTHROPIC_API_KEY from the project .env when run standalone
load_dotenv(Path(__file__).parent.parent / ".env")

ANNOTATION_DIR = Path(__file__).parent.parent / "annotation"
SCHEMA_PATH = Path(__file__).parent.parent / "schema.sql"

ANNOTATION_FILES = [
    ("Spatial Zone",            "annotation_batch_class1_spatial_zone.csv"),
    ("Temporal Scope",          "annotation_batch_class2_temporal_scope.csv"),
    ("Player/Entity",           "annotation_batch_class3_player_entity.csv"),
    ("Simple Aggregation",      "annotation_batch_class4_simple_aggregation.csv"),
    ("Comparative Aggregation", "annotation_batch_class5_comparative_aggregation.csv"),
    ("Multi-Turn Coreference",  "annotation_batch_class6_coreference.csv"),
    ("Game/Matchup Context",    "annotation_batch_class7_game_context.csv"),
    ("Shot Characteristics",    "annotation_batch_class8_shot_characteristics.csv"),
]

DB_SCHEMA = """
Tables in PostgreSQL database 'nba_spatial':

players(player_id INTEGER PK, name TEXT, team TEXT, position TEXT,
        height TEXT, weight TEXT, draft_year INTEGER)

games(game_id TEXT PK, date DATE, home_team TEXT, away_team TEXT,
      venue TEXT, score INTEGER, season_type TEXT)
  -- season_type values: 'Regular', 'Playoff', 'Preseason'
  -- game_id prefix: 002=Regular, 004=Playoff

shot_charts(id SERIAL PK, player_id INTEGER FK, game_id TEXT FK,
            shot_type TEXT, x INTEGER, y INTEGER, distance INTEGER,
            made_flag SMALLINT, defender TEXT,
            minutes_remaining INTEGER, period_seconds_remaining INTEGER,
            period INTEGER)
  -- x, y: court coordinates in tenths of feet (-250 to +250, 0 to 470)
  -- distance: shot distance in whole feet (e.g. distance > 22 for 3PT, NOT > 220)
  -- made_flag: 1 = made, 0 = missed
  -- shot_type: '2PT Field Goal' or '3PT Field Goal'
  -- period: 1-4 regulation, 5+ overtime
  -- clock: minutes_remaining * 60 + period_seconds_remaining = total seconds left

play_by_play(id SERIAL PK, event_id INTEGER, game_id TEXT FK,
             event_type TEXT, game_clock TEXT, player_ids TEXT,
             lineups TEXT, running_score TEXT)

Spatial zone reference:
  left_corner_3:   x <= -220 AND y <= 90
  right_corner_3:  x >= 220 AND y <= 90
  above_break_3:   y > 90 AND distance > 22
  restricted_area: distance <= 4 OR (ABS(x) <= 80 AND y <= 190)
  in_the_paint:    ABS(x) <= 80 AND y <= 190
  mid_range:       distance BETWEEN 8 AND 22
"""


def load_examples() -> dict[str, list[dict]]:
    """Load all approved annotation pairs grouped by query class."""
    examples: dict[str, list[dict]] = {}
    for class_name, fname in ANNOTATION_FILES:
        path = ANNOTATION_DIR / fname
        if not path.exists():
            continue
        pairs = []
        with open(path, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                if row.get("execution_pass", "").upper() == "TRUE" and row.get("utterance") and row.get("gold_sql"):
                    pairs.append({
                        "utterance": row["utterance"],
                        "sql": row["gold_sql"],
                        "notes": row.get("notes", ""),
                    })
        examples[class_name] = pairs
    return examples


def select_examples(utterance: str, examples: dict[str, list[dict]], n: int = 3) -> list[dict]:
    """
    Pick n in-context examples by keyword overlap with the utterance.
    Falls back to random sampling across all classes if no strong match.
    """
    utterance_lower = utterance.lower()

    CLASS_KEYWORDS = {
        "Spatial Zone":            ["corner", "zone", "paint", "left", "right", "mid", "three", "3pt", "restricted", "court"],
        "Temporal Scope":          ["quarter", "q4", "q3", "period", "half", "overtime", "ot", "clock", "minute", "second", "fourth"],
        "Player/Entity":           ["jayson", "jaylen", "tatum", "brown", "player", "who", "name"],
        "Simple Aggregation":      ["how many", "count", "total", "average", "avg", "sum", "percent"],
        "Comparative Aggregation": ["more than", "less than", "most", "least", "compare", "vs", "better", "higher", "lower"],
        "Multi-Turn Coreference":  ["those", "them", "his", "their", "same", "also", "what about", "and"],
        "Game/Matchup Context":    ["game", "opponent", "against", "home", "away", "matchup", "date"],
        "Shot Characteristics":    ["distance", "feet", "layup", "dunk", "jump shot", "type", "made", "missed"],
    }

    scores: dict[str, int] = {}
    for class_name, keywords in CLASS_KEYWORDS.items():
        scores[class_name] = sum(1 for kw in keywords if kw in utterance_lower)

    best_class = max(scores, key=lambda c: scores[c])
    pool = examples.get(best_class, [])

    if len(pool) >= n:
        return random.sample(pool, n)

    # pad from other classes if needed
    all_pairs = [p for pairs in examples.values() for p in pairs]
    return random.sample(all_pairs, min(n, len(all_pairs)))


def build_prompt(utterance: str, selected: list[dict], prior_sql: Optional[str] = None) -> str:
    """Build the few-shot prompt with schema + examples + utterance."""
    examples_text = "\n".join(
        f"NL: {ex['utterance']}\nSQL: {ex['sql']}"
        for ex in selected
    )

    coreference_block = ""
    if prior_sql:
        coreference_block = f"""
This is a follow-up question in a multi-turn dialogue.
The previous SQL query was:
{prior_sql}

Apply coreference resolution: carry forward table, filters, and entity references
from the prior SQL unless the new utterance explicitly replaces them.
"""

    return f"""You are a Text-to-SQL system for NBA shot-chart data.
Generate a single executable PostgreSQL SELECT query for the given question.
Return ONLY the SQL — no explanation, no markdown, no semicolon.

Output format rules:
- "How many" or "Show me all" questions about counts → always use SELECT COUNT(*), never SELECT *
- Shooting percentage → use CAST(SUM(CASE WHEN made_flag=1 THEN 1 ELSE 0 END) AS FLOAT) / COUNT(*)
- Label strings in CASE WHEN → use lowercase_with_underscores (e.g. 'first_half', 'made', 'missed')
- When returning a single ranked result → include the metric column, not just the group key
- Period filters → use period IN (1,2) not period <= 2 (avoids including OT periods unintentionally)
- Quarter/period analysis (ranking, comparing, aggregating by period) → always add WHERE period BETWEEN 1 AND 4 to exclude overtime, unless the question explicitly asks about overtime
- Date queries → always use date = 'YYYY-MM-DD' format, never EXTRACT. Season is 2023-24: October–December = 2023, January–June = 2024 (e.g. "October 30th" → date = '2023-10-30')

{DB_SCHEMA}

Examples:
{examples_text}
{coreference_block}
Question: {utterance}
SQL:"""


class NL2SQL:
    """
    Few-shot NL→SQL inference using Claude Opus 4.8.

    Follows DIN-SQL decomposition:
      1. Schema linking (injected statically — domain is fixed)
      2. Query classification (keyword-based example selection)
      3. SQL generation (few-shot in-context learning)
      4. Coreference (prior_sql carry-forward for Turn 2+)
    """

    def __init__(self, api_key: Optional[str] = None,
                 examples: Optional[dict[str, list[dict]]] = None):
        """
        Args:
            api_key:  Anthropic API key (falls back to ANTHROPIC_API_KEY env var)
            examples: In-context example pool grouped by query class.
                      Pass a train-only pool during evaluation — loading the
                      default (all annotations) would leak test items into
                      the few-shot prompt.
        """
        self.client = anthropic.Anthropic(api_key=api_key or os.environ.get("ANTHROPIC_API_KEY"))
        self.examples = examples if examples is not None else load_examples()
        total = sum(len(v) for v in self.examples.values())
        print(f"Loaded {total} approved examples across {len(self.examples)} query classes")

    def predict(self, utterance: str, prior_sql: Optional[str] = None) -> str:
        """
        Predict SQL for a natural language utterance.

        Args:
            utterance:  The user's natural language question
            prior_sql:  SQL from the prior turn (enables coreference resolution)

        Returns:
            Predicted SQL string
        """
        selected = select_examples(utterance, self.examples)
        prompt = build_prompt(utterance, selected, prior_sql)

        response = self.client.messages.create(
            model="claude-opus-4-8",
            max_tokens=512,
            thinking={"type": "adaptive"},
            messages=[{"role": "user", "content": prompt}],
        )

        sql = ""
        for block in response.content:
            if block.type == "text":
                sql = block.text.strip()
                break

        # strip any accidental markdown fences
        if sql.startswith("```"):
            sql = sql.split("```")[1].strip()
            if sql.lower().startswith("sql"):
                sql = sql[3:].strip()

        return sql

    def predict_conversation(self, turns: list[str]) -> list[dict]:
        """
        Run a full multi-turn conversation.

        Args:
            turns: List of utterances in order

        Returns:
            List of {utterance, sql, turn} dicts
        """
        results = []
        prior_sql = None
        for i, utterance in enumerate(turns):
            sql = self.predict(utterance, prior_sql=prior_sql if i > 0 else None)
            results.append({"turn": i + 1, "utterance": utterance, "sql": sql})
            prior_sql = sql
        return results


if __name__ == "__main__":
    model = NL2SQL()

    print("\n--- Single-turn example ---")
    q = "How many 3-pointers did Jayson Tatum make from the left corner?"
    sql = model.predict(q)
    print(f"NL:  {q}")
    print(f"SQL: {sql}")

    print("\n--- Multi-turn coreference example ---")
    turns = [
        "How many shots did Jaylen Brown attempt in Q4?",
        "What about only his made shots?",
        "And just from the restricted area?",
    ]
    for result in model.predict_conversation(turns):
        print(f"Turn {result['turn']}: {result['utterance']}")
        print(f"  → {result['sql']}")
