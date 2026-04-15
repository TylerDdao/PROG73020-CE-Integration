FROM python:3.12-slim

WORKDIR /app

# Copy requirements FIRST
COPY requirements.txt .

RUN pip install -r requirements.txt

# Then copy app
COPY app/ .

CMD ["python", "app.py"]
