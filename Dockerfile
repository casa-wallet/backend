FROM python:3.11-slim

RUN useradd -m -d /app python
ENV PYTHONPATH=/app \
    GUNICORN_CMD_ARGS='--worker-class=uvicorn.workers.UvicornWorker --forwarded-allow-ips="*"'

COPY --chown=python:python requirements.txt .
RUN python -m pip install --no-cache-dir -r requirements.txt
WORKDIR /app
COPY --chown=python:python src/ .
USER python
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "app:app"]