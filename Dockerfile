# Hugging Face Spaces compatible Dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install git (needed for GitPython to clone repos)
RUN apt-get update && apt-get install -y git && rm -rf /var/lib/apt/lists/*

# Copy and install dependencies first (layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Pre-download ML models during build so they are baked into the image
# This avoids cold-start download delays and works around HF Spaces cache issues
RUN python -c "
from sentence_transformers import SentenceTransformer, CrossEncoder
print('Downloading embedding model...')
SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')
print('Downloading cross-encoder...')
CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2')
print('Models ready.')
"

# Copy application code
COPY app/ ./app/

# Create persistent storage directories
# On HF Spaces, /data is the persistent volume
RUN mkdir -p /data/repos /data/chroma

# HF Spaces runs as non-root user 1000
RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app /data
USER 1000

# Expose port (HF Spaces expects 7860)
EXPOSE 7860

# Start FastAPI on port 7860
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "7860"]