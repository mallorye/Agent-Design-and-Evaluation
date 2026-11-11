###  Eval using Inspect
### Initial spine drafted by Claude Fable 5.2 as an example at Mallory's request (2026-11-10).
# The scorer applies her rule that the final move is scored per task.
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
        target=record["final_move"],
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
        return state

    return solve

# 3. Scorer: a placeholder that compares the final move to the label
@scorer(metrics=[accuracy()])
def final_move_scorer():
    async def score(state: TaskState, target: Target):
        final_move = state.store.get("final_move")
        return Score(
            value=CORRECT if final_move == target.text else INCORRECT,
            answer=final_move,
        )

    return score

@task
def agent_eval():
    return Task(
        dataset=json_dataset("tasks.jsonl", record_to_sample)[0:1],
        solver=agent_solver(),
        scorer=final_move_scorer(),
    )