FROM python:3.12-slim
WORKDIR /app
COPY backend/requirements.txt backend/constraints.txt ./
RUN pip install --no-cache-dir --upgrade "pip>=26.2,<27" && pip install --no-cache-dir -r requirements.txt
COPY backend/app ./app
COPY contracts ./contracts
COPY backend/alembic.ini .
COPY backend/migrations ./migrations
EXPOSE 8000
CMD ["sh", "-c", "python -m alembic upgrade head && exec python -m uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
