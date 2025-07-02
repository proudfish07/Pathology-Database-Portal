from flask import Flask, request, render_template_string, redirect, url_for
import sqlite3

app = Flask(__name__)

def init_db():
    with sqlite3.connect("data.db") as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS samples (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pathology_id TEXT,
                species TEXT,
                doctor TEXT,
                send_date TEXT,
                send_time TEXT,
                sample_site TEXT,
                lab TEXT,
                exam_type TEXT
            )
        ''')

@app.route('/')
def form():
    return render_template_string('''
        <h2>新增送檢紀錄</h2>
        <form method="POST" action="/submit">
            病理編號：<input name="pathology_id"><br>
            物種：<input name="species"><br>
            主治醫師：<input name="doctor"><br>
            送檢日期：<input name="send_date" type="date"><br>
            送檢時間：<input name="send_time" type="time"><br>
            送檢部位：<input name="sample_site"><br>
            送檢單位：<input name="lab"><br>
            檢驗類型：<input name="exam_type"><br>
            <input type="submit" value="儲存">
        </form>
        <br>
        <a href="/search">🔍 查詢紀錄</a>
    ''')

@app.route('/submit', methods=['POST'])
def submit():
    data = (
        request.form['pathology_id'],
        request.form['species'],
        request.form['doctor'],
        request.form['send_date'],
        request.form['send_time'],
        request.form['sample_site'],
        request.form['lab'],
        request.form['exam_type']
    )
    with sqlite3.connect("data.db") as conn:
        conn.execute("""
            INSERT INTO samples (pathology_id, species, doctor, send_date, send_time, sample_site, lab, exam_type)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, data)
    return redirect(url_for('form'))

@app.route('/search', methods=['GET', 'POST'])
def search():
    if request.method == 'POST':
        pid = request.form['pathology_id']
        with sqlite3.connect("data.db") as conn:
            records = conn.execute("SELECT * FROM samples WHERE pathology_id = ?", (pid,)).fetchall()
        return render_template_string('''
            <h2>查詢結果</h2>
            <table border="1">
                <tr><th>編輯</th><th>日期</th><th>時間</th><th>物種</th><th>部位</th><th>檢驗</th><th>單位</th><th>醫師</th></tr>
                {% for r in records %}
                    <tr>
                        <td><a href="/edit/{{ r[0] }}">✏️</a></td>
                        <td>{{ r[4] }}</td><td>{{ r[5] }}</td><td>{{ r[2] }}</td>
                        <td>{{ r[6] }}</td><td>{{ r[8] }}</td><td>{{ r[7] }}</td><td>{{ r[3] }}</td>
                    </tr>
                {% endfor %}
            </table>
            <a href="/search">🔙 返回</a>
        ''', records=records)
    return render_template_string('''
        <h2>查詢送檢紀錄</h2>
        <form method="POST">
            請輸入病理編號：<input name="pathology_id">
            <input type="submit" value="查詢">
        </form>
        <br><a href="/">🏠 回首頁</a>
    ''')

@app.route('/edit/<int:id>', methods=['GET', 'POST'])
def edit(id):
    with sqlite3.connect("data.db") as conn:
        if request.method == 'POST':
            data = (
                request.form['pathology_id'],
                request.form['species'],
                request.form['doctor'],
                request.form['send_date'],
                request.form['send_time'],
                request.form['sample_site'],
                request.form['lab'],
                request.form['exam_type'],
                id
            )
            conn.execute("""
                UPDATE samples SET 
                    pathology_id=?, species=?, doctor=?, send_date=?,
                    send_time=?, sample_site=?, lab=?, exam_type=? 
                WHERE id=?
            """, data)
            return redirect(url_for('search'))
        else:
            record = conn.execute("SELECT * FROM samples WHERE id=?", (id,)).fetchone()
    return render_template_string('''
        <h2>編輯送檢紀錄</h2>
        <form method="POST">
            病理編號：<input name="pathology_id" value="{{ r[1] }}"><br>
            物種：<input name="species" value="{{ r[2] }}"><br>
            主治醫師：<input name="doctor" value="{{ r[3] }}"><br>
            送檢日期：<input name="send_date" type="date" value="{{ r[4] }}"><br>
            送檢時間：<input name="send_time" type="time" value="{{ r[5] }}"><br>
            送檢部位：<input name="sample_site" value="{{ r[6] }}"><br>
            送檢單位：<input name="lab" value="{{ r[7] }}"><br>
            檢驗類型：<input name="exam_type" value="{{ r[8] }}"><br>
            <input type="submit" value="儲存變更">
        </form>
        <a href="/search">🔙 返回查詢</a>
    ''', r=record)

if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5000, debug=True)
