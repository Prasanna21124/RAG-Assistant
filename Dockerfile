FROM python:3.11-slim

WORKDIR /app

# Install system dependencies required for psycopg2 and compilation
RUN apt-get update && apt-get install -y libpq-dev gcc build-essential

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Run the FastAPI server on port 8000 with 4 workers for production scaling
CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
