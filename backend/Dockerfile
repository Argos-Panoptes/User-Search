FROM python:3.12-slim

# Install Java (Required for PySpark)
# Install Java (Required for PySpark)
RUN apt-get update && \
    apt-get install -y --no-install-recommends openjdk-21-jre-headless procps curl && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Set JAVA_HOME
ENV JAVA_HOME=/usr/lib/jvm/java-21-openjdk-amd64

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Expose API port
EXPOSE 8000

# Run standalone database initialization, then start FastAPI with Gunicorn (4 workers)
# --forwarded-allow-ips=* is needed to resolve a Uvicorn AttributeError with proxy headers in Docker
CMD python -m app.init_db && \
    gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker -b 0.0.0.0:8000 --forwarded-allow-ips="*"
