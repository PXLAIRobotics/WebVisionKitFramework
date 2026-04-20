FROM python:3.11-slim

ARG SOURCE_HASH=unknown

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

LABEL webvisionkit.source-hash="${SOURCE_HASH}"

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libglib2.0-0 \
    libgl1 \
    libsm6 \
    libxext6 \
    libxrender1 \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir \
    opencv-python-headless==4.13.0.92 \
    numpy==2.4.4 \
    requests==2.33.1 \
    websocket-client==1.9.0

COPY api/webvisionkit /app/webvisionkit

CMD ["python", "-m", "webvisionkit.runner"]
