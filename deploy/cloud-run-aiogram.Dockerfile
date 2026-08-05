FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

WORKDIR /app

COPY requirements.txt ./
RUN apt-get update && apt-get install -y git && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir -r requirements.txt

COPY src ./src

RUN groupadd --system oisha \
    && useradd --system --gid oisha --home-dir /app oisha \
    && chown -R oisha:oisha /app

USER oisha

CMD ["python", "-m", "uvicorn", "src.aiogram_cloudrun:app", "--host", "0.0.0.0", "--port", "8080"]
