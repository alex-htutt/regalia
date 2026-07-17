# course-setup — checks

Sanity checks for the `course-setup` skill. They don't run automatically here (the skill isn't registered in this session) — use them once it's installed, or via the `skill-creator` skill which automates them.

## `trigger-eval.json`
Should-trigger vs. should-not-trigger queries. Verifies the skill fires on coursework-setup requests and stays quiet on the near-misses: general (non-course) calendar/reminders, non-course project scaffolding, plain concept questions, non-syllabus PDFs, spreadsheet/email tasks, simple lookups from an existing note, and requests to hand over submittable graded answers (blocked by the AI-policy guardrail).

## `evals.json`
End-to-end task prompts to run the skill against, each with a note on the expected result (scaffold, study materials, calendar, practice exam).

## How to run
- **Triggering:** register the skill (Settings → Capabilities), then send each `trigger-eval.json` query in a fresh chat and check whether the skill loads. It should fire on the `true` cases and not the `false` ones.
- **Behavior:** run each `evals.json` prompt against the installed skill and compare to `expected_output`.
- **Automated:** point the `skill-creator` skill at this folder to run trigger/description optimization and task evals.
