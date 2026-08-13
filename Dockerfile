FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY statuspage_bridge.py .

RUN useradd --create-home --uid 1000 bridge \
    && mkdir -p /app/data \
    && chown -R bridge:bridge /app
USER bridge

ENV BRIDGE_PORT=9090
EXPOSE 9090

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import os,urllib.request as u; u.urlopen('http://localhost:' + os.environ.get('BRIDGE_PORT', '9090') + '/health', timeout=3)"

CMD ["sh", "-c", "exec uvicorn statuspage_bridge:app --host 0.0.0.0 --port ${BRIDGE_PORT:-9090}"]
