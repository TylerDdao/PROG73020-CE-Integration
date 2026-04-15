FROM python:3.12-slim

WORKDIR /app

COPY app/ /app/

RUN pip install flask flask-cors requests paramiko psycopg2-binary

CMD ["python", "app.py"]
