FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
EXPOSE 8080

CMD exec gunicorn --bind :8080 --workers 1 --timeout 120 main:app
