FROM python:3.11-slim

WORKDIR /app

# Install system dependencies required for psycopg2 and compilation
RUN apt-get update && apt-get install -y libpq-dev gcc build-essential

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Run FastAPI using $PORT assigned dynamically by Railway (or fallback to 8000)
CMD ["sh", "-c", "uvicorn api:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1"]
