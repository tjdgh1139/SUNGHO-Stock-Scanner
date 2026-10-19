FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /opt/atlas
COPY atlas_collector_watchdog.py atlas_collector_runner.py atlas_collector_storage.py atlas_market_session_schedule.py atlas_collector_market_gate.py ./
COPY deploy/atlas-paper/health_worker.py ./health_worker.py
RUN useradd -r -u 10001 atlas && mkdir -p /var/lib/atlas && chown atlas:atlas /var/lib/atlas
USER atlas
VOLUME ["/var/lib/atlas"]
CMD ["python","health_worker.py"]
