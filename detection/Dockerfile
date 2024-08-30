ARG PYTORCH="2.2.0"
ARG CUDA="12.1"
ARG CUDNN="8"

FROM pytorch/pytorch:${PYTORCH}-cuda${CUDA}-cudnn${CUDNN}-devel

RUN mkdir -p /data/.huggingface

ENV TORCH_CUDA_ARCH_LIST="6.0 6.1 7.0 7.5 8.0 8.6+PTX" \
    TORCH_NVCC_FLAGS="-Xfatbin -compress-all" \
    CMAKE_PREFIX_PATH="$(dirname $(which conda))/../" \
    FORCE_CUDA="1" \
    HF_HOME="/data/.huggingface"


# Python 3.8 and pip3
RUN apt-get update
RUN apt-get install -y software-properties-common
RUN apt-get install -y python3.9
RUN ln -s /usr/bin/python3.9 /usr/bin/python
RUN apt-get install -y python3-pip


# (Optional, use Mirror to speed up downloads)
# RUN sed -i 's/http:\/\/archive.ubuntu.com\/ubuntu\//http:\/\/mirrors.aliyun.com\/ubuntu\//g' /etc/apt/sources.list && \
#    pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple

# Install the required packages
RUN apt-get update \
    && apt-get install -y ffmpeg libsm6 libxext6 git ninja-build libglib2.0-0 libsm6 libxrender-dev libxext6 curl unzip \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

RUN pip install torch torchvision transformers[torch] albumentations datasets pycocotools timm safetensors gitpython


COPY requirements.txt /detection/requirements.txt

WORKDIR /detection

RUN pip install -r requirements.txt

COPY . /detection



ENTRYPOINT python3 main.py
EXPOSE 6666
