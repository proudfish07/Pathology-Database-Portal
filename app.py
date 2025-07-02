from flask import Flask, request, render_template_string, redirect, url_for
import sqlite3
import pandas as pd

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 2 * 1024 * 1024  # 限制上傳檔案最大2MB

def init_db():
    with sqlite3.connect("data.db") as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS samples (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pathology_id TEXT,
                species TEXT,
                species_type TEXT,
                gender TEXT,
                age TEXT,
                doctor TEXT,
                send_date TEXT,
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
            conn.execute(f'CREATE TABLE IF NOT EXISTS {table} (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE)')

def get_all(table):
    with sqlite3.connect("data.db") as conn:
        return [row[1] for row in conn.execute(f"SELECT * FROM {table} ORDER BY name")]

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
                with sqlite3.connect("data.db") as conn:
                    conn.execute(f"INSERT INTO {t} (name) VALUES (?)", (name,))
                msg = "新增成功"
            except sqlite3.IntegrityError:
                msg = "名稱重複"
    delete_id = request.args.get('delete')
    if delete_id:
        with sqlite3.connect("data.db") as conn:
            conn.execute(f"DELETE FROM {t} WHERE id=?", (delete_id,))
        return redirect(url_for('lists', type=t))
    with sqlite3.connect("data.db") as conn:
        items = conn.execute(f"SELECT id, name FROM {t} ORDER BY name").fetchall()
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
                        with sqlite3.connect("data.db") as conn:
                            conn.execute(f"INSERT INTO {table} (name) VALUES (?)", (name,))
                        count += 1
                    except sqlite3.IntegrityError:
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
        request.form.get('send_date', ''),
        request.form.get('exam_type', ''),
        request.form.get('sample_type', ''),
        request.form.get('sample', ''),
        request.form.get('lab', ''),
        request.form.get('lab_code', ''),
        request.form.get('report', ''),
    )
    with sqlite3.connect("data.db") as conn:
        conn.execute("""
            INSERT INTO samples (
                pathology_id, species, species_type, gender, age, doctor, send_date,
                exam_type, sample_type, sample, lab, lab_code, report
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, data)
    return redirect(url_for('form'))

@app.route('/browse', methods=['GET', 'POST'])
def browse():
    species = get_all('species')
    species_types = get_all('species_type')
    genders = get_all('gender')
    ages = get_all('age')
    doctors = get_all('doctors')
    exam_types = get_all('exam_types')
    sample_types = get_all('sample_types')
    labs = get_all('labs')
    records = []
    total = 0
    conds = []
    vals = []
    form_val = dict(request.form) if request.method == 'POST' else {}
    if request.method == 'POST':
        pid = request.form.get('pathology_id', '').strip()
        if pid:
            conds.append('pathology_id LIKE ?')
            vals.append(f"%{pid}%")
        date_start = request.form.get('date_start', '')
        date_end = request.form.get('date_end', '')
        if date_start:
            conds.append('send_date >= ?')
            vals.append(date_start)
        if date_end:
            conds.append('send_date <= ?')
            vals.append(date_end)
        cond_map = [
            ('species', 'species'),
            ('species_type', 'species_type'),
            ('gender', 'gender'),
            ('age', 'age'),
            ('doctor', 'doctor'),
            ('exam_type', 'exam_type'),
            ('sample_type', 'sample_type'),
            ('lab', 'lab')
        ]
        for k, col in cond_map:
            v = request.form.get(k, '')
            if v:
                conds.append(f"{col}=?")
                vals.append(v)
        sql = "SELECT * FROM samples"
        if conds:
            sql += " WHERE " + " AND ".join(conds)
        with sqlite3.connect("data.db") as conn:
            records = conn.execute(sql, vals).fetchall()
            total = len(records)
    return render_template_string('''
        <h2>複合條件查詢</h2>
        <form method="POST">
            病理編號：<input name="pathology_id" value="{{ form_val.get('pathology_id','') }}">
            日期範圍：<input type="date" name="date_start" value="{{ form_val.get('date_start','') }}"> ~
            <input type="date" name="date_end" value="{{ form_val.get('date_end','') }}">
            <br>
            物種：<select name="species"><option value="">全部</option>{% for x in species %}<option {% if form_val.get('species')==x %}selected{% endif %}>{{x}}</option>{% endfor %}</select>
            物種類別：<select name="species_type"><option value="">全部</option>{% for x in species_types %}<option {% if form_val.get('species_type')==x %}selected{% endif %}>{{x}}</option>{% endfor %}</select>
            性別：<select name="gender"><option value="">全部</option>{% for x in genders %}<option {% if form_val.get('gender')==x %}selected{% endif %}>{{x}}</option>{% endfor %}</select>
            年齡：<select name="age"><option value="">全部</option>{% for x in ages %}<option {% if form_val.get('age')==x %}selected{% endif %}>{{x}}</option>{% endfor %}</select>
            主治醫師：<select name="doctor"><option value="">全部</option>{% for x in doctors %}<option {% if form_val.get('doctor')==x %}selected{% endif %}>{{x}}</option>{% endfor %}</select>
            檢驗類別：<select name="exam_type"><option value="">全部</option>{% for x in exam_types %}<option {% if form_val.get('exam_type')==x %}selected{% endif %}>{{x}}</option>{% endfor %}</select>
            檢體類型：<select name="sample_type"><option value="">全部</option>{% for x in sample_types %}<option {% if form_val.get('sample_type')==x %}selected{% endif %}>{{x}}</option>{% endfor %}</select>
            送檢單位：<select name="lab"><option value="">全部</option>{% for x in labs %}<option {% if form_val.get('lab')==x %}selected{% endif %}>{{x}}</option>{% endfor %}</select>
            <input type="submit" value="查詢">
        </form>
        {% if records %}
        <h3>查詢結果 (共 {{total}} 筆)</h3>
        <table border="1">
            <tr>
                <th>編輯</th>
                <th>病理編號</th><th>物種</th><th>物種類別</th><th>性別</th><th>年齡</th><th>主治醫師</th>
                <th>送檢日期</th><th>檢驗類別</th><th>檢體類型</th><th>樣本</th>
                <th>送檢單位</th><th>送檢單位編號</th><th>報告</th>
            </tr>
            {% for r in records %}
            <tr>
                <td><a href="/edit/{{ r[0] }}">編輯</a></td>
                <td>{{ r[1] }}</td><td>{{ r[2] }}</td><td>{{ r[3] }}</td><td>{{ r[4] }}</td><td>{{ r[5] }}</td><td>{{ r[6] }}</td>
                <td>{{ r[7] }}</td><td>{{ r[8] }}</td><td>{{ r[9] }}</td><td>{{ r[10] }}</td>
                <td>{{ r[11] }}</td><td>{{ r[12] }}</td><td>{{ r[13] }}</td>
            </tr>
            {% endfor %}
        </table>
        {% endif %}
        <a href="/">🏠 回首頁</a>
    ''', species=species, species_types=species_types, genders=genders, ages=ages,
         doctors=doctors, exam_types=exam_types, sample_types=sample_types, labs=labs,
         records=records, total=total, form_val=form_val)

@app.route('/edit/<int:id>', methods=['GET', 'POST'])
def edit(id):
    species = get_all('species')
    species_types = get_all('species_type')
    genders = get_all('gender')
    ages = get_all('age')
    doctors = get_all('doctors')
    exam_types = get_all('exam_types')
    sample_types = get_all('sample_types')
    labs = get_all('labs')
    with sqlite3.connect("data.db") as conn:
        if request.method == 'POST':
            data = (
                request.form.get('pathology_id', ''),
                request.form.get('species', ''),
                request.form.get('species_type', ''),
                request.form.get('gender', ''),
                request.form.get('age', ''),
                request.form.get('doctor', ''),
                request.form.get('send_date', ''),
                request.form.get('exam_type', ''),
                request.form.get('sample_type', ''),
                request.form.get('sample', ''),
                request.form.get('lab', ''),
                request.form.get('lab_code', ''),
                request.form.get('report', ''),
                id
            )
            conn.execute("""
                UPDATE samples SET
                    pathology_id=?, species=?, species_type=?, gender=?, age=?, doctor=?, send_date=?,
                    exam_type=?, sample_type=?, sample=?, lab=?, lab_code=?, report=?
                WHERE id=?
            """, data)
            return redirect(url_for('browse'))
        else:
            rec = conn.execute("SELECT * FROM samples WHERE id=?", (id,)).fetchone()
    return render_template_string('''
        <h2>編輯送檢紀錄</h2>
        <form method="POST">
        <div class="container" style="display:flex;gap:24px">
          <div class="box" style="border:1px solid #888;border-radius:8px;padding:16px;">
            <h3>物種資訊</h3>
            <div class="item"><label>病理編號</label><input name="pathology_id" value="{{ rec[1] }}"></div>
            <div class="item"><label>物種</label>
              <select name="species">{% for x in species %}<option value="{{x}}" {% if rec[2]==x %}selected{% endif %}>{{x}}</option>{% endfor %}</select>
            </div>
            <div class="item"><label>物種類別</label>
              <input list="species_type_list" name="species_type" value="{{ rec[3] }}" autocomplete="off">
              <datalist id="species_type_list">
                {% for x in species_types %}
                <option value="{{x}}">
                {% endfor %}
              </datalist>
            </div>
            <div class="item"><label>性別</label>
              <select name="gender">{% for x in genders %}<option value="{{x}}" {% if rec[4]==x %}selected{% endif %}>{{x}}</option>{% endfor %}</select>
            </div>
            <div class="item"><label>年齡</label>
              <select name="age">{% for x in ages %}<option value="{{x}}" {% if rec[5]==x %}selected{% endif %}>{{x}}</option>{% endfor %}</select>
            </div>
            <div class="item"><label>主治醫師</label>
              <select name="doctor">{% for x in doctors %}<option value="{{x}}" {% if rec[6]==x %}selected{% endif %}>{{x}}</option>{% endfor %}</select>
            </div>
          </div>
          <div class="box" style="border:1px solid #888;border-radius:8px;padding:16px;">
            <h3>送檢資訊</h3>
            <div class="item"><label>送檢日期</label><input name="send_date" type="date" value="{{ rec[7] }}"></div>
            <div class="item"><label>檢驗類別</label>
              <select name="exam_type">{% for x in exam_types %}<option value="{{x}}" {% if rec[8]==x %}selected{% endif %}>{{x}}</option>{% endfor %}</select>
            </div>
            <div class="item"><label>檢體類型</label>
              <select name="sample_type">{% for x in sample_types %}<option value="{{x}}" {% if rec[9]==x %}selected{% endif %}>{{x}}</option>{% endfor %}</select>
            </div>
            <div class="item"><label>樣本</label><input name="sample" value="{{ rec[10] }}"></div>
            <div class="item"><label>送檢單位</label>
              <select name="lab">{% for x in labs %}<option value="{{x}}" {% if rec[11]==x %}selected{% endif %}>{{x}}</option>{% endfor %}</select>
            </div>
            <div class="item"><label>送檢單位編號</label><input name="lab_code" value="{{ rec[12] }}"></div>
            <div class="item"><label>報告</label><input name="report" value="{{ rec[13] }}"></div>
          </div>
        </div>
        <br>
        <input type="submit" value="儲存變更">
        </form>
        <a href="/browse">🔙 返回查詢</a>
    ''', rec=rec, species=species, species_types=species_types, genders=genders, ages=ages, doctors=doctors,
         exam_types=exam_types, sample_types=sample_types, labs=labs)

if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5000, debug=True)
