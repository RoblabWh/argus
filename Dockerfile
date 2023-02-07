FROM ubuntu:20.04
ENV DEBIAN_FRONTEND noninteractive

RUN apt update && \
    apt install -y  python3 python3-pip exiftool ffmpeg libsm6 libxext6 && \
    pip install --upgrade pip

COPY src /app
WORKDIR /app

RUN pip install -r requirements.txt

ENTRYPOINT ["python3", "main_new.py"]
EXPOSE 5000