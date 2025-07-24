import os
import psycopg2
from flask import Flask

app = Flask(__name__)

def get_db_conn():
    return psycopg2.connect(
        host=os.environ.get("DB_HOST", "127.0.0.1"),
        port=int(os.environ.get("DB_PORT", 5432)),
        dbname=os.environ.get("DB_NAME", "Pathology-DataBase"),
        user=os.environ.get("DB_USER", "wildone"),
        password=os.environ.get("DB_PASS", "81148165")
    )

@app.route("/")
def hello():
    return "Cloud Run + Cloud SQL (Postgres) minimal demo!"

@app.route("/db_status")
def db_status():
    try:
        with get_db_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT NOW()")
                now = cur.fetchone()[0]
        return f"DB連線成功，Postgres時間：{now}"
    except Exception as e:
        return f"DB連線失敗：{e}"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
