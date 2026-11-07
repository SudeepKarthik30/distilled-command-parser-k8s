# Command Parser Microservice Containerfile
# Base Python runtime on lightweight Debian Bookworm
FROM python:3.11-slim

# System configuration and environment clamps for CPU-bound PyTorch inference
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    OMP_NUM_THREADS=1 \
    MKL_NUM_THREADS=1

WORKDIR /srv/app

# Pre-install PyTorch CPU-only wheel to keep final image size under 2.0 GB
RUN pip install --no-cache-dir torch==2.15.0 --index-url https://download.pytorch.org/whl/cpu

# Copy and install pinned requirements
COPY service/requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Bundle application service logic
COPY service/ service/

EXPOSE 8000

# Start Uvicorn ASGI server hosting the FastAPI application
CMD ["uvicorn", "service.app:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
