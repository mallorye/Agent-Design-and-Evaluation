# Methodology (outline)

COMP 4991 · Mallory Berg · as of Sat Nov 7, 2026

Outline assembled by Claude Opus 5.5 from Mallory's decisions and project files. The design is hers. The final paper is written by her and does not reuse this text.

## 1. Question and thesis
- Question: can an agent ask the right questions about a data request?
- Thesis: the reason to build an agent is deciding *when* to ask, answer, or hand off, not the ability to ask. Intake is where the ambiguity lives: requesters often don't know what they need, or why it matters.
- Comparison points:
  - Never ask: the baseline (single turn, cannot ask).
  - Always ask: computed from the labels, not run. Right on 9 ask tasks, wrong on 15 answer and 6 abstain tasks (9/30).
  - The agent has to beat both.

## 2. Environment
- Postgres 18 in Docker Compose; synthetic advancement schema (designation, constituent, contribution, contact_preference, constituent_relationship, degree); read-only `agent_reader` role.
- Today is fixed at Sept 23, 2026. Contribution data starts FY23. FY27 is partial.
- Data dictionary v2 (`data_dictionary_v2.txt`):
  - Governed definitions (commitment and cash, donor count, parent, contactable, householding, sender scope, and others).
  - Five ambiguity dimensions: year_basis (default fiscal), counting_basis (default commitment), credit_scope (no default), contactable_scope (no default), entity_scope (default university-wide). missing_input is a sixth ask dimension with no dictionary block.
  - 20 published-figure keys, used by `check_reference`.
  - Routing rules for four roles.

## 3. Eval set
- 30 tasks: 25 numbered plus B1–B5. 15 answer / 9 ask / 6 abstain. Labeled copy: `docs/eval_set_v1.md`; rater copy: `docs/eval_set_v1_rater.md`.
- Gold SQL (`db/gold.sql`) for every answer and ask task, plus abstain task 14 (abstain with output).
- Each ask task has its gold dimension(s), one scripted reply per dimension, and a reading line (the clarified spec). B3 has two dimensions.
- Second rater, first pass: 15 tasks, 6/15 agreement (κ ≈ 0.1). Disagreements sorted into guide gaps, task wording, and misreads. Second pass pending, using the rater copy.
- Pre-freeze changes (one paragraph in the paper):
  - Wording: 1, 4, 9, 17, 24, B3, B5.
  - Labels: 1 and 2 → credit_scope; B3 → credit_scope + contactable_scope (purpose removed from the request); 14 → abstain with output.
  - Log: `claude/gold_sql_change_log.md` (project).

## 4. Conditions
- Baseline (`baseline.py`): one call; schema and dictionary in context; emits SQL; cannot ask.
- Agent (`agent_v1.py`):
  - Hand-coded tool loop on the raw API. Model in current runs: anthropic/claude-sonnet-5.5.
  - Five tools: ask_user, run_query, check_reference, submit_answer, abstain.
  - Caps: 3 asks and 30 calls (enforced in code); 3 reruns (stated in the prompt only).
- Prompt v2 (`system_prompt_v2.txt`): three sections (setup, tools, decision guidelines). It replaces v1's numbered procedure, following Connin's Oct 27 feedback.
- Decision guidelines in v2:
  - Ask when a dimension the request leaves open has no default; when a request reads like a contact list but states no purpose; or when a stated use doesn't fit the default.
  - Aggregates are checked against a published figure. With no figure and no source of truth to check against, abstain with output and route to an analyst.
  - Abstain when a request is outside the data or the office.

## 5. Simulator
- Scripted replies keyed on (task, dimension), with a fallback for any other dimension.
- Until the harness exists, replies are typed by hand at `input()` and must match the gold reply word for word.

## 6. Scoring
- Decision: did the agent ask, and was its final move submit or abstain.
- Dimension, by the covering rule: an ask task passes if the agent's asks cover every gold dimension, in any order. Each call covers one dimension.
- Result set: order- and name-insensitive compare against gold.
- Abstain: has_output checked. The route is not scored.
- Explanation tasks (10, 25): checklist.
- Repetitions: k = 5; pass@1 and pass^5; oracle-clarification condition. Harness in Inspect.
- Judgment tasks reported separately (proposed: B3, 9, 16, B4).
- Trajectories (what the agent checked, in what order, how many queries, what it caught) are described, not scored.

## 7. Judge protocol
- LLM judge scores question quality on three items: targets the right dimension, offers the governed options, asks a single question.
- At least 50 hand-labeled questions; second rater on at least 15. Cohen's κ for judge vs. human and human vs. human.

## 8. Limitations and known issues
- The dictionary disagrees with itself on credit: credit_scope says must ask, while the commitment and cash definitions settle it.
- Authorization (who's asking, FERPA) is out of scope. v1 assumes the requester is authorized; access control sits outside the agent.
- Purpose before personal data is tested by one task only (B3). B4 is the no-ask control.
- B3's result set is the same under either contact purpose, so only the dimension check shows whether the agent used the reply.
- Do-not-contact is left for the requester to filter on solicitation lists.
- Abstain is a small, label-only category.

## 9. Open before the full run
- Task 16: year_basis has a default, so neither ask guideline reaches the gold ask. Possible path: its published figures are calendar 2026.
- Task 23: labeled counting_basis, which has a default; the open question is what "notable" means.
- Prompt v2: task 15 (donor audit) isn't covered by the abstain guideline.
- `agent_v1.py` line 305 logs `prompt_version` as `system_prompt.txt` for v2 runs.
- Simulator and scorers not built yet.
