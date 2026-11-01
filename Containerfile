FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DJANGO_DB_PATH=/data/db.sqlite3
WORKDIR /app
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt && \
    groupadd --gid 10001 games && \
    useradd --uid 10001 --gid games --no-create-home games && \
    mkdir /data && chown games:games /data
COPY mySite /app/mySite
COPY couplesQuestions /app/couplesQuestions
WORKDIR /app/mySite
RUN DJANGO_DEBUG=true python manage.py collectstatic --noinput
USER 10001:10001
EXPOSE 8000
CMD ["sh", "-c", "umask 077 && python manage.py migrate --noinput && exec uvicorn mySite.asgi:application --host 0.0.0.0 --port 8000 --no-proxy-headers --no-access-log --ws-max-size 1024 --limit-concurrency 100"]
