FROM python:3.12.2

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        ffmpeg \
        exiftool \
        libsm6 \
        libxext6 \
        libpq-dev \
        netcat-openbsd && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Make the entrypoint script executable
RUN chmod +x entrypoint.sh

# Use entrypoint script to run migrations then start the server
ENTRYPOINT ["sh", "-c","./entrypoint.sh"]
EXPOSE 8000

