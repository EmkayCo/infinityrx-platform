# Continuous Learning System

**Location in repo:** `docs/team/continuous-learning.md`  
**Also referenced by:** CLAUDE.md (builders read this)

---

## THE PROBLEM

Builder 1 discovers that SQLAlchemy silently converts Decimal to float when using `func.sum()`. Spends 20 minutes debugging. Fixes it. Builder 3 hits the exact same issue two hours later. Nobody learned anything.

## THE SOLUTION

Three mechanisms that capture mistakes AS THEY HAPPEN and prevent them from recurring across all builders.

---

## MECHANISM 1 — LESSONS LOG (Real-Time Capture)

File: `docs/lessons-learned.md`

Every builder MUST add an entry when they encounter a non-obvious bug, a surprising behavior, or a pattern that took more than 5 minutes to debug.

**Format:**
```markdown
### LESSON-{number}: {short title}
**Date:** {date}  
**Module:** {module name}  
**Builder:** {builder name}  
**Severity:** critical | high | medium  

**What happened:**
{describe the bug or surprising behavior}

**Root cause:**
{why it happened}

**Fix:**
{what you did to fix it}

**Prevention rule:**
{the rule that would have prevented this — goes into .claude/rules/ if severity is critical or high}

**Regression test:**
{the test you wrote to catch this if it ever happens again}
```

**Example:**
```markdown
### LESSON-001: SQLAlchemy func.sum() silently converts Decimal to float
**Date:** 2026-04-14  
**Module:** billing  
**Builder:** Builder-Billing  
**Severity:** critical  

**What happened:**
`select(func.sum(APRecord.amount))` returns a Python float, not Decimal. 
Batch total was $45,892.439999999... instead of $45,892.44.

**Root cause:**
PostgreSQL returns NUMERIC correctly, but SQLAlchemy's func.sum() 
doesn't preserve the Decimal type on the Python side.

**Fix:**
Cast the result: `Decimal(str(result))` after every aggregate query.
Created helper: `def safe_sum(result) -> Decimal`

**Prevention rule:**
ADDED TO .claude/rules/financial-precision.md:
"Never use raw func.sum/func.avg results for money. Always wrap in 
Decimal(str(result)). Use the safe_sum() helper from core.utils.decimal."

**Regression test:**
test_ap_batch_total_is_decimal_not_float — verifies batch total 
is exactly Decimal type and matches penny-perfect sum of components.
```

---

## MECHANISM 2 — RULES FILE UPDATES (Propagation)

When a lesson has severity **critical** or **high**, the builder MUST:

1. Add the prevention rule to the appropriate `.claude/rules/{category}.md` file
2. Commit the rules file update in the SAME commit as the fix
3. All other builders read rules files — they get the learning immediately on their next task

**Which rules file:**
| Lesson category | Rules file |
|---|---|
| Decimal/float/rounding | `.claude/rules/financial-precision.md` |
| PHI leak, encryption issue | `.claude/rules/phi-compliance.md` |
| Auth bypass, injection, security | `.claude/rules/security.md` |
| Tenant isolation breach | `.claude/rules/security.md` |
| SQLAlchemy/PostgreSQL gotcha | `.claude/rules/data-integrity.md` |
| Event bus message issue | `.claude/rules/data-integrity.md` |
| Test pattern issue | `.claude/rules/testing.md` |
| API contract mismatch | `.claude/rules/api-contracts.md` |
| Performance/query issue | `.claude/rules/performance.md` |

**Medium severity lessons** stay in the lessons log but don't get promoted to rules — they're reference material for builders who hit similar issues.

---

## MECHANISM 3 — SESSION RETROSPECTIVE (End of Each Session)

Before ending a session, every builder appends to their handoff note:

```markdown
## Session Retrospective

**Mistakes made:**
- {what went wrong and what was learned}

**Surprising behaviors:**
- {anything that didn't work as expected}

**Time sinks:**
- {what took longer than expected and why}

**Rules added:**
- {list any rules file updates made during this session}

**Recommendations for next session:**
- {anything the next session (or other builders) should know}
```

The team lead reviews retrospectives between sessions and decides if any learning needs to be escalated to CLAUDE.md (the highest-priority rules file that ALL agents read first).

---

## MECHANISM 4 — ANTI-PATTERN REGISTRY (Growing List)

File: `docs/anti-patterns.md`

The anti-patterns list in the handbook (section 9) is the STARTING list. As the build progresses, new anti-patterns are discovered and added here. Every builder reads this file.

**Format:**
```markdown
### AP-{number}: {short title}
**Discovered:** {date}  
**Module:** {where it was found}  

**The pattern:**
{code example of what NOT to do}

**Why it's bad:**
{what goes wrong}

**The fix:**
{code example of what TO do instead}
```

This file grows throughout the build. By the end of Phase 2, it's a comprehensive list of every mistake the team made and how to avoid each one. This becomes invaluable for Phase 3 and beyond.

---

## WHEN THE TEAM LEAD UPDATES CLAUDE.md

The team lead promotes a lesson to CLAUDE.md (top of the rules hierarchy) when:

- The same mistake is made by 2+ different builders
- The mistake is severe enough that it MUST be the first thing any builder sees
- The lesson applies to ALL modules, not just one

**CLAUDE.md additions go at the top of the file** under a section called `## CRITICAL LESSONS LEARNED` so they're the first thing any agent reads after the project description.

---

## FLOW

```
Builder hits bug
    │
    ├── Fix the bug
    ├── Write regression test
    ├── Add entry to docs/lessons-learned.md
    │
    ├── Severity critical/high?
    │   ├── YES → Update .claude/rules/{category}.md in SAME commit
    │   └── NO  → Lesson stays in log as reference
    │
    └── End of session → Write retrospective in handoff note
                              │
                         Team lead reviews
                              │
                         Same mistake by 2+ builders?
                              │
                         YES → Promote to CLAUDE.md
```

---

## BUILDER PROMPT ADDITION

Add this to every builder agent file:

```
CONTINUOUS LEARNING RULES:
- Before starting work, read docs/lessons-learned.md for recent discoveries
- When you encounter a non-obvious bug (took >5 min to debug), add a LESSON entry
- When the lesson is critical or high severity, update the relevant .claude/rules/ file
- When ending a session, write a retrospective in your handoff note
- Never silently fix a bug — always document what you learned
```

---

## FILES TO CREATE IN REPO

```bash
# Create the files before launch
touch docs/lessons-learned.md
touch docs/anti-patterns.md

# Add headers
echo "# Lessons Learned Log" > docs/lessons-learned.md
echo "" >> docs/lessons-learned.md
echo "Entries added by builders during the build. Critical/high severity lessons are propagated to .claude/rules/ files." >> docs/lessons-learned.md

echo "# Anti-Pattern Registry" > docs/anti-patterns.md
echo "" >> docs/anti-patterns.md  
echo "Growing list of patterns to avoid. Discovered during build. Read by all builders." >> docs/anti-patterns.md

git add docs/lessons-learned.md docs/anti-patterns.md
git commit -m "docs: add continuous learning system files"
```
