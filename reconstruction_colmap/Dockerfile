# COLMAP SfM worker. The official image ships the CUDA `colmap` CLI on PATH;
# we add Python + the orchestration deps (pycolmap, pyproj, …) on top.
#
# NOTE: keep the pycolmap pin in requirements.txt compatible with the COLMAP
# version baked into this base image (pycolmap only reads the binaries it wrote).
FROM colmap/colmap:latest

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update \
    && apt-get install -y --no-install-recommends python3 python3-pip python3-dev \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /reconstruction_colmap/requirements.txt
RUN pip3 install --no-cache-dir --break-system-packages -r /reconstruction_colmap/requirements.txt

WORKDIR /reconstruction_colmap
COPY . /reconstruction_colmap

# The base image sets an ENTRYPOINT of `colmap`; override it so we launch celery.
ENTRYPOINT ["celery", "-A", "tasks_colmap", "worker", "-Q", "colmap", "--loglevel=info"]
