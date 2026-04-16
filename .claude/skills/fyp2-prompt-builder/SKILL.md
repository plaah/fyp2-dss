---
name: fyp2-prompt-builder
description: >
  Builds complete, precise Claude Code execution prompts for any FYP2 DSS
  sprint task. ALWAYS use this skill when the user asks to "make a prompt",
  "write a prompt for", "prepare claude code prompt", "next sprint prompt",
  or wants to continue development on any FYP2 task. Produces prompts that
  are self-contained, reference the correct files, include error handling,
  and always end with CLAUDE.md update instructions. Use for any new
  feature, bug fix, refactor, testing, or thesis writing task.
---

# FYP2 Prompt Builder — Claude Code

## Purpose
Produce Claude Code prompts that work the first time — fully specified,
contextually grounded, with correct file paths, error handling, and
documentation steps baked in.

## Prompt Template Structure
Every FYP2 Claude Code prompt must have these sections in order:

```
1. ROLE DECLARATION
2. READ INSTRUCTIONS (what to read before starting)
3. TASK BREAKDOWN (numbered, with Jira keys)
4. VERIFICATION STEPS (how to confirm each task works)
5. ERROR HANDLING RULES
6. CONTEXT EFFICIENCY RULES
7. START INSTRUCTION (what to do first)
```

## Section 1: Role Declaration (always this exact text)

```
Read CLAUDE.md before starting. Focus on: Sprint Status + ML Architecture
+ API Endpoints sections only.

=== YOUR ROLE ===
You are a senior software engineer AND hospital informatics expert who
deeply understands BPJS Kesehatan, INA-CBGs tariff structure, Casemix
coding workflow, and clinical decision support systems. You understand
Indonesian hospital billing — the relationship between iDRG grouping,
INACBG CBG codes, kelas tariffs, and how undercoding/overcoding creates
financial risk. The system entry point is the DOCTOR at diagnosis stage,
not the Casemix coder post-coding.
```

## Section 2: Read Instructions

Always include:
```
=== BEFORE STARTING ===
1. python scripts/surrogate_grouper_status.py  (check baseline)
2. python -m pytest tests/ -q --tb=no          (confirm 91 tests pass)
3. Verify venv active: which python (should be ./venv/bin/python)
```

For data-heavy tasks, also add:
```
4. Check data files exist:
   ls -lh data/indonesian_icd10_lookup.csv data/indonesian_icd9_lookup.csv
```

## Section 3: Task Breakdown Format

For each task:
```
=== TASK T{X.Y} — {Task Name} ===
Jira: SCRUM-{XX}
Effort: {Xh}
Depends on: {T{X.Z} if any}

[Detailed implementation with:
 - Exact file paths
 - Complete function signatures with docstrings
 - Code that references existing project structure
 - Specific variable names matching existing codebase]

CHECKPOINT T{X.Y}:
Print "=== T{X.Y} DONE === {key metric} ✅ | {key metric} ✅"
```

## Section 4: Verification Steps

Always include curl tests for API endpoints:
```bash
source venv/bin/activate && python app.py &
sleep 2
curl -s "http://localhost:5001/api/v1/{endpoint}" | python -m json.tool
```

Always include pytest at the end:
```bash
python -m pytest tests/ -v --tb=short -q
# All tests must pass including new ones
```

Always include a browser smoke test for UI changes:
```
Open http://localhost:5001
Test: [specific action]
Expected: [specific outcome]
```

## Section 5: Error Handling (standard block)

```
=== ERROR HANDLING ===
1. Try to fix autonomously — max 3 attempts per error
2. After 3 failed attempts:
   Print "=== BLOCKED === Task: [T{X.Y}] | Error: [message]"
   Append to docs/sprint{X}_errors.md
   Skip to next task — never stop entire sprint
3. Port conflict: lsof -ti:5001 | xargs kill -9
4. DB connection: pg_isready -h localhost -p 5432
5. venv issues: deactivate && source venv/bin/activate
```

## Section 6: Context Efficiency Rules

```
=== CONTEXT EFFICIENCY ===
- Read CLAUDE.md once at session start — never re-read mid-sprint
- After each CHECKPOINT: append 1-line status to scripts/sprint{X}_status.py
- Use -q flag on pytest to reduce output noise
- Read only the specific function you're fixing, not whole files
- Run full test suite only once at the very end
```

## Section 7: Start Instruction + Final Summary

```
=== START ===
First: python scripts/surrogate_grouper_status.py
Then: python -m pytest tests/ -q --tb=no
Confirm baseline before touching any code.
Then begin T{X.1}.

=== FINAL SUMMARY FORMAT ===
Print when ALL tasks complete:
"=== SPRINT {X} COMPLETE ==="
"T{X.1} {name}: {key metric} ✅"
"T{X.2} {name}: {key metric} ✅"
"..."
"Tests: [X] passed / 0 failed"
"Git commit: [hash]"
"Cumulative progress: ~[X]%"
```

## CLAUDE.md Update Instructions (always at end of every prompt)

```
=== UPDATE CLAUDE.md ===
1. Mark completed tasks ✅ in Sprint Status table
2. Update cumulative progress %
3. If new data files created: add to data inventory section
4. If new endpoints added: add to API Endpoints table
5. If model retrained: update ML Architecture section with new metrics
6. Git commit CLAUDE.md:
   git add CLAUDE.md
   git commit -m "docs: Sprint {X} complete — CLAUDE.md updated"
```

## Existing Project File Reference

Key files Claude Code must know about:

```
src/
  api/routes.py              ← all Flask endpoints
  services/
    surrogate_grouper.py     ← MAIN ML pipeline (Stage 1+2+3)
    financial_estimator.py   ← tariff risk logic
    recommender.py           ← action synthesis
    icd_search.py            ← ICD search service (Sprint 6)
  models/
    db_models.py             ← SQLAlchemy ORM (3 tables)
    crud.py                  ← DB operations

models/
  mdc_predictor.pkl          ← Stage 1 (77.22% acc)
  severity_predictor.pkl     ← Stage 2 (92.21% acc)
  cbg_lookup_table.pkl       ← Stage 3 (100% coverage)
  mdc_feature_names.txt      ← feature list for Stage 1

data/
  tamtech_raw_extract.csv        ← 3,429 real claims
  clinical_training_data.csv     ← 3,076 training records
  indonesian_icd10_lookup.csv    ← validated Indonesian→ICD-10
  indonesian_icd9_lookup.csv     ← Indonesian procedure→ICD-9
  icd10_2010_reference.csv       ← WHO ICD-10 Vol.3 extracted
  icd9_cm_procedures.csv         ← ICD-9-CM extracted

templates/
  index.html                 ← prediction form (doctor input)
  dashboard.html             ← analytics overview

tests/
  test_surrogate_grouper.py  ← 91 tests (all passing)
  test_database.py
  test_financial_estimator.py
  test_recommender.py
  test_icd_search.py         ← Sprint 6 tests
```

## Anti-Patterns to Avoid in Prompts

❌ Never include grouping_success, final_success, idrg_grouping_success
   as input features — these are post-grouper outputs, circular reasoning

❌ Never instruct to predict grouping_valid/coding_incomplete/grouping_invalid
   — these are the RETIRED 3-class labels, replaced by CBG prediction

❌ Never use port 5000 — project runs on 5001

❌ Never reference synthetic_bpjs.csv as training data — it's legacy

❌ Never suggest retraining the ML model without checking
   data/clinical_training_data.csv exists first
