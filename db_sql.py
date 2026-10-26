import psycopg
import os
from psycopg.rows import dict_row

def run_sql(sql: str):
    """Execute extracted SQL as agent_reader; return (rows, error) """
    conninfo = (
        f"host={os.getenv('DB_HOST')} port={os.getenv('DB_PORT')} "
        f"dbname={os.getenv('DB_NAME')} user={os.getenv('DB_USER')} "
        f"password={os.getenv('DB_PASSWORD')}"
    )
    #limiting use to agent acc
    if os.getenv('DB_USER') == 'agent_reader':
        try:
            with psycopg.connect(conninfo, options="-c default_transaction_read_only=on -c statement_timeout=15000", row_factory = dict_row) as conn:
                with conn.cursor() as cur:
                    cur.execute(sql)
                    return cur.fetchall(), None
        except psycopg.Error as e:
            return None, str(e)
    else:
         return(None, "refused: DB_User is not agent_reader")