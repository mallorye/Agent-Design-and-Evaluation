"""
compare_to_gold.py
Written by Claude Fable 5.2 at Mallory's request (2026-11-14). The code is AI-written.

The match rule is Mallory's, decided 2026-11-14:
  - A list: the IDs in the agent's result are the same IDs as in the gold result.
    Extra columns, column names and row order do not matter.
  - A total: within $1. A count: the same number.
  - Totals that come in groups (by year, by unit): every group's number has to match.
  - Explanation requests: not compared here. Mallory reads those.
  - Anything the rule cannot call a match or a miss is marked "review" for Mallory to read.

What it does:
  Reads a saved Inspect log. For every run where the agent submitted an answer, it runs the
  SQL the agent submitted and the gold SQL for that request (from tasks.jsonl), both through
  db_sql.run_sql, which is the same read-only connection the agent uses. Then it compares
  the two results by the rule above. No model is called. The log is not changed.

Run from the repo root, with Docker up:
    python3 compare_to_gold.py logs/<log file>.eval

Writes a CSV next to the log, named <log file>-gold-comparison.csv, with one row per run.
"""
import csv
import json
import re
import sys
from collections import Counter
from decimal import Decimal, InvalidOperation
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from inspect_ai.log import read_eval_log  # noqa: E402

from db_sql import run_sql  # noqa: E402

DOLLAR_TOLERANCE = Decimal("1.00")
TASKS_FILE = "tasks.jsonl"


# ---------- reading the inputs ----------

def load_tasks(path):
    """tasks.jsonl as a dictionary: request id -> its row."""
    tasks = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                row = json.loads(line)
                tasks[str(row["id"])] = row
    return tasks


def first_statement(sql):
    """Gold SQL can hold comments and more than one statement. Use the first real one."""
    parts = re.split(r";\s*(?:\n|$)", sql)
    real = [p.strip() for p in parts if re.sub(r"--.*", "", p).strip()]
    return real[0] if real else ""


def submitted_sql(messages):
    """The SQL on the agent's submit_answer call, or None if there is none."""
    sql = None
    for message in messages or []:
        for call in message.get("tool_calls") or []:
            if call["function"]["name"] == "submit_answer":
                try:
                    args = json.loads(call["function"]["arguments"])
                except (TypeError, ValueError):
                    args = {}
                sql = args.get("sql") if isinstance(args, dict) else None
    return sql


# ---------- the comparison ----------

def as_id(value):
    """IDs compared as text, so 8, '8' and Decimal('8') are the same ID."""
    if isinstance(value, (int, Decimal)) and not isinstance(value, bool) and value == int(value):
        return str(int(value))
    return str(value).strip()


def as_number(value):
    """A cell as a number, or None. Text like '1,234.50' or '$1,234.50' counts as a number."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float, Decimal)):
        return Decimal(str(value))
    if isinstance(value, str):
        text = value.strip().replace(",", "").replace("$", "")
        if re.fullmatch(r"-?\d+(\.\d+)?", text):
            try:
                return Decimal(text)
            except InvalidOperation:
                return None
    return None


def numbers_in(rows):
    """Every number anywhere in a result."""
    found = []
    for row in rows:
        for value in row.values():
            number = as_number(value)
            if number is not None:
                found.append(number)
    return found


def same_number(gold_value, agent_number):
    """A count has to be the same number. A dollar total has to be within $1."""
    gold_number = as_number(gold_value)
    if gold_number is None:
        return False
    if isinstance(gold_value, int) and not isinstance(gold_value, bool):
        return agent_number == gold_number
    return abs(agent_number - gold_number) <= DOLLAR_TOLERANCE


def compare_list(gold_rows, agent_rows):
    """A list matches when the agent's result holds the same IDs as the gold result."""
    gold_columns = list(gold_rows[0].keys())
    key = "constituent_id" if "constituent_id" in gold_columns else gold_columns[0]
    gold_ids = {as_id(row[key]) for row in gold_rows}
    if not agent_rows:
        return "no match", f"the agent's SQL returned 0 rows; gold has {len(gold_ids)} {key} values"

    agent_columns = list(agent_rows[0].keys())
    # Look at the same-named column first, then any other column that holds exactly the gold IDs.
    ordered = ([key] if key in agent_columns else []) + [c for c in agent_columns if c != key]
    for column in ordered:
        if {as_id(row[column]) for row in agent_rows} == gold_ids:
            return "match", f"same {len(gold_ids)} IDs (gold column {key}, agent column {column})"

    if key in agent_columns:
        agent_ids = {as_id(row[key]) for row in agent_rows}
        missing = len(gold_ids - agent_ids)
        extra = len(agent_ids - gold_ids)
        return "no match", (f"gold has {len(gold_ids)} {key} values, the agent has {len(agent_ids)}: "
                            f"{missing} of gold's are missing, {extra} are extra")
    return "review", (f"no column in the agent's result is named {key} or holds the gold IDs; "
                      f"agent columns: {', '.join(agent_columns)}")


def compare_numbers(gold_rows, agent_rows):
    """Totals and counts. The number to match is the last column of the gold result."""
    measure = list(gold_rows[0].keys())[-1]
    gold_values = [row[measure] for row in gold_rows]
    agent_numbers = numbers_in(agent_rows)

    if len(gold_rows) == 1:
        gold_value = gold_values[0]
        if len(agent_rows) != 1:
            return "review", (f"gold is one number ({measure} = {gold_value}); "
                              f"the agent's SQL returned {len(agent_rows)} rows")
        shown = ", ".join(str(n) for n in agent_numbers[:8]) or "no numbers"
        if any(same_number(gold_value, n) for n in agent_numbers):
            return "match", f"gold {measure} = {gold_value}; found in the agent's row ({shown})"
        return "no match", f"gold {measure} = {gold_value}; the agent's row holds {shown}"

    # Groups: every gold group's number has to be found once in the agent's result.
    pool = list(agent_numbers)
    found = 0
    for gold_value in gold_values:
        for i, number in enumerate(pool):
            if same_number(gold_value, number):
                pool.pop(i)
                found += 1
                break
    verdict = "match" if found == len(gold_values) else "no match"
    return verdict, (f"{found} of {len(gold_values)} group numbers found in the agent's result "
                     f"(gold {len(gold_rows)} rows, agent {len(agent_rows)} rows)")


# ---------- one run ----------

gold_cache = {}


def gold_result(task):
    """Run a request's gold SQL once and keep the result."""
    request_id = str(task["id"])
    if request_id not in gold_cache:
        gold_cache[request_id] = run_sql(first_statement(task["gold_sql"]))
    return gold_cache[request_id]


def compare_run(task, final_move, messages):
    """Returns (verdict, detail, gold row count, agent row count) for one run."""
    kind = task.get("type")
    if final_move != "submit_answer":
        return "not compared", f"the run ended in {final_move}, so there is no answer to compare", "", ""
    if kind == "explanation":
        return "read by Mallory", "explanation request: the gold is an explanation, not rows", "", ""
    if not task.get("gold_sql"):
        return "not compared", "this request has no gold SQL", "", ""

    sql = submitted_sql(messages)
    if not sql:
        return "review", "no SQL found on the submit_answer call", "", ""

    gold_rows, gold_error = gold_result(task)
    if gold_error is not None:
        return "review", f"the gold SQL did not run: {gold_error.splitlines()[0]}", "", ""
    agent_rows, agent_error = run_sql(sql)
    if agent_error is not None:
        return "no match", f"the agent's submitted SQL did not run: {agent_error.splitlines()[0]}", len(gold_rows), ""

    if not gold_rows:
        verdict = "match" if not agent_rows else "no match"
        return verdict, f"gold returns 0 rows; the agent's SQL returns {len(agent_rows)}", 0, len(agent_rows)
    if kind == "list":
        verdict, detail = compare_list(gold_rows, agent_rows)
    elif kind == "aggregate":
        verdict, detail = compare_numbers(gold_rows, agent_rows)
    else:
        verdict, detail = "review", f"request type is {kind}; the rule covers lists and totals"
    return verdict, detail, len(gold_rows), len(agent_rows)


# ---------- the whole log ----------

def main():
    if len(sys.argv) != 2:
        print("Usage: python3 compare_to_gold.py logs/<log file>.eval")
        sys.exit(1)
    log_path = Path(sys.argv[1])
    tasks = load_tasks(TASKS_FILE)
    order = list(tasks.keys())
    log = read_eval_log(str(log_path))
    samples = sorted(log.samples, key=lambda s: (order.index(str(s.id)), s.epoch))

    out_rows = []
    for sample in samples:
        task = tasks[str(sample.id)]
        final_move = sample.store.get("final_move")
        verdict, detail, gold_n, agent_n = compare_run(task, final_move, sample.store.get("messages"))
        out_rows.append({
            "request": str(sample.id), "repeat": sample.epoch, "your_label": task["label"],
            "kind": task.get("type") or "", "final_move": final_move,
            "verdict": verdict, "detail": detail, "gold_rows": gold_n, "agent_rows": agent_n,
        })

    out_path = log_path.with_name(log_path.stem + "-gold-comparison.csv")
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(out_rows[0].keys()))
        writer.writeheader()
        writer.writerows(out_rows)

    submitted = [r for r in out_rows if r["final_move"] == "submit_answer"]
    print(f"\nRuns in the log: {len(out_rows)}. Runs that submitted an answer: {len(submitted)}.")
    print("\nOf the submitted answers:")
    for verdict, n in Counter(r["verdict"] for r in submitted).most_common():
        print(f"  {verdict:<16} {n}")
    print("\nBy your label (match / no match / review / read by Mallory):")
    for label in ("ask", "answer", "abstain"):
        c = Counter(r["verdict"] for r in submitted if r["your_label"] == label)
        print(f"  {label:<8} {c['match']} / {c['no match']} / {c['review']} / {c['read by Mallory']}")
    print(f"\nWrote {out_path}")


if __name__ == "__main__":
    main()
