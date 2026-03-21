FROM python:3.12-slim

WORKDIR /app

# System deps for lmdb, faiss, and general build
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install in the required order:
# 1. faiss-cpu first
# 2. flexrag from GitHub (no-deps)
# 3. everything else from requirements.txt
RUN pip install --no-cache-dir faiss-cpu
RUN pip install --no-cache-dir git+https://github.com/ictnlp/FlexRAG.git --no-deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project
COPY app/ ./app/
COPY scripts/ ./scripts/

# Create data and output dirs
RUN mkdir -p data/raw data/processed outputs

CMD ["bash"]
