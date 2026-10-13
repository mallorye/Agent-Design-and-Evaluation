################################################################################################
#### Baseline Request
#### Feed 5 hand written request to a model with a schema and data dictionary at hand. 
###  Handle output
################################################################################################

#libraries
import os
from openai import OpenAI
from dotenv import load_dotenv, find_dotenv
import psycopg
from dotenv import load_dotenv
import json
from datetime import datetime, timezone

## Setting up API key

load_dotenv()

### Setting up OpenAI connection

api_key = os.getenv("OPENROUTER_API_KEY")
if not api_key:
    raise ValueError("OPENROUTER_API_KEY not found — check your .env file")

client = OpenAI(
    api_key=api_key,
    base_url="https://openrouter.ai/api/v1"
)
print("OpenRouter client created successfully!")

#model selection
model="anthropic/claude-sonnet-5.5"

#for logs
os.makedirs("logs", exist_ok=True)

### System Content Message and Resources

system_message = """
You are here to turn a data request into a runnable sql query. You will be given a schema and a data dictionary. 
Return exactly one query in a ``` sql fenced block, nothing else.
"""
database_schema = open("db/init/01_schema.sql").read()
data_dictionary = open("data_dictionary_v0.txt").read()

system_content = f"{system_message}\n\n## DATABASE SCHEMA\n{database_schema}\n\n## DATA DICTIONARY\n{data_dictionary}"

## User Data Request
data_requests = ["What is the size of our contactable base?",
"How many parents are in our database?",
"Can you get me a household lists of donors to the School of Business who have given a lifetime amount of over $500",
"Who gave last fiscal year but not this fiscal year?",
"What is our commitment  fundraising total this year so far?"]





## 
def call_model(system_content, data_request,model):
    try:
        r = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_content},
                {"role": "user", "content": data_request},
            ],
            temperature= 0,
            max_tokens= 8000,
        )
        output =  r.choices[0].message.content.strip()
        return output
    except Exception as e:
        error_m =  f"[error: {e}]"
        return error_m

## Setting up SQL to run OUTPUT##
def sql_output_evaluate(output):
    if "error:" in output:
        print(output)
    else:
        #remove sql indicator
        clean_1 = output.replace("```sql","")
        clean = clean_1.replace("```","")
        return clean


#connect to PosgressDB as a user  and send output to get results

def run_sql(sql: str):
    """Execute extracted SQL as agent_reader; return (rows, error) — exactly one is None."""
    conninfo = (
        f"host={os.getenv('DB_HOST')} port={os.getenv('DB_PORT')} "
        f"dbname={os.getenv('DB_NAME')} user={os.getenv('DB_USER')} "
        f"password={os.getenv('DB_PASSWORD')}"
    )
    try:
        with psycopg.connect(conninfo) as conn:
            with conn.cursor() as cur:
                cur.execute(sql)
                return cur.fetchall(), None
    except psycopg.Error as e:
        return None, str(e)

##Creating Logging 



def log_run(log_path, data_request, output, sql_query, results, error,
            model):
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "condition": "Baseline",
        "model": model,                    
        "system_version": "v0",  
        "request": data_request,
        "response_text": output,    
        "sql": sql_query,                        # extracted; None if extraction failed
        "rows": results,                      # None on failure
        "row_count": len(results) if results is not None else None,
        "error": error,                    # None on success
    }
    with open(log_path, "a") as f:
        f.write(json.dumps(record, default=str) + "\n")


for data_request in data_requests:
    output = call_model(system_content, data_request,model) 
    sql_query = sql_output_evaluate(output)
    if sql_query is None:
        log_run("logs/baseline_runs.jsonl", data_request, output, None, None, "extraction failed", model)
        continue
    results, error = run_sql(sql_query)
    log_run("logs/baseline_runs.jsonl",data_request,output,sql_query,results,error,model)
    print("error")
    print(error)
    print("results")
    print(results)

