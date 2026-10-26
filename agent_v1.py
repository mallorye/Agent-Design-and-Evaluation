################################################################################################
#### Agent v_1
### 
###  An agent that takes a data request, evaluates if it needs more information, runs sql and
###  chooses to ask more questions, fulfill the request or abstain and call a human analyst in 
###  for feedback and support.
###
################################################################################################

#libraries
import os
from openai import OpenAI

from dotenv import load_dotenv
import json
from datetime import datetime, timezone
from db_sql import run_sql
import pandas as pd

## Setting up API key

load_dotenv()

api_key = os.getenv("OPENROUTER_API_KEY")
if not api_key:
    raise ValueError("OPENROUTER_API_KEY not found")

client = OpenAI(
    api_key=api_key,
    base_url="https://openrouter.ai/api/v1"
)
print("OpenRouter client created successfully!")

#model selection
model="anthropic/claude-sonnet-5.5"

#for logs
os.makedirs("logs", exist_ok=True)

## Tool Calls



def ask_user(dimension, question):
    """
    Allows you to ask a user question about a pre-defined dimension and get an answer back.
    """
    print(f'Dimension: {dimension}')
    print(f'Question: {question}')
    return(input())

def check_reference(metric, value):
    """
    Compares aggregated data value against data table. Name of metrics in initial data dictionary.
    """
    validated_df = pd.read_csv('validation_lookup.csv')
    rows =  validated_df[validated_df["metric"] == metric]
    if rows.empty:
        return (f'No matching figure in look up table.{validated_df["metric"].tolist()}')
    published = float(rows.iloc[0]["value"])   
    if abs(published - float(value)) < 0.01:
        return (f'Match: {rows}')
    else:
        return (f'Mismatch: data table has {published} vs {value}')

def sql_handler(sql, preview_rows = 200):
    results , error = run_sql(sql)
    if error is not None:
            return({"error": error})
    else:
        return {"row_count":len(results),"rows":results[:min(preview_rows, 200)]}


def submit_answer(sql, result):
     """
     Terminal call. In deployment sends answer or data set to end user.
     Here it ends run and returns what the agent submitted for logging.
     """
     return({"sql":sql, "result" :result})



def abstain(route_to, has_output, reason,sql= None, result= None ):
     """
     If output, deliver to analyst, if none, route to analyst or partner
     """
     return({"route_to":route_to,"has_output":has_output,"reason":reason,"sql":sql,"result":result})


#API Call to provide a tool


tools_defined = [
    {
        "type": "function",
        "function": {
            "name": "ask_user",
            "description": "Ask the requester one clarifying question about a pre-defined ambiguity dimension and get their answer back. Use only when the data dictionary does not settle the reading.",
            "parameters": {
                "type": "object",
                "properties": {
                    "dimension": {
                        "type": "string",
                        "enum": ["year_basis", "counting_basis", "credit_scope", "contactable_scope", "entity_scope"],
                        "description": "The ambiguity dimension the question is about."
                    },
                    "question": {
                        "type": "string",
                        "description": "The question to ask, in plain language."
                    }
                },
                "required": ["dimension", "question"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "check_reference",
            "description": "Compares aggregated data value against data table.Use a key from the Published figures list in the data dictionary, exactly as written.",
            "parameters": {
                "type": "object",
                "properties": {
                    "metric": {
                        "type": "string",
                        "description": "Name of aggregated measure being asked for."
                    },
                    "value": {
                        "type": "number",
                        "description": "Aggregated measure to be evaluted by function."
                    }
                },
                "required": ["metric", "value"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "run_query",
            "description": "Executes sql queries against posgress db with synth_advancement schema.Do not add LIMIT for inspection; use preview_rows. ",
            "parameters": {
                "type": "object",
                "properties": {
                    "sql": {
                        "type": "string",
                        "description": "Run SQL query against postgres database as read only user. Will return a max of 200 rows and total number of output."
                    },
                    "preview_rows": {
                        "type": "integer",
                        "description": "Optionally select number of preview rows up to 200. Default is 200."
                    },
                },
                "required": ["sql"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "submit_answer",
            "description": "Terminal call. Use only after the result has passed your checks. This ends the run. ",
            "parameters": {
                "type": "object",
                "properties": {
                    "sql": {
                        "type": "string",
                        "description": "Submit sql code used to produce the result"
                    },
                    "result": {
                        "type": "string",
                        "description": "Deliver requested data. A short summary: the number for an aggregate, or the row count and one line describing a list"
                    },
                },
                "required": ["sql", "result"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "abstain",
            "description": "Terminal call. If output, deliver to analyst, if none, route to analyst or partner.Consult enum key and data_dictionary_v1.txt to see who to route to. ",
            "parameters": {
                "type": "object",
                "properties": {
                    "route_to": {
                        "type": "string",
                        "description": "Select a user role from enum based on 'End User Routing Rules'",
                        "enum": ["Analytics_Director", "Fundraising_Analyst", "Communication_Analyst", "Registrar_Representative"]
                    },
                    "has_output": {
                        "type": "boolean",
                        "description": "Yes or no on whether a data artifact exists or not."
                    },
                    "reason": {
                        "type": "string",
                        "description": "Why the abstain option was chosen- failed data checks, which one failed, or no access to data or other."
                    },
                    "sql": {
                        "type": "string",
                        "description": "SQL script created for result."
                    },
                    "result": {
                        "type": "string",
                        "description": "Output of SQL script"
                    },
                },
                "required": ["route_to", "has_output", "reason"]
            }
        }
    }
]

dispatcher_dictionary = {"ask_user": ask_user, "check_reference": check_reference, "run_query": sql_handler, "submit_answer": submit_answer, "abstain": abstain}

#for logs
os.makedirs("logs", exist_ok=True)

### System Content Message and Resources

system_prompt = open("system_prompt.txt").read()
database_schema = open("db/init/01_schema.sql").read()
data_dictionary = open("data_dictionary_v1.txt").read()

system_content = f"{system_prompt}\n\n## DATABASE SCHEMA\n{database_schema}\n\n## DATA DICTIONARY\n{data_dictionary}"

## Original 5 User Data Requests
data_requests = ["What is the size of our contactable base?",
"How many parents are in our database?",
"Can you get me a household lists of donors to the School of Business who have given a lifetime amount of over $500",
"Who gave last fiscal year but not this fiscal year?",
"What is our commitment  fundraising total this year so far?"]




def call_model(messages,model):
    """
    Calling model with initial tools and messages
    """
    r = client.chat.completions.create(
            model=model,
            messages=messages,
            tools = tools_defined,
            temperature= 0,
            max_tokens= 8000,
        )
    output =  r.choices[0].message
    return output
    





def run_task(request):
    """
    Building each request out fresh.
    """
    messages = [{"role": "system", "content": system_content},
                {"role": "user", "content": request}]
    asks = 0
    calls = 0
    final_move = None
    while True:
        reply = call_model(messages,model)
        calls += 1
        messages.append(reply)

        if not reply.tool_calls:
            final_move = "malformed"    
            break

        name = ''    

        for call in reply.tool_calls:
            name = call.function.name
            args = json.loads(call.function.arguments)
            result = dispatcher_dictionary[call.function.name](**args)
            messages.append({
                "role" : "tool",
                "tool_call_id": call.id,
                "content": json.dumps(result, default=str)
            })
        if name == "ask_user":
                asks += 1

        if name in ("submit_answer", "abstain"):
                final_move = name
                break

        if asks >3 or calls > 30:
                final_move = "Cap"
                break

    return {"request": request, "messages": messages, "final_move": final_move, "asks": asks, "calls": calls}            

def log_run(log_path, run, model):
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "condition": "Agent",
        "model": model,                    
        "system_version": "v1",  
        "prompt_version" : "system_prompt.txt",
        "dictionary_version": "data_dictionary_v1.txt",
        "request": run["request"],
        "final_move": run["final_move"],
        "calls":run["calls"],
        "asks": run["asks"],
        "messages": [m if isinstance(m,dict) else m.model_dump() for m in run["messages"]]
    }
    with open(log_path, "a") as f:
        f.write(json.dumps(record, default=str) + "\n") 

for x in data_requests:
   
   out = run_task(x)
   log_run("logs/agent_runs.jsonl",out,model)
   break #TO-DO- remove break. Put here temporariliy to just run one question.
