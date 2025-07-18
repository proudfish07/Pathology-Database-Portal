try:
    import os
    import psycopg2
    import pandas as pd
    from flask import Flask, request, render_template_string, redirect, url_for
    from werkzeug.datastructures import MultiDict
except Exception as e:
    import sys
    print("IMPORT ERROR:", e, file=sys.stderr)
    raise


app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 2 * 1024 * 1024  # 限制上傳檔案最大2MB

# 環境變數設置（Cloud Run設參數，不要寫死密碼）
DB_HOST = os.environ.get("DB_HOST", "127.0.0.1")
DB_PORT = int(os.environ.get("DB_PORT", 5432))
DB_NAME = os.environ.get("DB_NAME", "Pathology-DataBase")
DB_USER = os.environ.get("DB_USER", "wildone")
DB_PASS = os.environ.get("DB_PASS", "81148169")

def get_db_conn():
    try:
        return psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            dbname=DB_NAME,
            user=DB_USER,
            password=DB_PASS
        )
    except Exception as e:
        print("DB CONNECT ERROR:", e, file=sys.stderr)
        raise

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
    return render_template_string('''
    <style>
    .container { display: flex; gap: 24px; }
    .box { border: 1px solid #888; border-radius: 8px; padding: 16px; min-width: 340px; }
    .box h3 { margin-top:0; }
    .item { margin-bottom: 8px; }
    .item label { width: 110px; display: inline-block; }
    </style>
    <h2>WildOne 病例送檢登記表</h2>
    <form method="POST" action="/submit">
    <div class="container">
      <div class="box">
        <h3>病例資訊</h3>
        <div class="item"><label>病理編號</label><input name="pathology_id"></div>
        <div class="item"><label>物種</label>
          <input name="species_type" list="species_type_list" autocomplete="off" placeholder="可手動輸入或選擇">
          <datalist id="species_type_list">
            {% for x in species_types %}
            <option value="{{x}}">
            {% endfor %}
          </datalist>
        </div>
        <div class="item"><label>物種類別</label>
          <select name="species">
            <option value="">請選擇</option>
            {% for x in species %}
            <option value="{{x}}">{{x}}</option>
            {% endfor %}
          </select>
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
        <div class="item"><label>雲端資料連結</label>
          <input name="cloud_link" type="url" placeholder="貼上雲端連結(如Google Drive)">
        </div>
      </div>
      <div class="box">
        <h3>送檢資訊</h3>
        <div class="item"><label>送檢日期</label><input name="send_date" type="date"></div>
        <div class="item"><label>送驗項目</label>
          <select name="exam_item"><option value="">請選擇</option>{% for x in exam_items %}<option>{{x}}</option>{% endfor %}</select>
        </div>
        <div class="item"><label>檢體類型</label>
          <select name="sample_type"><option value="">請選擇</option>{% for x in sample_types %}<option>{{x}}</option>{% endfor %}</select>
        </div>
        <div class="item"><label>樣本說明</label><input name="sample"></div>
        <div class="item"><label>送檢單位</label>
          <select name="lab"><option value="">請選擇</option>{% for x in labs %}<option>{{x}}</option>{% endfor %}</select>
        </div>
        <div class="item" style="display:none"><label>送檢單位編號</label><input name="lab_code"></div>
        <div class="item" style="display:none"><label>報告</label><input name="report"></div>
      </div>
    </div>
    <br>
    <input type="submit" value="儲存">
    </form>
    <br>
    <a href="/lists">🗂️ 清單管理</a>
    <a href="/browse">📊 複合查詢</a>
    <a href="/import_samples">⬆️ 批次上傳病例/送檢</a>
    ''', species=species, species_types=species_types, genders=genders, ages=ages, doctors=doctors,
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

@app.route('/browse', methods=['GET', 'POST'])
def browse():
    species = get_all('species')
    species_types = get_all('species_type')
    genders = get_all('gender')
    ages = get_all('age')
    doctors = get_all('doctors')
    exam_items = get_all('exam_items')
    sample_types = get_all('sample_types')
    labs = get_all('labs')
    with get_db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT DISTINCT pathology_id FROM samples WHERE pathology_id != ''")
            pathology_ids = [row[0] for row in cur.fetchall()]

    if request.method == 'POST':
        form_val = request.form
    else:
        form_val = MultiDict()

    records = []
    total = 0
    conds = []
    vals = []

    if request.method == 'POST':
        def get_multi(name):
            return request.form.getlist(name)
        pid = request.form.get('pathology_id', '').strip()
        if pid:
            conds.append('pathology_id LIKE %s')
            vals.append(f"%{pid}%")
        date_start = request.form.get('date_start', '')
        date_end = request.form.get('date_end', '')
        if date_start:
            conds.append('send_date >= %s')
            vals.append(date_start)
        if date_end:
            conds.append('send_date <= %s')
            vals.append(date_end)
        multi_fields = [
            ('species_type', 'species_type'),
            ('species', 'species'),
            ('lab', 'lab'),
            ('exam_item', 'exam_item'),
            ('sample_type', 'sample_type'),
        ]
        for field_name, col in multi_fields:
            sel = get_multi(field_name)
            if sel:
                conds.append(f"{col} IN ({','.join(['%s']*len(sel))})")
                vals.extend(sel)
        for k, col in [
            ('gender', 'gender'),
            ('age', 'age'),
            ('doctor', 'doctor')
        ]:
            v = request.form.get(k, '')
            if v:
                conds.append(f"{col}=%s")
                vals.append(v)
        sql = "SELECT * FROM samples"
        if conds:
            sql += " WHERE " + " AND ".join(conds)
        with get_db_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, tuple(vals))
                records = cur.fetchall()
                total = len(records)

    filter_js = """
    <style>
    .multifilter { position:relative; display:inline-block; }
    .multifilter-btn { width:146px; text-align:left; }
    .multifilter-list { position:absolute; z-index:9; background:#fff; border:1px solid #aaa; padding:8px; min-width:156px; display:none; max-height:200px; overflow:auto;}
    .multifilter-list label { display:block; font-weight:normal; }
    </style>
    <script>
    function showFilter(id) {
      document.getElementById(id).style.display = 'block';
      document.body.addEventListener('mousedown', hideFilter, true);
    }
    function hideFilter(e) {
      var lists = document.querySelectorAll('.multifilter-list');
      var clicked = e && e.target;
      let found=false;
      lists.forEach(function(list){
        if(list.contains(clicked) || (clicked && clicked.classList.contains('multifilter-btn'))) found=true;
        else list.style.display='none';
      });
      if(!found) document.body.removeEventListener('mousedown', hideFilter, true);
    }
    function updateBtnText(id, inputName) {
      var checked = document.querySelectorAll('#'+id+' input[type=checkbox]:checked');
      var btn = document.getElementById(id.replace('list','btn'));
      if(checked.length) {
        let arr = Array.from(checked).map(x=>x.value);
        btn.innerText = arr.length>2 ? arr.slice(0,2).join(',') + '...' : arr.join(',');
      } else {
        btn.innerText = '全部';
      }
    }
    function clearFilter(id, inputName) {
      document.querySelectorAll('#'+id+' input[type=checkbox]').forEach(x=>x.checked=false);
      updateBtnText(id, inputName);
    }
    </script>
    """

    multifilter_html = lambda id, name, opts: f"""
    <div class="multifilter">
      <button type="button" class="multifilter-btn" id="{id}btn" onclick="showFilter('{id}list')">全部</button>
      <div class="multifilter-list" id="{id}list">
        <button type="button" onclick="clearFilter('{id}list','{name}')">清除</button>
        <hr style="margin:2px 0;">
        {''.join([f'<label><input type="checkbox" name="{name}" value="{x}" ' + ('checked' if name in form_val and x in form_val.getlist(name) else '') + f' onchange="updateBtnText(\'{id}list\',\'{name}\')">{x}</label>' for x in opts])}
      </div>
    </div>
    """

    return render_template_string(f'''
        {filter_js}
        <h2>複合條件查詢</h2>
        <form method="POST">
            <div>
            病理編號：
            <input name="pathology_id" value="{{{{ form_val.get('pathology_id','') }}}}" list="pidlist">
            <datalist id="pidlist">
              {{% for pid in pathology_ids %}}
                <option value="{{{{ pid }}}}">
              {{% endfor %}}
            </datalist>
            日期範圍：
            <input type="date" name="date_start" value="{{{{ form_val.get('date_start','') }}}}"> ~
            <input type="date" name="date_end" value="{{{{ form_val.get('date_end','') }}}}">
            </div>
            <div style="margin-top: 8px;">
            物種類別：{multifilter_html('species_type','species_type',species_types)}
            物種：{multifilter_html('species','species',species)}
            送檢單位：{multifilter_html('lab','lab',labs)}
            送驗項目：{multifilter_html('exam_item','exam_item',exam_items)}
            檢體類型：{multifilter_html('sample_type','sample_type',sample_types)}
            </div>
            <div style="margin-top: 8px;">
            性別：<select name="gender" style="width:70px;">
                <option value="">全部</option>{{% for x in genders %}}<option {{% if form_val.get('gender')==x %}}selected{{% endif %}}>{{{{x}}}}</option>{{% endfor %}}
            </select>
            年齡：<select name="age" style="width:70px;">
                <option value="">全部</option>{{% for x in ages %}}<option {{% if form_val.get('age')==x %}}selected{{% endif %}}>{{{{x}}}}</option>{{% endfor %}}
            </select>
            主治醫師：<select name="doctor" style="width:100px;">
                <option value="">全部</option>{{% for x in doctors %}}<option {{% if form_val.get('doctor')==x %}}selected{{% endif %}}>{{{{x}}}}</option>{{% endfor %}}
            </select>
            </div>
            <input type="submit" value="查詢" style="margin-top:8px;">
        </form>
        <script>
        window.addEventListener('DOMContentLoaded',function(){{
            ['species_type','species','lab','exam_item','sample_type'].forEach(function(id){{
                updateBtnText(id+'list',id);
            }});
        }});
        </script>
        {{% if records %}}
        <h3>查詢結果 (共 {{{{total}}}} 筆)</h3>
        <table border="1">
            <tr>
                <th>編輯</th>
                <th>病理編號</th><th>物種</th><th>物種類別</th><th>性別</th><th>年齡</th><th>主治醫師</th>
                <th>送檢日期</th><th>送驗項目</th><th>檢體類型</th><th>樣本</th>
                <th>送檢單位</th><th>送檢單位編號</th><th>報告</th><th>雲端資料連結</th>
            </tr>
            {{% for r in records %}}
            <tr>
                <td><a href="/edit/{{{{ r[0] }}}}">編輯</a></td>
                <td>{{{{ r[1] }}}}</td><td>{{{{ r[2] }}}}</td><td>{{{{ r[3] }}}}</td><td>{{{{ r[4] }}}}</td><td>{{{{ r[5] }}}}</td><td>{{{{ r[6] }}}}</td>
                <td>{{{{ r[7] }}}}</td><td>{{{{ r[8] }}}}</td><td>{{{{ r[9] }}}}</td><td>{{{{ r[10] }}}}</td>
                <td>{{{{ r[11] }}}}</td><td>{{{{ r[12] }}}}</td><td>{{{{ r[13] }}}}</td>
                <td>
                  {{% if r[14] %}}
                    <a href="{{{{ r[14] }}}}" target="_blank">雲端連結</a>
                  {{% endif %}}
                </td>
            </tr>
            {{% endfor %}}
        </table>
        {{% endif %}}
        <a href="/">🏠 回首頁</a>
    ''',
    species=species, species_types=species_types, genders=genders, ages=ages,
    doctors=doctors, exam_items=exam_items, sample_types=sample_types, labs=labs,
    records=records, total=total, form_val=form_val, pathology_ids=pathology_ids)

@app.route('/edit/<int:id>', methods=['GET', 'POST'])
def edit(id):
    species = get_all('species')
    species_types = get_all('species_type')
    genders = get_all('gender')
    ages = get_all('age')
    doctors = get_all('doctors')
    exam_items = get_all('exam_items')
    sample_types = get_all('sample_types')
    labs = get_all('labs')
    with get_db_conn() as conn:
        with conn.cursor() as cur:
            if request.method == 'POST':
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
                    id
                )
                cur.execute("""
                    UPDATE samples SET
                        pathology_id=%s, species=%s, species_type=%s, gender=%s, age=%s, doctor=%s, send_date=%s,
                        exam_item=%s, sample_type=%s, sample=%s, lab=%s, lab_code=%s, report=%s, cloud_link=%s
                    WHERE id=%s
                """, data)
                conn.commit()
                return redirect(url_for('browse'))
            else:
                cur.execute("SELECT * FROM samples WHERE id=%s", (id,))
                rec = cur.fetchone()
    return render_template_string('''
        <h2>編輯送檢紀錄</h2>
        <form method="POST">
        <div class="container" style="display:flex;gap:24px">
          <div class="box" style="border:1px solid #888;border-radius:8px;padding:16px;">
            <h3>物種資訊</h3>
            <div class="item"><label>病理編號</label><input name="pathology_id" value="{{ rec[1] }}"></div>
            <div class="item"><label>物種</label>
              <input name="species_type" list="species_type_list" autocomplete="off" value="{{ rec[3] }}" placeholder="可手動輸入或選擇">
              <datalist id="species_type_list">
                {% for x in get_all('species') %}
                <option value="{{x}}">
                {% endfor %}
              </datalist>
            </div>
            <div class="item"><label>物種類別</label>
              <select name="species">
                <option value="">請選擇</option>
                {% for x in get_all('species_type') %}
                <option value="{{x}}" {% if rec[2]==x %}selected{% endif %}>{{x}}</option>
                {% endfor %}
              </select>
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
            <div class="item"><label>雲端資料連結</label>
              <input name="cloud_link" value="{{ rec[14] }}">
            </div>
          </div>
          <div class="box" style="border:1px solid #888;border-radius:8px;padding:16px;">
            <h3>送檢資訊</h3>
            <div class="item"><label>送檢日期</label><input name="send_date" type="date" value="{{ rec[7] }}"></div>
            <div class="item"><label>送驗項目</label>
              <select name="exam_item">{% for x in exam_items %}<option value="{{x}}" {% if rec[8]==x %}selected{% endif %}>{{x}}</option>{% endfor %}</select>
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
    ''', rec=rec, genders=genders, ages=ages, doctors=doctors, exam_items=exam_items, sample_types=sample_types, labs=labs, get_all=get_all)

if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=8080)
