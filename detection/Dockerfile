ARG PYTORCH="2.2.0"
ARG CUDA="12.1"
ARG CUDNN="8"

FROM pytorch/pytorch:${PYTORCH}-cuda${CUDA}-cudnn${CUDNN}-devel

# Hugging Face cache location
ENV HF_HOME="/data/.huggingface" \
    TORCH_CUDA_ARCH_LIST="6.0 6.1 7.0 7.5 8.0 8.6+PTX" \
    TORCH_NVCC_FLAGS="-Xfatbin -compress-all" \
    CMAKE_PREFIX_PATH="$(dirname $(which conda))/../" \
    FORCE_CUDA="1"

# Install system dependencies
RUN apt-get update \
    && apt-get install -y ffmpeg libsm6 libxext6 git ninja-build libglib2.0-0 libxrender-dev curl unzip \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*


# Install Python packages
RUN pip install torch torchvision transformers[torch] albumentations datasets pycocotools timm safetensors gitpython

COPY requirements.txt /detection/requirements.txt
RUN pip install --no-cache-dir -r /detection/requirements.txt

WORKDIR /detection

# Copy app code
COPY . /detection
RUN mkdir -p /data/.huggingface

RUN echo "Hugging Face cache directory: $HF_HOME"

# Start celery worker (GPU-ready)
ENTRYPOINT ["celery", "-A", "tasks_detection", "worker", "-Q", "detection", "--loglevel=info"]
