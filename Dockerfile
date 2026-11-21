FROM python:3.12-slim-trixie

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    KTS_DATA_DIR=/data/projects \
    KTS_KEYCLOAKIFY_CACHE_DIR=/data/keycloakify-cache \
    KTS_KEYCLOAKIFY_VERSION=11.16.4

WORKDIR /app

# Optional enterprise proxy settings are passed at build time through Compose.
ARG HTTP_PROXY
ARG HTTPS_PROXY
ARG NO_PROXY
ARG http_proxy
ARG https_proxy
ARG no_proxy

# The native JAR export needs only Python. The React/Keycloakify export additionally
# requires Node.js, npm, Java and Maven; install the complete toolchain in the image.
RUN apt-get update && apt-get install -y --no-install-recommends \
      nodejs npm openjdk-21-jdk-headless maven ca-certificates \
    && rm -rf /var/lib/apt/lists/*

RUN addgroup --system app && adduser --system --ingroup app app
COPY requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
RUN mkdir -p /data/projects /data/keycloakify-cache && chown -R app:app /app /data

USER app
EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/api/health', timeout=3)" || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
