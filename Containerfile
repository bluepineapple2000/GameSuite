FROM python:3.13-alpine

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt /app/

RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

COPY mySite /app/mySite

WORKDIR /app/mySite

EXPOSE 8000

#To-do: use asgi
CMD ["sh", "-c", "python manage.py migrate && python manage.py runserver 0.0.0.0:8000"]