FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PLANWISE_DATABASE=/data/planwise.sqlite3
WORKDIR /app
COPY nas/requirements.txt /app/nas/requirements.txt
RUN pip install --no-cache-dir -r nas/requirements.txt \
    && groupadd --gid 10001 planwise \
    && useradd --uid 10001 --gid 10001 --no-create-home planwise \
    && mkdir /data && chown 10001:10001 /data
COPY planner.py timetable.py events.py storage.py holidays.py i18n.py translations.json /app/
COPY nas/*.py /app/nas/
COPY nas/static /app/nas/static
USER 10001:10001
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/healthz',timeout=3)"
# Initialize SQLite once before forking; workers only open per-request connections.
CMD ["gunicorn", "--preload", "--bind=0.0.0.0:8080", "--forwarded-allow-ips=", "--workers=2", "--threads=2", "--timeout=60", "--worker-tmp-dir=/tmp", "nas.application:create_app()"]
