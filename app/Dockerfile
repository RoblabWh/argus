FROM ubuntu:22.04
ENV DEBIAN_FRONTEND noninteractive

RUN apt update && \
    apt install -y  python3 python3-pip exiftool ffmpeg libsm6 libxext6 && \
    pip install --upgrade pip

COPY . /app
WORKDIR /app

RUN pip install -r requirements.txt

ENTRYPOINT ["sh", "-c", "python3 main.py"]
EXPOSE 5000
