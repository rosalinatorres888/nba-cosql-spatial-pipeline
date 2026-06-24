# IE7500 Natural Language Processing — Milestone 2: Model Development

**Team:** Rosalina Torres, Craig Hobel, Sean Costello
**Course:** IE7500 Natural Language Processing | Northeastern University COE | EDGE Summer 2026

---

## 1. Research and Selection of Methods

### Project Objective

Build a conversational Text-to-SQL (CoSQL) system over NBA spatial shot-chart data, supporting multi-turn dialogue with coreference resolution across turns.

### Literature Review

- **DIN-SQL** (Pourreza & Rafiei, 2023) — Decomposed In-Context Learning of Text-to-SQL with Self-Correction. Few-shot prompting with GPT-4 achieves 55.9% EM on the CoSQL benchmark. Adopted as our primary prompting strategy.
- **CoSQL** (Yu et al., 2019) — Conversational Text-to-SQL challenge. Established the WOZ (Wizard-of-Oz) annotation protocol we followed for corpus construction and inter-annotator agreement measurement.
- **Seq2Seq / Neural Machine Translation** — Encoder-decoder GRU architecture (Sutskever et al., 2014) used for sequence-to-sequence SQL generation as a trainable baseline model.

### Methods Selected

| Approach | Framework | Role |
|---|---|---|
| Few-shot prompting (DIN-SQL style) | Claude Opus 4.8 (Anthropic API) | Primary NL→SQL inference |
| Seq2Seq GRU encoder-decoder | TensorFlow / Keras | Baseline NMT model for BLEU evaluation |
| Coreference resolution | Custom heuristic (pronoun + starter detection) | Multi-turn dialogue handling |

### Benchmarking

Our few-shot prompting approach was selected over fine-tuning due to corpus size constraints (138 pairs). A fine-tuned seq2seq model serves as a comparable baseline, enabling BLEU score comparison against gold SQL. This dual-model approach allows us to report both syntactic similarity (BLEU) and semantic correctness (execution accuracy).

### Preliminary Experiments

6 evaluation iterations (v1–v6) were conducted, improving execution accuracy from 42.9% → 100% on a held-out test split. Full iteration history documented in `docs/EVALUATION_RESULTS.md`.

---

## 2. Model Implementation

### Dataset Preparation

- **Source:** Boston Celtics 2023–24 season via `nba_api` → PostgreSQL database (`nba_spatial`)
- **Corpus:** 139 WOZ-annotated NL/SQL pairs across 8 query classes, execution-verified against live database
- **Annotation:** 3-annotator cross-verification; inter-annotator agreement 98.6% (68/69 pairs)
- **Split:** 80/20 train/test, seed=42 → 110 training pairs, 28 test pairs
- **Preprocessing:** SQL tokens preserved (e.g. `COUNT(*)` not stripped); English questions lowercased and whitespace-normalized

### Query Classes

| Class | Pairs | Example |
|---|---|---|
| Spatial Zone | 18 | "How many shots from the left corner?" |
| Temporal Scope | 18 | "What was the FG% in Q4?" |
| Player/Entity | 18 | "Which players attempted the most mid-range shots?" |
| Simple Aggregation | 18 | "How many 3-pointers were made in playoffs?" |
| Comparative Aggregation | 18 | "Who shot above 50% with at least 200 attempts?" |
| Multi-Turn Coreference | 16 | "What about only his made shots?" |
| Game/Matchup Context | 18 | "How many shots on October 30th?" |
| Shot Characteristics | 15 | "How many shots with less than 5 seconds left?" |

### Model Development

**Few-shot NL→SQL model (`model/nl2sql.py`):**
- Schema injected statically into every prompt (domain is fixed)
- 3 in-context examples selected per query by keyword-matched query class
- Coreference handled via prior-SQL carry-forward for Turn 2+ utterances
- 7 output format rules enforced in prompt (date format, period filters, shooting percentage formula, etc.)
- No fine-tuning — relies entirely on in-context learning

**Evaluator (`model/evaluate.py`):**
- Execution accuracy: predicted SQL executes AND result matches gold
- Result normalization: case-insensitive, float-tolerant (2 decimal places), row-order-independent, transposition-tolerant
- Coreference detection: pronoun + starter heuristic with punctuation stripping

**Seq2Seq GRU baseline (Craig Hobel / Sean Costello):**
- TensorFlow encoder-decoder architecture from Week 12 NMT lab
- Trained on `sql_training_full.csv` (NL question → gold SQL string)
- Hyperparameters: batch size=20, embedding dim=128, units=256

### Training & Fine-Tuning

| Model | Training | Hyperparameters |
|---|---|---|
| Few-shot (Claude Opus 4.8) | None — in-context learning | 3 examples per query, adaptive thinking |
| Seq2Seq GRU | 110 NL/SQL training pairs | batch=20, embed=128, units=256, epochs=TBD |

### Evaluation & Metrics

| Metric | Value |
|---|---|
| Execution accuracy — few-shot (held-out test set) | 28/28 = **100%** |
| SQL validity rate | 28/28 = 100% |
| Annotation corpus execution rate | 138/139 = 99.3% |
| Inter-annotator agreement | 68/69 = **98.6%** |
| DIN-SQL GPT-4 CoSQL benchmark (Pourreza & Rafiei, 2023) | 55.9% EM |
| BLEU-4 — seq2seq baseline | In progress |

---

## 3. GitHub Repository

**Repository:** https://github.com/rosalinatorres888/nba-cosql-spatial-pipeline

**Annotation Review Tool (live):** https://serene-alfajores-56283d.netlify.app

### Repository Structure

```
nba-cosql-spatial-pipeline/
├── annotation/                   # 8 query class CSVs — 139 NL/SQL pairs
├── model/
│   ├── nl2sql.py                 # Few-shot NL→SQL inference (DIN-SQL style)
│   └── evaluate.py               # Execution accuracy evaluator
├── docs/
│   ├── EVALUATION_RESULTS.md     # Full iteration history: 42.9% → 100%
│   ├── BUG_REPORT.md             # 13 bugs documented with root causes + fixes
│   ├── ANNOTATION_SHEET_SETUP.md # WOZ annotation protocol
│   └── NBA_API_REFERENCE.md      # nba_api v1.11.4 field reference
├── schema.sql                    # PostgreSQL schema (4 tables, FK constraints)
├── collect_nba_data.py           # nba_api data collection
├── load_csvs_to_db.py            # CSV → PostgreSQL bulk loader
├── kappa_report.py               # Inter-annotator agreement report
├── sql_training_full.csv         # Full annotated corpus (139 pairs)
├── requirements.txt              # Pinned Python dependencies
└── README.md                     # Full project documentation with badges
```

### Version Control & Documentation

- All development tracked via Git with descriptive commit messages
- 13 documented bugs with root causes and fixes in `docs/BUG_REPORT.md`
- README includes badges (execution accuracy, IAA, Python version, PostgreSQL, model), architecture diagram, multi-turn example, and live tool link
- Repository is public and accessible to reviewers

---

## References

- Pourreza, M. & Rafiei, D. (2023). DIN-SQL: Decomposed In-Context Learning of Text-to-SQL with Self-Correction. *NeurIPS 2023*.
- Yu, T. et al. (2019). CoSQL: A Conversational Text-to-SQL Challenge Towards Cross-Domain Natural Language Interfaces to Databases. *EMNLP 2019*.
- Sutskever, I., Vinyals, O., & Le, Q. V. (2014). Sequence to Sequence Learning with Neural Networks. *NeurIPS 2014*.
