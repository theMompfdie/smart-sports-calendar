FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir --requirement requirements.txt

COPY app/ ./app/

RUN useradd \
    --create-home \
    --uid 10001 \
    --shell /usr/sbin/nologin \
    calendar \
    && mkdir -p /data/media \
    && chown -R calendar:calendar /app /data

USER calendar

CMD ["python", "-m", "app.main"]
