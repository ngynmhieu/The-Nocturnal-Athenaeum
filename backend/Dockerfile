FROM python:3.12-slim

WORKDIR /app
ENV PYTHONUNBUFFERED=1 PYTHONPATH=/app

COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r /app/backend/requirements.txt
# Headless Chromium (+ its system libraries) for the read module's per-site extractors.
RUN python -m playwright install --with-deps chromium

COPY backend/ /app/backend/

EXPOSE 8000
CMD ["python", "-m", "backend.run_backend"]
