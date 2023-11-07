FROM ubuntu:22.04
ENV DEBIAN_FRONTEND noninteractive

RUN apt update && \
    apt install -y  python3 python3-pip exiftool ffmpeg libsm6 libxext6 && \
    pip install --upgrade pip

COPY requirements.txt /app/requirements.txt

WORKDIR /app

RUN pip install -r requirements.txt

COPY . /app

ENTRYPOINT ["sh", "-c", "python3 main.py"]
EXPOSE 5000
