from flask import Flask

app = Flask(__name__)

@app.route("/")
def index():
    return "✅ Cloud Run 測試成功！"

@app.route("/ping")
def ping():
    return "pong"
