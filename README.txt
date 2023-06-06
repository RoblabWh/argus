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


