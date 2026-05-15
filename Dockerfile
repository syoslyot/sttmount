FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/
COPY scripts/ ./scripts/

RUN mkdir -p /app/app/static/gpx /app/app/static/maps /app/db

# DB 由 CI 的 normalize.py 產生後 COPY 進來；本機 build 則在此初始化空 schema
COPY db/ ./db/
RUN python3 -c "from app.models import init_db; init_db()"

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
