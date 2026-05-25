FROM python:3.12-slim-bookworm AS builder

WORKDIR /build
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

FROM python:3.12-slim-bookworm

RUN apt-get update && apt-get install -y --no-install-recommends \
    openjdk-17-jre-headless \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY --from=builder /install /usr/local
COPY . .

RUN addgroup --system --gid 1001 openhome \
    && adduser --system --uid 1001 --gid 1001 openhome \
    && mkdir -p /opt/openhome/server \
    && chown -R openhome:openhome /app /opt/openhome

USER openhome

EXPOSE 8000
EXPOSE 25565

ENV PYTHONUNBUFFERED=1
ENV SERVER_DIR=/opt/openhome/server

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--ws", "auto"]
