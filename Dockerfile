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

# Upgrade pip
RUN pip3 install --upgrade pip setuptools wheel

# Copy code
COPY . /app/
WORKDIR /app/

# Install deps
RUN pip3 install --no-cache-dir -r requirements.txt

# Run
CMD ["python3", "-m", "YUKIWAFUS"]
