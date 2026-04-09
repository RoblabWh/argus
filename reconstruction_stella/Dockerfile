FROM nvidia/cuda:12.9.1-devel-ubuntu24.04
ENV DEBIAN_FRONTEND noninteractive

# install dependencies via apt
RUN apt-get update --yes && \
    apt-get upgrade --yes --no-install-recommends && \
    apt-get install --yes --no-install-recommends \
        # basic dependencies
        git \
        curl \
        cmake \
        ffmpeg \
        ninja-build \
        clang \
        pkg-config \
        # g2o dependencies
        libatlas-base-dev \
        libsuitesparse-dev \
        libglew-dev \
        # backward-cpp dependencies
        binutils-dev \
        # stella-vslam dependencies
        libomp-dev \
        libopencv-dev \
        libeigen3-dev \
        libyaml-cpp-dev \
        sqlite3 \
        libsqlite3-dev \
        # python dependencies
        python3 \
        python3-pip \
        python3-opencv \
        python3-msgpack \
        python3-numpy \
        python3-scipy \
        python3-dev \
        pybind11-dev && \
    pip install --break-system-packages \
        pybind11-stubgen

# compiler settings
ENV C=clang CXX=clang++
ARG NUM_THREADS=0

# g2o
ARG G2O_VERSION=20230223_git
RUN cd /tmp && \
    git clone https://github.com/RainerKuemmerle/g2o.git --branch ${G2O_VERSION} --depth 1 && \
    cd g2o && \
    cmake -B build -G Ninja \
        -DCMAKE_BUILD_TYPE=Release \
        -DBUILD_SHARED_LIBS=ON \
        -DBUILD_UNITTESTS=OFF \
        -DG2O_USE_CHOLMOD=OFF \
        -DG2O_USE_CSPARSE=ON \
        -DG2O_USE_OPENGL=OFF \
        -DG2O_USE_OPENMP=OFF \
        -DG2O_BUILD_APPS=OFF \
        -DG2O_BUILD_EXAMPLES=OFF \
        -DG2O_BUILD_LINKED_APPS=OFF \
        && \
    cmake --build build --parallel $(test ${NUM_THREADS} -eq 0 && nproc || (printf ${NUM_THREADS})) && \
    cmake --install build && \
    cd /tmp && \
    rm -rf *

# backward-cpp
ARG BACKWARD_CPP_COMMIT=5ffb2c879ebdbea3bdb8477c671e32b1c984beaa
RUN cd /tmp && \
    git clone https://github.com/bombela/backward-cpp.git && \
    cd backward-cpp && \
    git checkout ${BACKWARD_CPP_COMMIT} && \
    cmake -B build -G Ninja -DCMAKE_BUILD_TYPE=Release && \
    cmake --build build --parallel $(test ${NUM_THREADS} -eq 0 && nproc || (printf ${NUM_THREADS})) && \
    cmake --install build && \
    cd /tmp && \
    rm -rf *

# stella
COPY stella_vslam_dense /reconstruction_stella/stella_vslam_dense
RUN cd /reconstruction_stella/stella_vslam_dense && \
    export PYTHONPATH=/reconstruction_stella/stella_vslam_dense/build/lib && \
    cmake -B build -G Ninja -DCMAKE_BUILD_TYPE=Release && \
    cmake --build build --parallel $(test ${NUM_THREADS} -eq 0 && nproc || (printf ${NUM_THREADS})) && \
    cmake --install build && \
    ldconfig

# celery
COPY requirements.txt /reconstruction_stella/requirements.txt
RUN pip install --no-cache-dir --break-system-packages -r /reconstruction_stella/requirements.txt

# setup worker
COPY --exclude=stella_vslam_dense --exclude=requirements.txt . /reconstruction_stella
WORKDIR /reconstruction_stella
ENTRYPOINT ["celery", "-A", "tasks_reconstruction_stella", "worker", "-Q", "reconstruction_stella", "--loglevel=info"]
