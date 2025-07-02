from flask import Flask, request, render_template_string, redirect, url_for, make_response
import psycopg2
import psycopg2.extras
import pandas as pd
import os
import io

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 2 * 1024 * 1024

# 環境變數設置，Cloud Run 上會自動帶入
DB_USER = os.environ.get("DB_USER", "test")
DB_PASS = os.environ.get("DB_PASS", "test")
DB_NAME = os.environ.get("DB_NAME", "postgres")
DB_SOCKET = os.environ.get("DB_SOCKET", "/cloudsql/fabled-coder-463906-b3:asia-east1:my-instance")

def get_conn():
    # 在 Cloud Run 上只用 Unix Socket，避免用 localhost
    return psycopg2.connect(
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASS,
        host=DB_SOCKET,
        cursor_factory=psycopg2.extras.DictCursor
    )

def init_db():
    with get_conn() as conn:
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
                    send_date DATE,
                    exam_type TEXT,
                    sample_type TEXT,
                    sample TEXT,
                    lab TEXT,
                    lab_code TEXT,
                    report TEXT
                )
            ''')
            tables = [
                'doctors', 'species', 'species_type', 'gender', 'age',
                'exam_types', 'sample_types', 'labs'
            ]
            for table in tables:
                cur.execute(f'''CREATE TABLE IF NOT EXISTS {table} (
                    id SERIAL PRIMARY KEY,
                    name TEXT UNIQUE
                )''')
            conn.commit()

def get_all(table):
    with get_conn() as conn:
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
        "exam_types": "檢驗類別",
        "sample_types": "檢體類型",
        "labs": "送檢單位"
    }
    t = request.args.get('type', 'doctors')
    msg = ""
    if request.method == 'POST' and 'name' in request.form:
        name = request.form.get('name', '').strip()
        if name:
            try:
                with get_conn() as conn:
                    with conn.cursor() as cur:
                        cur.execute(f"INSERT INTO {t} (name) VALUES (%s)", (name,))
                        conn.commit()
                msg = "新增成功"
            except Exception:
                msg = "名稱重複或錯誤"
    delete_id = request.args.get('delete')
    if delete_id:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(f"DELETE FROM {t} WHERE id=%s", (delete_id,))
                conn.commit()
        return redirect(url_for('lists', type=t))
    with get_conn() as conn:
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
    allowed = ['doctors', 'species', 'species_type', 'gender', 'age', 'exam_types', 'sample_types', 'labs']
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
                        with get_conn() as conn:
                            with conn.cursor() as cur:
                                cur.execute(f"INSERT INTO {table} (name) VALUES (%s)", (name,))
                                conn.commit()
                        count += 1
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

@app.route('/', methods=['GET', 'POST'])
def form():
    species = get_all('species')
    species_types = get_all('species_type')
    genders = get_all('gender')
    ages = get_all('age')
    doctors = get_all('doctors')
    exam_types = get_all('exam_types')
    sample_types = get_all('sample_types')
    labs = get_all('labs')
    return render_template_string('''
    <style>
    .container { display: flex; gap: 24px; }
    .box { border: 1px solid #888; border-radius: 8px; padding: 16px; min-width: 340px; }
    .box h3 { margin-top:0; }
    .item { margin-bottom: 8px; }
    .item label { width: 110px; display: inline-block; }
    </style>
    <h2>新增送檢紀錄</h2>
    <form method="POST" action="/submit">
    <div class="container">
      <div class="box">
        <h3>物種資訊</h3>
        <div class="item"><label>病理編號</label><input name="pathology_id"></div>
        <div class="item"><label>物種</label>
          <select name="species"><option value="">請選擇</option>{% for x in species %}<option>{{x}}</option>{% endfor %}</select>
        </div>
        <div class="item"><label>物種類別</label>
          <input list="species_type_list" name="species_type" autocomplete="off">
          <datalist id="species_type_list">
            {% for x in species_types %}
            <option value="{{x}}">
            {% endfor %}
          </datalist>
        </div>
        <div class="item"><label>性別</label>
          <select name="gender"><option value="">請選擇</option>{% for x in genders %}<option>{{x}}</option>{% endfor %}</select>
        </div>
        <div class="item"><label>年齡</label>
          <select name="age"><option value="">請選擇</option>{% for x in ages %}<option>{{x}}</option>{% endfor %}</select>
        </div>
        <div class="item"><label>主治醫師</label>
          <select name="doctor"><option value="">請選擇</option>{% for x in doctors %}<option>{{x}}</option>{% endfor %}</select>
        </div>
      </div>
      <div class="box">
        <h3>送檢資訊</h3>
        <div class="item"><label>送檢日期</label><input name="send_date" type="date"></div>
        <div class="item"><label>檢驗類別</label>
          <select name="exam_type"><option value="">請選擇</option>{% for x in exam_types %}<option>{{x}}</option>{% endfor %}</select>
        </div>
        <div class="item"><label>檢體類型</label>
          <select name="sample_type"><option value="">請選擇</option>{% for x in sample_types %}<option>{{x}}</option>{% endfor %}</select>
        </div>
        <div class="item"><label>樣本</label><input name="sample"></div>
        <div class="item"><label>送檢單位</label>
          <select name="lab"><option value="">請選擇</option>{% for x in labs %}<option>{{x}}</option>{% endfor %}</select>
        </div>
        <div class="item"><label>送檢單位編號</label><input name="lab_code"></div>
        <div class="item"><label>報告</label><input name="report"></div>
      </div>
    </div>
    <br>
    <input type="submit" value="儲存">
    </form>
    <br>
    <a href="/lists">🗂️ 清單管理</a>
    <a href="/browse">📊 複合查詢</a>
    ''', species=species, species_types=species_types, genders=genders, ages=ages, doctors=doctors,
         exam_types=exam_types, sample_types=sample_types, labs=labs)

@app.route('/submit', methods=['POST'])
def submit():
    data = (
        request.form.get('pathology_id', ''),
        request.form.get('species', ''),
        request.form.get('species_type', ''),
        request.form.get('gender', ''),
        request.form.get('age', ''),
        request.form.get('doctor', ''),
        request.form.get('send_date', None),
        request.form.get('exam_type', ''),
        request.form.get('sample_type', ''),
        request.form.get('sample', ''),
        request.form.get('lab', ''),
        request.form.get('lab_code', ''),
        request.form.get('report', ''),
    )
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO samples (
                    pathology_id, species, species_type, gender, age, doctor, send_date,
                    exam_type, sample_type, sample, lab, lab_code, report
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, data)
            conn.commit()
    return redirect(url_for('form'))

@app.route('/browse', methods=['GET', 'POST'])
def browse():
    query = "SELECT * FROM samples ORDER BY id DESC LIMIT 100"
    filters = []
    values = []

    if request.method == 'POST':
        species = request.form.get('species')
        doctor = request.form.get('doctor')
        exam_type = request.form.get('exam_type')
        # 可依需求增加更多欄位

        if species:
            filters.append("species = %s")
            values.append(species)
        if doctor:
            filters.append("doctor = %s")
            values.append(doctor)
        if exam_type:
            filters.append("exam_type = %s")
            values.append(exam_type)

        if filters:
            query = f"SELECT * FROM samples WHERE {' AND '.join(filters)} ORDER BY id DESC LIMIT 100"

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(query, tuple(values))
            results = cur.fetchall()
            columns = [desc[0] for desc in cur.description]

    # 取得下拉選單資料
    all_species = get_all('species')
    all_doctors = get_all('doctors')
    all_exam_types = get_all('exam_types')

    form_data = dict(request.form) if request.method == 'POST' else {}

    return render_template_string('''
        <h2>複合查詢</h2>
        <form method="POST">
          物種：
          <select name="species">
            <option value="">(全部)</option>
            {% for s in all_species %}
              <option value="{{s}}" {% if form_data.get('species')==s %}selected{% endif %}>{{s}}</option>
            {% endfor %}
          </select>
          主治醫師：
          <select name="doctor">
            <option value="">(全部)</option>
            {% for d in all_doctors %}
              <option value="{{d}}" {% if form_data.get('doctor')==d %}selected{% endif %}>{{d}}</option>
            {% endfor %}
          </select>
          檢驗類別：
          <select name="exam_type">
            <option value="">(全部)</option>
            {% for e in all_exam_types %}
              <option value="{{e}}" {% if form_data.get('exam_type')==e %}selected{% endif %}>{{e}}</option>
            {% endfor %}
          </select>
          <input type="submit" value="查詢">
        </form>
        <form method="POST" action="/download_csv">
          <!-- 隱藏欄位保留查詢條件 -->
          <input type="hidden" name="species" value="{{form_data.get('species','')}}">
          <input type="hidden" name="doctor" value="{{form_data.get('doctor','')}}">
          <input type="hidden" name="exam_type" value="{{form_data.get('exam_type','')}}">
          <button type="submit">下載查詢結果 (CSV)</button>
        </form>
        <table border="1" style="margin-top:16px;">
          <tr>
            {% for col in columns %}
              <th>{{col}}</th>
            {% endfor %}
          </tr>
          {% for row in results %}
            <tr>
              {% for item in row %}
                <td>{{item}}</td>
              {% endfor %}
            </tr>
          {% endfor %}
        </table>
        <br>
        <a href="/">🏠 回首頁</a>
    ''', results=results, columns=columns, all_species=all_species,
         all_doctors=all_doctors, all_exam_types=all_exam_types, form_data=form_data)

@app.route('/download_csv', methods=['POST'])
def download_csv():
    # 跟 browse 查詢條件一樣
    query = "SELECT * FROM samples"
    filters = []
    values = []

    species = request.form.get('species')
    doctor = request.form.get('doctor')
    exam_type = request.form.get('exam_type')

    if species:
        filters.append("species = %s")
        values.append(species)
    if doctor:
        filters.append("doctor = %s")
        values.append(doctor)
    if exam_type:
        filters.append("exam_type = %s")
        values.append(exam_type)

    if filters:
        query += " WHERE " + " AND ".join(filters)
    query += " ORDER BY id DESC LIMIT 100"

    with get_conn() as conn:
        df = pd.read_sql_query(query, conn, params=values)

    output = io.StringIO()
    df.to_csv(output, index=False, encoding='utf-8-sig')
    output.seek(0)

    response = make_response(output.getvalue())
    response.headers["Content-Disposition"] = "attachment; filename=query_result.csv"
    response.headers["Content-type"] = "text/csv; charset=utf-8-sig"
    return response

if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=8080, debug=True)
