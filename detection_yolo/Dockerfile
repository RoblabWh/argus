ARG PYTORCH="2.9.1" 
ARG CUDA="12.8" 
ARG CUDNN="9" 

FROM pytorch/pytorch:${PYTORCH}-cuda${CUDA}-cudnn${CUDNN}-devel

# System dependencies
RUN apt-get update \
    && apt-get install -y ffmpeg libsm6 libxext6 git curl unzip \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Python deps
COPY requirements.txt /detection/requirements.txt
RUN pip install --no-cache-dir -r /detection/requirements.txt

WORKDIR /detection_yolo

COPY . /detection_yolo

# Warm the model cache, then start the celery worker
ENTRYPOINT ["/detection_yolo/entrypoint.sh"]
