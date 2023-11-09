# ARGUS

The ARGUS WebApp is still in development.

# Dependencies
- Linux
- [Docker & Docker Compose](https://docs.docker.com/engine/install/)
- (Optional) [Nvidia Docker](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html)

## Installing
1. clone repo
2. run repo/install.sh

## Running with installation
1. argus up

## Running without installation

1. clone repo
2. cd argus
3. ./argus up --build

## Utilising the systemd service
- systemctl enable argus


## Uninstalling

### Without removing images and userdata
 /opt/argus/uninstall.sh

### With removing images and userdata
 /opt/argus/uninstall.sh all

## In Prosa und alt
Run the start-docker.sh script.
This will build the image and run the container.
Once build the script will only run the container.
If you want to rebuild the image you will need to run the script with the --rebuid flag.
It will also mount a directory called data to the container where you can see the uploaded images without the server running.
This is where all images and project descriptions will be stored.

Currently, it is not easily possible to run the WebApp without Docker.
Accessing the WebApp from another computer on the same network is currently only possible with a linux system.


## Accessing the WebApp

The WebApp is typically running in port 5000.
You can either use your loaclhost or the IP address of the machine running the WebApp.
