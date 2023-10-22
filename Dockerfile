FROM ubuntu:22.04
ENV DEBIAN_FRONTEND noninteractive

RUN apt update && \
    apt install -y  python3 python3-pip exiftool ffmpeg libsm6 libxext6 && \
    pip install --upgrade pip

COPY src /app
WORKDIR /app

RUN pip install -r requirements.txt

ENV AM_I_IN_A_DOCKER_CONTAINER Yes

ENTRYPOINT ["sh", "-c", "python3 main.py $0"]
EXPOSE 5000