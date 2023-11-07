ARG PYTORCH="1.9.0"
ARG CUDA="11.1"
ARG CUDNN="8"

FROM pytorch/pytorch:${PYTORCH}-cuda${CUDA}-cudnn${CUDNN}-devel

ARG MODEL_WEIGHTS_FILE="model_weights_mmdet3"

ENV TORCH_CUDA_ARCH_LIST="6.0 6.1 7.0 7.5 8.0 8.6+PTX" \
    TORCH_NVCC_FLAGS="-Xfatbin -compress-all" \
    CMAKE_PREFIX_PATH="$(dirname $(which conda))/../" \
    FORCE_CUDA="1"

# Avoid Public GPG key error
# https://github.com/NVIDIA/nvidia-docker/issues/1631
RUN rm /etc/apt/sources.list.d/cuda.list \
    && rm /etc/apt/sources.list.d/nvidia-ml.list \
    && apt-key del 7fa2af80 \
    && apt-key adv --fetch-keys https://developer.download.nvidia.com/compute/cuda/repos/ubuntu1804/x86_64/3bf863cc.pub \
    && apt-key adv --fetch-keys https://developer.download.nvidia.com/compute/machine-learning/repos/ubuntu1804/x86_64/7fa2af80.pub

# (Optional, use Mirror to speed up downloads)
# RUN sed -i 's/http:\/\/archive.ubuntu.com\/ubuntu\//http:\/\/mirrors.aliyun.com\/ubuntu\//g' /etc/apt/sources.list && \
#    pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple

# Install the required packages
RUN apt-get update \
    && apt-get install -y ffmpeg libsm6 libxext6 git ninja-build libglib2.0-0 libsm6 libxrender-dev libxext6 curl unzip \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install MMEngine and MMCV
RUN pip install openmim && \
    mim install "mmengine==0.8.4" "mmcv==2.0.0"

# Install MMDetection
RUN conda clean --all \
    && git clone -b v3.1.0 https://github.com/open-mmlab/mmdetection.git /mmdetection \
    && cd /mmdetection \
    && pip install --no-cache-dir -e .

RUN curl -u "dF2wQbFNW2zuCpK:fire" "https://w-hs.sciebo.de/public.php/webdav/${MODEL_WEIGHTS_FILE}.zip" -o "/tmp/${MODEL_WEIGHTS_FILE}.zip" && \
    cd /tmp && \
    unzip "${MODEL_WEIGHTS_FILE}.zip" && \
    mkdir /detection && \
    mv "${MODEL_WEIGHTS_FILE}" "/detection/model_weights"

COPY requirements.txt /detection/requirements.txt

WORKDIR /detection

RUN pip install -r requirements.txt

COPY . /detection

ENTRYPOINT python3 main.py
EXPOSE 6000
