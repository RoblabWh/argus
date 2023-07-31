README
======

The ARGUS WebApp is still in development.
The object detection is currently not working inside the docker container.

Running with Docker
===================
You will need to have Docker installed.
Make sure to also install the NVIDIA Container Toolkit
https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html#docker

Run the start-docker.sh script.
This will build the image and run the container.
Once build the script will only run the container.
If you want to rebuild the image you will need to run the script with the --rebuid flag.
It will also mount a directory called data to the container where you can see the uploaded images without the server running.
This is where all images and project descriptions will be stored.

Currently, it is not easily possible to run the WebApp without Docker.
Accessing the WebApp from another computer on the same network is currently only possible with a linux system.


Accessing the WebApp
====================
The WebApp is typically running in port 5000.
You can either use your loaclhost or the IP address of the machine running the WebApp (as long as you are using linux).



conda env Vorgehen

conda create --name argus python
conda activate argus
conda install pip (,üsste man eigentlich schon haben, aber nur zur Sicherheit)
pip install numpy
pip install vincenty
pip install utm
pip install geopy
pip install shapely
pip install descartes
pip install pyexifinfo
pip install imutils
pip install Pillow (müsste dann eigneltich shco da sein)
pip install requests
pip install opencv-python
pip install scipy
pip install docker==6.0.0
pip install flask==2.2.2
pip install pyodm==1.5.10
pip install pyocclient

pip install --force-reinstall -v requests==2.28.0
(Version 2.28.0 needed or docker error will occure)
// matplotlib
// piexif
// weathercom
// scikit_image
// ipython




mmdet
ins conda env gehen, dann:
conda install pytorch torchvision torchaudio pytorch-cuda=11.8 -c pytorch -c nvidia
git clone https://github.com/open-mmlab/mmdetection.git -b v2.28.1
cd mmdetection/
pip install -r requirements/build.txt
pip install "git+https://github.com/open-mmlab/cocoapi.git#subdirectory=pycocotools"
pip install -v -e .
pip install mmcv-full==1.7.1
pip install mmpycocotools==12.0.3
