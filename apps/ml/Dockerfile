# CPU image. For GPU servers use a CUDA base image and the matching torch/onnxruntime-gpu wheels.
FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 HF_HOME=/models/hf
RUN apt-get update && apt-get install -y --no-install-recommends git libgl1 libglib2.0-0 && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY app ./app
COPY scripts ./scripts
RUN useradd --system --uid 10002 --home /app saasta && mkdir -p /models && chown -R saasta /models
USER saasta
EXPOSE 8100
# Weights live on the /models volume: run scripts/download_weights.py once (see README).
ENV SAASTA_ML_TRYON_WEIGHTS=/models/tryon
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8100", "--workers", "1", "--no-server-header"]
