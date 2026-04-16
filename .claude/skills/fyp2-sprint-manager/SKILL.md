---
name: fyp2-sprint-manager
description: >
  Manages FYP2 DSS project sprint completions. ALWAYS use this skill when the
  user pastes a sprint completion summary, says "sprint done", "update jira",
  "mark complete", "jira update", or shares output from Claude Code ending with
  "=== SPRINT X COMPLETE ===". This skill handles the full post-sprint workflow:
  parse results → transition Jira tickets to Done → add detailed worklogs →
  update CLAUDE.md sprint status → confirm everything is logged. Use even for
  partial sprint completions or individual task updates.
---

# FYP2 Sprint Manager — Claude Code

## Project Constants
```
Jira cloudId:  1c807b90-cf69-4874-9a40-9892fb89df15
Project key:   SCRUM
Done:          transition id = "31"
In Progress:   transition id = "21"
```

## Jira Ticket Map
| Task | Key | Description |
|---|---|---|
| T1.1 | SCRUM-18 | Project Setup |
| T1.2 | SCRUM-19 | Synthetic Dataset |
| T1.3 | SCRUM-20 | Data Pipeline |
| T1.4 | SCRUM-21 | Ch.3 Draft |
| T2.1 | SCRUM-22 | XGBoost training |
| T2.2 | SCRUM-23 | Flask /predict |
| T2.3 | SCRUM-24 | SHAP module |
| T2.4 | SCRUM-25 | Git + summary |
| T3.1 | SCRUM-26 | Financial estimator |
| T3.2 | SCRUM-27 | Recommender |
| T3.3 | SCRUM-28 | Ch.5 draft |
| T4.1 | SCRUM-29 | Dashboard v1 |
| T4.2 | SCRUM-30 | PostgreSQL integration |
| T4.3 | SCRUM-31 | Ch.4 draft |
| T6.1 | SCRUM-61 | ICD lookup tables |
| T6.2 | SCRUM-62 | /icd-search endpoint |
| T6.3 | SCRUM-63 | Frontend ICD widget |
| T6.4 | SCRUM-64 | Sprint 6 housekeeping |

If ticket key unknown: search with JQL `summary ~ "T{X.Y}" ORDER BY summary ASC`

## Workflow

### Step 1 — Parse sprint summary
From the pasted output, extract:
- Sprint number + list of T{X.Y} tasks
- ✅ or ❌ per task
- Test count (e.g. "91 passed")
- Git commit hash
- Key metrics (accuracy, word count, row counts)
- What was built per task

### Step 2 — Transition tickets
For each ✅ completed task → `transitionJiraIssue` with `{"id": "31"}`
For ❌ or partial tasks → `transitionJiraIssue` with `{"id": "21"}`
Run all transitions before worklogs.

### Step 3 — Add worklogs
Call `addWorklogToJiraIssue` per completed task.

**Worklog format (markdown):**
```
✅ T{X.Y} COMPLETED — {date}

**{main file/module} — {one-line description}**

What was built:
- {item from sprint output}
- {item from sprint output}

Metrics: {test count} | {accuracy or word count if relevant}
Git commit: {hash}
```

**Time estimates:**
- Data prep / scripting: 4h
- ML training + eval: 6h  
- API endpoint: 4h
- Frontend widget: 6h
- Thesis writing: 5h
- Testing suite: 4h
- Housekeeping/git: 2h

### Step 4 — Update CLAUDE.md sprint status
Find the sprint row in CLAUDE.md and change ⏳ to ✅:
```bash
# Example for Sprint 6
sed -i 's/| \*\*Now\*\* | \*\*ICD reference.*| 🔄 In Progress |/| S6 | Free-text ICD search (Layer 1) | ✅ Done |/' CLAUDE.md
```
Or use str_replace to update the specific line precisely.

Also update cumulative progress % in CLAUDE.md.

### Step 5 — Git commit the CLAUDE.md update
```bash
git add CLAUDE.md
git commit -m "docs: update CLAUDE.md — Sprint {X} complete [T{X.1}-T{X.N}]"
```

### Step 6 — Confirm to user
```
=== JIRA UPDATED ===
✅ SCRUM-XX (T{X.Y}) → Done + worklog
✅ SCRUM-XX (T{X.Y}) → Done + worklog
...
CLAUDE.md: Sprint {X} marked complete ✅
Git: CLAUDE.md committed
Next: {next sprint tasks}
```

## Error Handling
- Ticket key unknown → search Jira JQL first
- Transition fails → log, continue other tickets
- Worklog fails → retry once, log and continue
- Never block entire workflow on one failure
