FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN groupadd --gid 10001 rialo-edge-log \
    && useradd --uid 10001 --gid 10001 --no-create-home --shell /usr/sbin/nologin rialo-edge-log

WORKDIR /app

COPY gateway/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir --requirement /tmp/requirements.txt

COPY archive ./archive
COPY gateway ./gateway
COPY portal ./portal

USER 10001:10001

EXPOSE 8090

CMD ["python", "-m", "archive.server", "--host", "0.0.0.0", "--port", "8090", "--database", "/var/lib/rialo-edge-log/archive.sqlite3"]

