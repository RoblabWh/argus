# FROM pytorch/pytorch:1.13.1-cuda11.6-cudnn8-devel
# ENV DEBIAN_FRONTEND noninteractive
#
# RUN apt update && \
#     apt install -y  python3 python3-pip exiftool ffmpeg libsm6 libxext6 && \
#     pip install --upgrade pip \
#     pip install "mmcv-full==1.7.1" \
#     pip install "mmdet==2.28.1"
#
# COPY src /app
# WORKDIR /app
#
# RUN pip install -r requirements.txt
#
# ENV AM_I_IN_A_DOCKER_CONTAINER Yes

FROM ubuntu:22.04
ENV DEBIAN_FRONTEND noninteractive

RUN apt update && \
    apt install -y  python3 python3-pip exiftool ffmpeg libsm6 libxext6 && \
    pip install --upgrade pip

COPY src /app
WORKDIR /app

RUN pip install -r requirements.txt

ENV AM_I_IN_A_DOCKER_CONTAINER Yes

ENTRYPOINT ["python3", "main.py"]
EXPOSE 5000