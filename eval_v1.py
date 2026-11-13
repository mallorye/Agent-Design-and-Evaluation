###  Eval using Inspect
### Initial spine drafted by Claude Fable 5.2 as an example at Mallory's request (2026-11-10).

################################################################################################

from inspect_ai import Task, task
from inspect_ai.dataset import Sample, json_dataset
from inspect_ai.scorer import CORRECT, INCORRECT, Score, Target, accuracy, scorer
from inspect_ai.solver import Generate, TaskState, solver

from agent_v1 import run_task


#1- Dataset - turning one row of tasks.jsonl into one Inspect sample
def record_to_sample(record):
    return Sample(
        input=record["request"],
        id=record["id"],
        target=record["label"],
        metadata={"replies": record["replies"]},
    )


#2. Solver - calling agent, and storing what came bacck
@solver
def agent_solver():
    async def solve(state: TaskState, generate: Generate):
        out = run_task(state.input_text, state.metadata["replies"])
        state.store.set("final_move", out["final_move"])
        state.store.set("asks", out["asks"])
        state.store.set("calls", out["calls"])
        state.store.set("messages", [m if isinstance(m,dict) else m.model_dump() for m in out["messages"]])
        return state

    return solve

# 3. Scorer: scores ask/answer/abstain against the tasks.json log
@scorer(metrics=[accuracy()])
def decision_scorer():
    async def score(state: TaskState, target: Target):
        final_move = state.store.get("final_move")
        asks = state.store.get("asks")
        if final_move == "abstain":
            decision = "abstain"
        elif asks > 0:
            decision = "ask"
        else:
            decision = "answer"
        return Score(
            value=CORRECT if decision == target.text else INCORRECT,
            answer=decision,
        )

    return score

@task
def agent_eval():
    return Task(
        dataset=json_dataset("tasks.jsonl", record_to_sample),
        solver=agent_solver(),
        scorer=decision_scorer(),
        epochs=5
    )