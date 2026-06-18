# WOZ Annotation Sheet Setup Guide

**CoSQL NBA Spatial · IE7600 · Real-Time Collaboration**

---

## Option A: Google Sheets (Recommended) ✓

Use Google Sheets for real-time collaboration. Share edit access with Craig and Sean. Export to CSV at M2 (Jul 3) for final submission.

### **Step 1: Create the Sheet**

1. Go to https://sheets.google.com
2. **New blank spreadsheet**
3. Name it: `CoSQL_NBA_WOZ_Annotations_v1`
4. Share link with Craig + Sean (edit access)

### **Step 2: Set Up Headers**

In row 1, create these column headers:

| A | B | C | D | E | F | G | H | I | J | K | L |
|---|---|---|---|---|---|---|---|---|---|---|---|
| utterance | gold_sql | query_class | state | annotator | nl_user_1 | nl_user_2 | state_auditor | execution_pass | kappa_agreement | date_completed | notes |

### **Step 3: Set Up Data Validation**

**Column C (query_class):** Dropdown with 8 options
1. Select column C
2. **Data → Data validation**
3. Criteria: List of items
4. Enter: `Spatial Zone, Temporal Scope, Player/Entity, Simple Aggregation, Comparative Aggregation, Multi-Turn Coreference, Game/Matchup Context, Shot Characteristics`
5. Apply

**Column D (state):** Dropdown with status options
1. Select column D
2. **Data → Data validation**
3. Criteria: List of items
4. Enter: `approved, needs_revision, ambiguous, clarification_needed, excluded, metric_ambiguous, coreference_failed`
5. Apply

**Column I (execution_pass):** Checkbox
1. Select column I
2. **Insert → Checkbox**
3. Apply

### **Step 4: Add Summary Section**

**Above the data table (rows before header), add:**

```
ANNOTATION TRACKER — CoSQL NBA WOZ Pairs

Week Ending: Jun 22, 2026
Target: 120 pairs by Jul 1 | Current: ___ pairs | Pace: ___

Distribution by Query Class (Target: 15+ per class):
- Spatial Zone: ___ / 15
- Temporal Scope: ___ / 15
- Player/Entity: ___ / 15
- Simple Aggregation: ___ / 15
- Comparative Aggregation: ___ / 15
- Multi-Turn Coreference: ___ / 15
- Game/Matchup Context: ___ / 15
- Shot Characteristics: ___ / 15

Cohen's Kappa (State Labels): ___ (target ≥ 0.75)
Execution Pass Rate: ___ % (target ≥ 95%)

Weekly Annotator Workload:
- Rosalina (SQL Expert): ___ pairs reviewed
- Craig (NL User 1): ___ turns
- Sean (NL User 2): ___ turns
- State Auditor (rotating): ___ reviewed
```

**Update manually each Monday after sync.**

### **Step 5: Format for Readability**

- **Freeze header row:** View → Freeze → 1 row
- **Bold headers:** Select row 1, Ctrl+B
- **Alternate row colors:** Format → Alternating colors → Choose a theme
- **Column widths:** Widen columns B (gold_sql) and L (notes) for readability
  - Column B: 400px (SQL can be long)
  - Column L: 300px (notes)

### **Step 6: Share with Team**

1. Click **Share** (top right)
2. Add Craig + Sean with **Editor** access
3. Post the link in your repo README:

```markdown
**Live Annotation Tracker:** [Google Sheets Link](https://docs.google.com/spreadsheets/d/YOUR_SHEET_ID/edit)
```

---

## Option B: CSV in Repo (Backup)

If you prefer to track annotations locally:

### **Weekly Workflow**

1. **Download CSV from Google Sheets:**
   - File → Download → CSV (.csv)
   - Save as `/training/woz_annotation_pairs_WEEK_N.csv`

2. **Commit to repo:**
   ```bash
   git add training/woz_annotation_pairs_WEEK_N.csv
   git commit -m "[T7a] WOZ pairs Week N — 20 pairs, κ=0.80"
   git push origin develop
   ```

3. **At M2 (Jul 3):**
   - Combine all weekly CSVs into one: `/training/woz_annotation_pairs_final.csv`
   - Commit as final version

---

## Weekly Annotation Workflow

### **Kickoff: Jun 15 (Week 3)**

1. **Rosalina** creates the Google Sheet and shares link
2. **Craig + Sean** accept share invitation and verify access
3. **All three** review `/docs/query_classes_and_clarify_templates.md` together
4. **Rosalina** posts annotation instructions in README

### **Weekly (Mon–Thu, Jun 15 – Jul 1)**

**Monday–Wednesday:**
- Craig: Annotate 5 pairs (NL user for 5 sessions)
- Sean: Annotate 5 pairs (NL user for 5 sessions)
- Rosalina: Write gold SQL for 10 pairs (SQL expert role)

**Thursday:**
- Rotating state auditor reviews all pairs from the week
- Calculate Cohen's κ on state labels (every 20 pairs)
- Mark execution_pass (did SQL run on live DB?)
- Update summary section

**Friday:**
- Weekly sync (10am ET): Review progress, redistribute if behind
- Celebrate milestones (every 20 pairs)

### **Pair Workflow**

#### **Step 1: NL User (Craig or Sean)**
- Generates 1–2 natural language questions about NBA data
- Posts in shared doc or Slack with context
- Example: "How many 3-pointers from the left corner in Q4?"

#### **Step 2: SQL Expert (Rosalina)**
- Writes gold_sql (ground truth SQL)
- Verifies execution on live PostgreSQL DB
- If it fails: mark `execution_pass = FALSE` and note the error
- Assigns query_class from the 8 classes
- Enters in the sheet

#### **Step 3: State Auditor (Rotating — Craig/Sean)**
- Reviews the pair for clarity and correctness
- Labels state: "approved", "needs_revision", or "ambiguous"
- Enters any notes (edge cases, ambiguities encountered)

#### **Step 4: Calculate Agreement**
- Every 20 pairs, Rosalina calculates Cohen's κ on state labels
- If κ < 0.75: re-annotate pairs below threshold
- Update summary

---

## Validation Checklist (Weekly)

Before week ends:

- [ ] **Row count:** 5 new pairs × 3 people = 15 pairs this week (cumulative: check total)
- [ ] **Execution pass:** All pairs run successfully (execution_pass = TRUE)
- [ ] **Distribution:** No query class is >5 pairs ahead or behind target
- [ ] **Cohen's κ:** ≥ 0.75 on every 20-pair batch
- [ ] **Notes filled:** Every pair has at least one note (why this pair, edge cases, etc.)
- [ ] **Date column:** All dates within current week
- [ ] **Summary updated:** Counts, κ, pass rate calculated and filled in

---

## Annotation Tips & Gotchas

### **Writing Good Gold SQL**

✓ **DO:**
- Test every SQL on the live database before submitting
- Use player_id, not player name (names are not unique keys)
- Quote string literals ('BOS', 'LAL')
- Comment complex queries: `-- Filter for Q4 and paint zone`
- Use lowercase for keywords (WHERE, SELECT, COUNT)

✗ **DON'T:**
- Hardcode player_id without confirming it matches nba_api
- Use undefined columns (check schema first)
- Write SQL that could timeout (avoid full table scans if possible)
- Assume zone names — always verify against lexicon

### **Common Errors to Catch**

| Error | Symptom | Fix |
|-------|---------|-----|
| Wrong zone bounds | "Left corner" mapped to x ≥ 220 (right corner) | Check lexicon in `/docs/query_classes_and_clarify_templates.md` |
| game_clock vs. shot_clock | "With 5 seconds left" interpreted as game_clock, not shot_clock | Clarify which timer: game period or shot clock? |
| Missing JOINs | "In the Celtics-Lakers game" returns no results | Verify games table has game_date, teams; shot_charts has game_id |
| Entity alias | "JT" not recognized | Resolve to full name in players table |
| Aggregation type | Counts when percentages expected | Re-read user's intent and clarify before writing SQL |

---

## Exporting to Final CSV (M2 Submission, Jul 3)

**One week before M2:**

1. **Download the full Google Sheet as CSV:**
   - File → Download → CSV
   - Save as `/training/woz_annotation_pairs_final.csv`

2. **Verify counts:**
   - `wc -l woz_annotation_pairs_final.csv` should be ≥ 120 rows (plus header)
   - Sort by query_class, count per class (each should be ≥ 15)

3. **Verify execution pass rate:**
   - `grep "TRUE" woz_annotation_pairs_final.csv | wc -l` ≥ 114 (95% of 120)

4. **Commit to repo:**
   ```bash
   git add training/woz_annotation_pairs_final.csv
   git commit -m "[T7a] Final WOZ annotation set — 150 pairs, κ=0.81, 98% execution pass"
   git push origin develop
   ```

5. **Tag in GitHub:**
   ```bash
   git tag m2-submission-woz-final
   git push origin m2-submission-woz-final
   ```

---

## Template Checklist

Use this CSV to get started. Copy-paste rows as needed and modify:

```csv
utterance,gold_sql,query_class,state,annotator,nl_user_1,nl_user_2,state_auditor,execution_pass,kappa_agreement,date_completed,notes
"[Your NL question here]","[Your gold SQL here]","[Class name]","approved","Rosalina","Craig","Sean","[Auditor name]",TRUE,0.80,2026-06-15,"[Your notes]"
```

Fill in the template CSV provided in the repo at `/training/woz_annotation_template.csv`.

---

**Ready to start?**

1. Create the Google Sheet today (Jun 3)
2. Share with Craig + Sean
3. Post link in your README
4. Annotation kickoff: **Jun 15**

---

**Document Version:** v1.0  
**Last Updated:** Jun 3, 2026  
**Status:** Ready for team use
