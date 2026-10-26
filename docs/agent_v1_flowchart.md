
# Agent v1 flow
# Drawn Oct 20, 2026
# matches agent_v1.py 

```mermaid
flowchart LR
    REQ([Agent receives a request]) --> Q1{Can it be answered with dictionary & schema?}
    Q1 -- No --> Q2{Could it be answered with clarification?}
    Q2 -- Yes --> ASK[ask_user]
    ASK --> Q1
    Q2 -- No --> ABS([abstain])
    Q1 -- Yes --> GEN[Generate SQL]
    GEN --> RUN[run_sql]
    RUN --> HEALTH[Evaluate output: dates, nulls, counts plausible]
    HEALTH --> TEST[run_sql: test query]
    TEST --> AGG{Aggregate?}
    AGG -- Yes --> REF[check_reference]
    AGG -- No --> PASS{Pass checks run?}
    REF --> PASS
    PASS -- Yes --> SUB([submit_answer])
    PASS -- No --> RETRY{Try again?}
    RETRY -- Yes --> GEN
    RETRY -- No --> ABS
```

**Tools (5)**: ask_user(dimension, question) · run_sql(sql) · check_reference(metric) · submit_answer(sql, result) · abstain(route_to, has_output, reason)

Prompt instructions: state ask / answer / abstain before acting · if asking, name the dimension from the five · state whether the request yields a number, a list, or an explanation · before submitting, state whether the result is plausible · a question about the data is answered in text and supported by a query

**Caps**: ask_user 3 · try_again 3 · 30 calls per run

**Run ends on**: submit_answer, abstain, a cap, or an error (logged)