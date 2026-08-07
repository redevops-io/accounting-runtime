FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py .
# data is mounted or baked at deploy; sample.jsonl ships in the repo
ENV PORT=8300
EXPOSE 8300
CMD ["sh","-c","uvicorn app:app --host 0.0.0.0 --port ${PORT}"]
