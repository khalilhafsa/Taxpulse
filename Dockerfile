# Public demo of TaxPulse: one container serving the API and the built frontend.
# The agents replay results recorded with Claude (DEMO_MODE), so no API key is needed or used.

FROM node:22-slim AS frontend
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.13-slim
WORKDIR /app
COPY backend/requirements-demo.txt backend/
RUN pip install --no-cache-dir -r backend/requirements-demo.txt
COPY backend/app backend/app
COPY data/demo data/demo
COPY --from=frontend /app/frontend/dist frontend/dist

ENV DEMO_MODE=true \
    SCHEDULER=false \
    STATIC_DIR=/app/frontend/dist \
    DATABASE_URL=sqlite:////tmp/taxpulse-demo.db \
    UPLOAD_DIR=/tmp/taxpulse-uploads \
    ANTHROPIC_API_KEY=""
WORKDIR /app/backend
EXPOSE 8000
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
