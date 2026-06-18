"""
evaluate.py — Execution Accuracy Evaluation
CoSQL NBA Spatial Pipeline | IE7500 NLP Northeastern EDGE Summer 2026
Author: Rosalina Torres

Evaluates the nl2sql inference model against a held-out test split of the
139 annotation pairs. Reports execution accuracy: does the predicted SQL
return the same result as the gold SQL on the live nba_spatial database?

Metrics reported:
  - Execution accuracy (primary): predicted SQL executes AND matches gold result
  - SQL validity rate: predicted SQL executes without error
  - Per-class breakdown across 8 query classes

Usage:
    python model/evaluate.py
    python model/evaluate.py --split 0.2 --seed 99
"""

import argparse
import csv
import os
import random
import sys
from pathlib import Path
from typing import Optional

import psycopg2
from psycopg2.extras import RealDictCursor

# allow running from project root or model/ directory
sys.path.insert(0, str(Path(__file__).parent.parent))
from model.nl2sql import NL2SQL, ANNOTATION_DIR, ANNOTATION_FILES

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "nba_spatial")
DB_USER = os.getenv("DB_USER", "rosalinatorres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")


def connect() -> psycopg2.extensions.connection:
    return psycopg2.connect(
        host=DB_HOST, port=DB_PORT, database=DB_NAME,
        user=DB_USER, password=DB_PASSWORD,
    )


def run_query(conn, sql: str) -> Optional[list]:
    """Execute a SELECT query and return rows, or None on error."""
    if not sql or not sql.strip().upper().startswith(("SELECT", "WITH")):
        return None
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql)
            return [dict(r) for r in cur.fetchall()]
    except Exception:
        conn.rollback()
        return None


def normalize_value(v) -> str:
    """Normalize a result cell for loose comparison."""
    if v is None:
        return "null"
    s = str(v).strip().lower()
    # normalize floats: 0.450000 → 0.45, 45.0 → 45.0
    try:
        f = float(s)
        # round to 4 sig figs to absorb AVG vs CAST/COUNT floating point drift
        return f"{round(f, 4):.4f}".rstrip("0").rstrip(".")
    except ValueError:
        return s


def results_match(gold_rows: Optional[list], pred_rows: Optional[list]) -> bool:
    """
    Two result sets match if they contain the same values regardless of:
    - column names
    - row order
    - string case ('First Half' == 'first_half')
    - minor float representation differences (AVG vs CAST/COUNT)
    """
    if gold_rows is None or pred_rows is None:
        return False
    if len(gold_rows) != len(pred_rows):
        return False

    def normalize(rows):
        return sorted([
            tuple(sorted(normalize_value(v) for v in r.values()))
            for r in rows
        ])

    return normalize(gold_rows) == normalize(pred_rows)


COREFERENCE_PRONOUNS = {"he", "his", "she", "her", "they", "their", "those", "them",
                        "that", "it", "its", "same", "there", "what about", "only",
                        "and only", "missed ones", "made ones"}


def is_coreference_turn(utterance: str) -> bool:
    """Heuristic: does this utterance depend on a prior turn's context?"""
    u = utterance.lower().strip()
    # starts with pronoun or coreference phrase
    starters = ("he ", "his ", "they ", "those ", "what about", "and ", "only ",
                 "how many did he", "how many of those", "what about")
    if any(u.startswith(s) for s in starters):
        return True
    # contains pronoun but no named entity (no capitalized proper noun other than start)
    words = u.split()
    has_pronoun = any(w in COREFERENCE_PRONOUNS for w in words)
    has_named_entity = any(w[0].isupper() for w in words[1:] if len(w) > 2)
    return has_pronoun and not has_named_entity


def load_test_pairs(split: float, seed: int) -> tuple[list[dict], list[dict]]:
    """
    Load all approved annotation pairs and split into train/test.
    Preserves file order within each class so prior_gold_sql can be attached
    to Turn 2+ (coreference-dependent) utterances.
    Returns (train_pairs, test_pairs).
    """
    all_pairs = []
    for class_name, fname in ANNOTATION_FILES:
        path = ANNOTATION_DIR / fname
        if not path.exists():
            continue
        class_pairs = []
        with open(path, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                if row.get("execution_pass", "").upper() == "TRUE" and row.get("utterance") and row.get("gold_sql"):
                    class_pairs.append({
                        "utterance": row["utterance"],
                        "gold_sql": row["gold_sql"],
                        "query_class": class_name,
                        "notes": row.get("notes", ""),
                        "prior_gold_sql": None,
                    })
        # attach prior turn's gold SQL for coreference-dependent utterances
        for i, pair in enumerate(class_pairs):
            if i > 0 and is_coreference_turn(pair["utterance"]):
                pair["prior_gold_sql"] = class_pairs[i - 1]["gold_sql"]
        all_pairs.extend(class_pairs)

    random.seed(seed)
    random.shuffle(all_pairs)
    cutoff = int(len(all_pairs) * (1 - split))
    return all_pairs[:cutoff], all_pairs[cutoff:]


def evaluate(split: float = 0.2, seed: int = 42) -> dict:
    print("=" * 60)
    print("EXECUTION ACCURACY EVALUATION")
    print("CoSQL NBA Spatial — NL→SQL Inference")
    print("=" * 60)

    train_pairs, test_pairs = load_test_pairs(split, seed)
    print(f"\nDataset:   {len(train_pairs) + len(test_pairs)} total approved pairs")
    print(f"Train:     {len(train_pairs)} pairs  ({int((1-split)*100)}%)")
    print(f"Test:      {len(test_pairs)} pairs  ({int(split*100)}%)")

    model = NL2SQL()
    conn = connect()
    print(f"\n✅ Connected to {DB_NAME}")

    per_class: dict[str, dict] = {}
    total_valid = 0
    total_match = 0
    errors = []

    print(f"\nRunning inference on {len(test_pairs)} test pairs...\n")

    for i, pair in enumerate(test_pairs):
        cls = pair["query_class"]
        if cls not in per_class:
            per_class[cls] = {"total": 0, "valid": 0, "match": 0}

        per_class[cls]["total"] += 1

        prior_sql = pair.get("prior_gold_sql")
        predicted_sql = model.predict(pair["utterance"], prior_sql=prior_sql)
        gold_rows = run_query(conn, pair["gold_sql"])
        pred_rows = run_query(conn, predicted_sql)

        valid = pred_rows is not None
        match = results_match(gold_rows, pred_rows)

        if valid:
            total_valid += 1
            per_class[cls]["valid"] += 1
        if match:
            total_match += 1
            per_class[cls]["match"] += 1

        status = "✅" if match else ("⚠️ " if valid else "❌")
        print(f"  [{i+1:3d}/{len(test_pairs)}] {status} {cls}")
        print(f"         NL:   {pair['utterance'][:80]}")
        print(f"         Gold: {pair['gold_sql'][:80]}")
        print(f"         Pred: {predicted_sql[:80]}")
        if not match:
            errors.append({
                "utterance": pair["utterance"],
                "gold_sql": pair["gold_sql"],
                "predicted_sql": predicted_sql,
                "query_class": cls,
                "error": "result_mismatch" if valid else "execution_error",
            })
        print()

    n = len(test_pairs)
    validity_rate = total_valid / n if n else 0
    exec_accuracy = total_match / n if n else 0

    print("=" * 60)
    print("RESULTS")
    print("=" * 60)
    print(f"\n  SQL validity rate:    {total_valid}/{n}  ({validity_rate:.1%})")
    print(f"  Execution accuracy:   {total_match}/{n}  ({exec_accuracy:.1%})")

    print(f"\n  Per-class breakdown:")
    print(f"  {'Query Class':<28} {'Test':>5}  {'Valid':>5}  {'Match':>5}  {'Acc':>6}")
    print("  " + "-" * 54)
    for cls, stats in per_class.items():
        acc = stats["match"] / stats["total"] if stats["total"] else 0
        print(f"  {cls:<28} {stats['total']:>5}  {stats['valid']:>5}  {stats['match']:>5}  {acc:>5.0%}")

    if errors:
        print(f"\n  Failed pairs ({len(errors)}):")
        for e in errors:
            print(f"    [{e['error']}] {e['query_class']}: {e['utterance'][:60]}")

    # write error log
    error_log = Path(__file__).parent / "eval_errors.csv"
    if errors:
        with open(error_log, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["utterance", "gold_sql", "predicted_sql", "query_class", "error"])
            writer.writeheader()
            writer.writerows(errors)
        print(f"\n  Error log written to: {error_log}")

    print(f"\n{'=' * 60}")
    if exec_accuracy >= 0.85:
        print(f"  ✅ STRONG — {exec_accuracy:.1%} execution accuracy on held-out test set")
    elif exec_accuracy >= 0.70:
        print(f"  ✅ GOOD — {exec_accuracy:.1%} execution accuracy")
    else:
        print(f"  ⚠️  {exec_accuracy:.1%} — review error log and refine few-shot examples")

    conn.close()
    return {
        "n_test": n,
        "validity_rate": validity_rate,
        "execution_accuracy": exec_accuracy,
        "per_class": per_class,
        "n_errors": len(errors),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Evaluate NL→SQL execution accuracy")
    parser.add_argument("--split", type=float, default=0.2, help="Test split fraction (default 0.2)")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for split (default 42)")
    args = parser.parse_args()
    evaluate(split=args.split, seed=args.seed)
