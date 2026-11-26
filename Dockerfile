# SalesPilot AI — single image: FastAPI backend + static frontend.
# The backend serves the API under /api/v1 and the built frontend
# (frontend/dist) at / when it is present in the image.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Backend dependencies first (better layer caching)
COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install -r backend/requirements.txt

# Application code + frontend
COPY backend/ ./backend/
COPY frontend/dist/ ./frontend/dist/

WORKDIR /app/backend
EXPOSE 8000

# Hosts like Render/Railway inject $PORT; default to 8000 locally / in compose.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
