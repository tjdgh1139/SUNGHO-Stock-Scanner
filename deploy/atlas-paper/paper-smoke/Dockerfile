FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /opt/atlas
COPY atlas_paper_ledger.py atlas_paper_live_bridge.py atlas_paper_sqlite.py atlas_paper_session_adapter.py ./
COPY deploy/atlas-paper/paper-smoke/worker.py ./worker.py
RUN useradd --system --uid 10002 atlas && mkdir -p /var/lib/atlas && chown atlas:atlas /var/lib/atlas
USER atlas
CMD ["python","worker.py"]
