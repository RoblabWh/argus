ARG PYTORCH="2.7.0" # PYTORCH="2.2.0" new for the 5090
ARG CUDA="12.8" # CUDA="12.1"
ARG CUDNN="9" # CUDNN="8"

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

# Start celery worker
ENTRYPOINT ["celery", "-A", "tasks_detection_yolo", "worker", "-Q", "detection_yolo", "--loglevel=info"]
