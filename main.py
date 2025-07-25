@app.route('/db_status')
def db_status():
    import sys
    try:
        with get_db_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                # 檢查 samples 資料表是否存在
                cur.execute("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables 
                        WHERE table_name = 'samples'
                    )
                """)
                exists = cur.fetchone()[0]
        return f"DB連線成功，samples資料表存在：{exists}"
    except Exception as e:
        print("DB health check error:", e, file=sys.stderr)
        return f"DB連線失敗或資料表不存在：{e}", 500



import os
import psycopg2
import pandas as pd
from flask import Flask, request, render_template_string, redirect, url_for
from werkzeug.datastructures import MultiDict

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 2 * 1024 * 1024  # 限制上傳檔案最大2MB

# PostgreSQL連線（用環境變數管理）
def get_db_conn():
    return psycopg2.connect(
        dbname=os.environ.get("DB_NAME"),
        user=os.environ.get("DB_USER"),
        password=os.environ.get("DB_PASS"),
        host=os.environ.get("DB_SOCKET", "/cloudsql/pathology-database-portal:asia-east1:wildone"),
    )

def init_db():
    with get_db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute('''
                CREATE TABLE IF NOT EXISTS samples (
                    id SERIAL PRIMARY KEY,
                    pathology_id TEXT,
                    species TEXT,
                    species_type TEXT,
                    gender TEXT,
                    age TEXT,
                    doctor TEXT,
                    send_date TEXT,
                    exam_item TEXT,
                    sample_type TEXT,
                    sample TEXT,
                    lab TEXT,
                    lab_code TEXT,
                    report TEXT,
                    cloud_link TEXT
                )
            ''')
            tables = [
                'doctors', 'species', 'species_type', 'gender', 'age',
                'exam_items', 'sample_types', 'labs'
            ]
            for table in tables:
                cur.execute(
                    f'CREATE TABLE IF NOT EXISTS {table} (id SERIAL PRIMARY KEY, name TEXT UNIQUE)'
                )
        conn.commit()

def get_all(table):
    with get_db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(f"SELECT * FROM {table} ORDER BY name")
            return [row[1] for row in cur.fetchall()]

@app.route('/lists', methods=['GET', 'POST'])
def lists():
    types = {
        "doctors": "主治醫師",
        "species": "物種",
        "species_type": "物種類別",
        "gender": "性別",
        "age": "年齡",
        "exam_items": "送驗項目",
        "sample_types": "檢體類型",
        "labs": "送檢單位"
    }
    t = request.args.get('type', 'doctors')
    msg = ""
    if request.method == 'POST' and 'name' in request.form:
        name = request.form.get('name', '').strip()
        if name:
            try:
                with get_db_conn() as conn:
                    with conn.cursor() as cur:
                        cur.execute(f"INSERT INTO {t} (name) VALUES (%s)", (name,))
                    conn.commit()
                msg = "新增成功"
            except psycopg2.errors.UniqueViolation:
                msg = "名稱重複"
            except Exception as e:
                msg = f"新增失敗: {e}"
    delete_id = request.args.get('delete')
    if delete_id:
        with get_db_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(f"DELETE FROM {t} WHERE id=%s", (delete_id,))
            conn.commit()
        return redirect(url_for('lists', type=t))
    with get_db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(f"SELECT id, name FROM {t} ORDER BY name")
            items = cur.fetchall()
    tab_html = ' | '.join([f'<a href="?type={x}" {"style=color:red" if t==x else ""}>{types[x]}</a>' for x in types])
    import_html = f'<a href="/import_list/{t}">⬆️ 批次匯入</a>'
    return render_template_string('''
        <h2>清單管理</h2>
        <div>{{tab_html|safe}}</div>
        <br>
        <form method="POST">
            新增{{types[t]}}：<input name="name" required>
            <input type="submit" value="新增">
            {{msg}}
        </form>
        {{import_html|safe}}
        <table border="1">
            <tr><th>名稱</th><th>操作</th></tr>
            {% for i in items %}
            <tr>
                <td>{{i[1]}}</td>
                <td>
                    <a href="?type={{t}}&delete={{i[0]}}" onclick="return confirm('確定刪除？')">刪除</a>
                </td>
            </tr>
            {% endfor %}
        </table>
        <br>
        <a href="/">🏠 回首頁</a>
    ''', t=t, types=types, items=items, tab_html=tab_html, msg=msg, import_html=import_html)

@app.route('/import_list/<table>', methods=['GET', 'POST'])
def import_list(table):
    allowed = ['doctors', 'species', 'species_type', 'gender', 'age', 'exam_items', 'sample_types', 'labs']
    msg = ""
    preview = None
    if table not in allowed:
        return "不允許的清單表格"
    if request.method == 'POST' and 'file' in request.files:
        file = request.files['file']
        filename = file.filename
        if not (filename.endswith('.csv') or filename.endswith('.xlsx')):
            msg = "只支援CSV或Excel檔案"
        else:
            try:
                if filename.endswith('.csv'):
                    df = pd.read_csv(file, encoding="utf-8")
                else:
                    df = pd.read_excel(file)
                names = df.iloc[:,0].dropna().astype(str).map(lambda x: x.strip())
                count = 0
                dup = 0
                for name in names:
                    try:
                        with get_db_conn() as conn:
                            with conn.cursor() as cur:
                                cur.execute(f"INSERT INTO {table} (name) VALUES (%s)", (name,))
                            conn.commit()
                        count += 1
                    except psycopg2.errors.UniqueViolation:
                        dup += 1
                        continue
                    except Exception:
                        dup += 1
                        continue
                msg = f"匯入完成，共新增 {count} 筆，重複略過 {dup} 筆。"
                preview = names.tolist()
            except Exception as e:
                msg = f"檔案處理失敗: {e}"
    return render_template_string('''
        <h2>批次匯入清單 ({{table}})</h2>
        <form method="POST" enctype="multipart/form-data">
          <input type="file" name="file" required>
          <input type="submit" value="上傳">
        </form>
        <div style="color:green;">{{msg}}</div>
        {% if preview %}
        <div>
          <b>上傳內容預覽 (僅顯示前20筆):</b>
          <ul>
          {% for name in preview[:20] %}
            <li>{{name}}</li>
          {% endfor %}
          </ul>
        </div>
        {% endif %}
        <a href="/lists?type={{table}}">返回清單管理</a>
    ''', table=table, msg=msg, preview=preview)

@app.route('/import_samples', methods=['GET', 'POST'])
def import_samples():
    msg = ""
    preview = None
    if request.method == 'POST' and 'file' in request.files:
        file = request.files['file']
        filename = file.filename
        if not (filename.endswith('.csv') or filename.endswith('.xlsx')):
            msg = "只支援CSV或Excel檔案"
        else:
            try:
                if filename.endswith('.csv'):
                    df = pd.read_csv(file, encoding="utf-8")
                else:
                    df = pd.read_excel(file)
                required_cols = ['pathology_id', 'species', 'species_type', 'gender', 'age', 'doctor', 'send_date', 'exam_item', 'sample_type', 'sample', 'lab', 'lab_code', 'report', 'cloud_link']
                for col in required_cols:
                    if col not in df.columns:
                        df[col] = ""
                count = 0
                dup = 0
                for _, row in df.iterrows():
                    values = tuple(row[col] for col in required_cols)
                    try:
                        with get_db_conn() as conn:
                            with conn.cursor() as cur:
                                cur.execute("""
                                    INSERT INTO samples (
                                        pathology_id, species, species_type, gender, age, doctor, send_date,
                                        exam_item, sample_type, sample, lab, lab_code, report, cloud_link
                                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                                """, values)
                            conn.commit()
                        count += 1
                    except psycopg2.errors.UniqueViolation:
                        dup += 1
                        continue
                    except Exception:
                        dup += 1
                        continue
                msg = f"匯入完成，共新增 {count} 筆 (資料重複/錯誤略過 {dup} 筆)。"
                preview = df.head(20).to_dict(orient='records')
            except Exception as e:
                msg = f"檔案處理失敗: {e}"
    return render_template_string('''
        <h2>批次匯入物種/送檢資訊</h2>
        <form method="POST" enctype="multipart/form-data">
          <input type="file" name="file" required>
          <input type="submit" value="上傳">
        </form>
        <div style="color:green;">{{msg}}</div>
        {% if preview %}
        <div>
          <b>上傳內容預覽 (僅顯示前20筆):</b>
          <table border="1">
            <tr>
              {% for k in preview[0].keys() %}
              <th>{{k}}</th>
              {% endfor %}
            </tr>
            {% for row in preview %}
            <tr>
              {% for v in row.values() %}
              <td>{{v}}</td>
              {% endfor %}
            </tr>
            {% endfor %}
          </table>
        </div>
        {% endif %}
        <a href="/">🏠 回首頁</a>
    ''', msg=msg, preview=preview)

@app.route('/', methods=['GET', 'POST'])
def form():
    species_types = get_all('species')
    species = get_all('species_type')
    genders = get_all('gender')
    ages = get_all('age')
    doctors = get_all('doctors')
    exam_items = get_all('exam_items')
    sample_types = get_all('sample_types')
    labs = get_all('labs')
    return render_template_string(''' ... ''', species=species, species_types=species_types, genders=genders, ages=ages, doctors=doctors,
         exam_items=exam_items, sample_types=sample_types, labs=labs)

@app.route('/submit', methods=['POST'])
def submit():
    data = (
        request.form.get('pathology_id', ''),
        request.form.get('species', ''),
        request.form.get('species_type', ''),
        request.form.get('gender', ''),
        request.form.get('age', ''),
        request.form.get('doctor', ''),
        request.form.get('send_date', ''),
        request.form.get('exam_item', ''),
        request.form.get('sample_type', ''),
        request.form.get('sample', ''),
        request.form.get('lab', ''),
        request.form.get('lab_code', ''),
        request.form.get('report', ''),
        request.form.get('cloud_link', ''),
    )
    with get_db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO samples (
                    pathology_id, species, species_type, gender, age, doctor, send_date,
                    exam_item, sample_type, sample, lab, lab_code, report, cloud_link
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, data)
        conn.commit()
    return redirect(url_for('form'))
