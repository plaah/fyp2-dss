---
name: fyp2-context-recovery
description: >
  Recovers full FYP2 DSS project context at the start of any Claude Code session.
  ALWAYS use this skill when the user says "where are we", "what's the status",
  "resume project", "continue from last time", "what have we done", "catch me up",
  "project status", or starts a new session without specifying a task. Also use
  when the user seems confused about current state or asks what to do next.
  Produces a crisp accurate current-state card in under 30 seconds.
---

# FYP2 Context Recovery — Claude Code

## Purpose
Recover project state fast at session start. Read only what's needed.
Never re-read the full CLAUDE.md. Never re-explain what's already built.

## Step 1: Read CLAUDE.md (3 sections only)

```bash
# Read only these sections — stop after 3
grep -A 30 "## Sprint Status" CLAUDE.md
grep -A 20 "## ML Architecture" CLAUDE.md
grep -A 15 "## API Endpoints" CLAUDE.md
```

## Step 2: Run status script

```bash
source venv/bin/activate
python scripts/surrogate_grouper_status.py 2>/dev/null || echo "Status script missing"
python -m pytest tests/ -q --tb=no 2>/dev/null | tail -3
```

## Step 3: Check key artifacts exist

```bash
python -c "
import os, pickle, pandas as pd
artifacts = {
    'MDC model':     'models/mdc_predictor.pkl',
    'Severity model':'models/severity_predictor.pkl',
    'CBG lookup':    'models/cbg_lookup_table.pkl',
    'Training data': 'data/clinical_training_data.csv',
    'ICD-10 lookup': 'data/icd10_2010_reference.csv',
    'ICD-9 lookup':  'data/icd9_cm_procedures.csv',
    'ID ICD-10':     'data/indonesian_icd10_lookup.csv',
    'ID ICD-9':      'data/indonesian_icd9_lookup.csv',
}
for name, path in artifacts.items():
    exists = os.path.exists(path)
    size = ''
    if exists and path.endswith('.csv'):
        try:
            n = len(pd.read_csv(path))
            size = f'({n} rows)'
        except: size = '(unreadable)'
    status = '✅' if exists else '❌'
    print(f'{status} {name}: {path} {size}')
"
```

## Step 4: Output current state card

Print this exactly:

```
=== FYP2 PROJECT — CURRENT STATE ===

SYSTEM: AI-DSS predicting BPJS INA-CBGs grouping from doctor's clinical inputs
ENTRY:  Doctor types diagnosis (Bahasa Indonesia) → ICD → CBG → tariff + risk

LAYER STATUS:
  Layer 1 — Free-text → ICD mapping    [status from CLAUDE.md]
  Layer 2 — Surrogate Grouper          [✅ MDC 77.22% | Severity 92.21% | CBG 100%]
  Layer 3 — Financial impact estimator [✅ kelas multipliers, 4-level risk]
  Layer 4 — Recommendation engine      [✅ SUBMIT/VERIFY/REVIEW actions]
  Layer 5 — Dashboard + PostgreSQL     [✅ 2 pages, audit trail, CSV export]
  Layer 6 — Neurovi HIS integration    [⏳ hook ready, awaiting API docs]

MODELS:
  Stage 1 MDC:      mdc_predictor.pkl      (XGBoost, 20 classes, 77.22% acc)
  Stage 2 Severity: severity_predictor.pkl (XGBoost binary, 92.21% acc)
  Stage 3 CBG:      cbg_lookup_table.pkl   (deterministic, 100% coverage)
  Training data:    3,076 real Tamtech claims (Oct–Nov 2025)

TESTS: [X]/91 passing
PROGRESS: ~[X]% | Demo 1: Apr 20–23 | Demo 2: May 25

NEXT TASK: [from CLAUDE.md sprint status — first ⏳ item]
===
```

## Step 5: Ask what to focus on

After the card, ask ONE question only:
"Ready to continue. Which task: [next pending task name] or something else?"

## Key Numbers (hardcoded — always correct)
- 3,076 real approved Tamtech claims used for training
- MDC 20 classes: A B D E F G H I J K L M N O Q S U V W Z (no P)
- Severity: ONLY 0 and I in real data (II/III not present)
- CBG: Q-5-44-0 = 39% of all claims (chronic misc outpatient)
- Tariff: 100% deterministic from CBG + kelas (confirmed)
- Kelas multipliers: kelas_1=1.5×, kelas_2=1.25×, kelas_3=1.0×
- Demo 1 target: ≥40% (system at ~55-90% depending on sprint)

## Error Handling
- If surrogate_grouper_status.py missing: run pytest directly
- If CLAUDE.md missing: check git log for last known state
- If models missing: check if venv activated, then re-check paths
