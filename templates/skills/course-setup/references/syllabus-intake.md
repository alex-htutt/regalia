# Syllabus & lecture intake

Goal: turn an uploaded syllabus/lecture PDF into a filled-in `_context_<slug>.md`. The user often drops the
PDF straight into the course folder.

- **Extract text** with `pdftotext -layout <file> -` in the shell (fast and reliable for dates/tables). For image-only/scanned PDFs, use the Read tool instead.
- **Pull into the context file:** instructor + contact, section/CRN + modality, meeting days/times, prerequisite, grading breakdown + grade scale, term start/end, exam and assessment dates, textbook + links (Canvas/course site), and the full course calendar.
- **Never fabricate.** If the syllabus doesn't state something (e.g. weekly meeting times for an online section), write `_TBD_` and say so — a wrong instructor/date/prereq costs far more to unwind than an honest gap.
- **Flag discrepancies** between the syllabus and the public catalog (e.g. prerequisite or GE area) rather than silently picking one.
- **Capture the course's AI policy** into the context file if present — it governs how much help you can give on graded work (see SKILL.md → Guardrails).
- **Finish:** update the context file's "Current state", then verify (frontmatter valid, `deadline` set to the term/exam end, wikilinks resolve).
