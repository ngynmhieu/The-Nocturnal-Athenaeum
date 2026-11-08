FROM nvidia/cuda:12.8.1-runtime-ubuntu24.04

WORKDIR /app
ENV PYTHONUNBUFFERED=1 PYTHONPATH=/app HF_HOME=/cache/huggingface

# No compiler needed: requirements.txt pulls a prebuilt manylinux CUDA wheel of
# llama-cpp-python, and this runtime image already ships cudart/cuBLAS.
# libgomp1 is the OpenMP runtime that llama.cpp's CPU backend links against.
RUN apt-get update && apt-get install -y --no-install-recommends \
      python3.12 python3-pip curl libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY models/requirements.txt /app/models/requirements.txt
RUN pip install --no-cache-dir --break-system-packages -r /app/models/requirements.txt

COPY models/ /app/models/

EXPOSE 8001
CMD ["python3", "-m", "models.run_models"]
