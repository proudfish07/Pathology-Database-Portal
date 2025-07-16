FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# SQLite 資料存到 /data 目錄（可微調）
RUN mkdir -p /data
ENV SQLITE_PATH=/data/data.db

EXPOSE 8080

CMD exec gunicorn --bind :8080 --workers 1 --timeout 120 main:app
