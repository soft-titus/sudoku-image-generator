FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        libfreetype6 \
        libpng-dev \
        && rm -rf /var/lib/apt/lists/*

COPY fonts/ ./fonts/

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY *.py .
COPY consumer/ ./consumer/

CMD ["python", "-m", "consumer.main"]
