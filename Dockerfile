FROM python:3.11-slim

ENV PIP_NO_CACHE_DIR=1
ENV PYTHONUNBUFFERED=1

# System deps
RUN apt-get update && apt-get install -y \
    git \
    build-essential \
    ffmpeg \
    libcairo2-dev \
    pkg-config \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# The base Python image already includes pip. Avoid self-upgrading during
# builds because transient PyPI 5xx responses can fail the whole deployment.

# Copy code
COPY . /app/
WORKDIR /app/

# Install deps
RUN python3 -m pip install \
    --disable-pip-version-check \
    --no-cache-dir \
    --retries 10 \
    --timeout 120 \
    -r requirements.txt

# Run
CMD ["python3", "-m", "YUKIWAFUS"]
