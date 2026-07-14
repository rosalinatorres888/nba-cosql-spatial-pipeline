"""
Tests for evaluation integrity: strict result matching and leakage-free
train/test splitting. No database or API key required.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from model.evaluate import (
    results_match,
    load_conversations,
    examples_from_conversations,
)


# ---------- results_match: strict semantics ----------

def test_match_identical():
    assert results_match([{"a": 1}], [{"a": 1}])


def test_match_ignores_column_names_and_row_order():
    gold = [{"player": "Tatum", "pts": 30}, {"player": "Brown", "pts": 25}]
    pred = [{"name": "Brown", "total": 25}, {"name": "Tatum", "total": 30}]
    assert results_match(gold, pred)


def test_no_match_on_swapped_labels():
    # Same numbers, different label pairing — must NOT match.
    gold = [{"zone": "made", "pct": 0.64}, {"zone": "missed", "pct": 0.37}]
    pred = [{"zone": "missed", "pct": 0.64}, {"zone": "made", "pct": 0.37}]
    assert not results_match(gold, pred)


def test_no_match_on_different_row_counts():
    # The old numeric-only fallback accepted this; strict matcher must not.
    gold = [{"paint_pct": 0.64, "above_break_pct": 0.37}]
    pred = [{"zone": "paint", "pct": 0.64}, {"zone": "above_break", "pct": 0.37}]
    assert not results_match(gold, pred)


def test_no_match_on_none():
    assert not results_match(None, [{"a": 1}])
    assert not results_match([{"a": 1}], None)


def test_float_normalization():
    assert results_match([{"pct": 0.5}], [{"pct": 0.50000001}])


# ---------- split: no leakage, conversation-level ----------

def test_split_has_no_train_test_overlap():
    # Leakage = a test item's (utterance, gold_sql) pair available as a
    # few-shot example. Bare utterance text can legitimately repeat across
    # conversations (generic follow-ups like "How many did he make?" have
    # different gold SQL depending on context), so we key on the pair.
    train_convs, test_convs = load_conversations(split=0.2, seed=42)
    pool = examples_from_conversations(train_convs)
    train_items = {(ex["utterance"], ex["sql"]) for exs in pool.values() for ex in exs}
    test_items = {(p["utterance"], p["gold_sql"]) for c in test_convs for p in c}
    assert test_items, "test split is empty"
    assert not (train_items & test_items), (
        "test (utterance, gold_sql) pairs leaked into the few-shot example pool"
    )


def test_conversations_not_split_across_train_test():
    train_convs, test_convs = load_conversations(split=0.2, seed=42)
    # multi-turn conversations exist and stay intact
    assert any(len(c) > 1 for c in train_convs + test_convs)
    for conv in train_convs + test_convs:
        assert all(isinstance(p["utterance"], str) and p["gold_sql"] for p in conv)
