![Argus Logo](https://github.com/RoblabWh/argus/blob/main/app/static/default/Argus_icon_dark_title-long_white_BG_scaled.PNG?raw=true)

# ARGUS

**The ARGUS WebApp is currently in development.**

ARGUS is a documentation and analysis app designed for structured work with drone images in rescue operations. Its main functions include creating orthophotos from mapping flights with UAVs, presenting flight data and individual images in a structured manner, and evaluating infrared images. Additionally, ARGUS offers extensive object recognition functionalities with specially developed classifiers based on our own datasets ([paper link](https://arxiv.org/abs/2310.05512), [dataset link](https://www.kaggle.com/datasets/julienmeine/rescue-object-detection)) from real-world missions. The established drone software OpenDroneMaps ([ODM link](https://www.opendronemap.org/) ) is also integrated into ARGUS.
Since ARGUS is a WebApp, it can be accessed from every device within the same network as the server. It is recommended to use Chrome (or any Chrome-based browser).


This WebApp was developed at the Westphalian University of Applied Sciences (Westfälische Hochschule) as part of the E-DRZ research project, funded by the German Federal Ministry of Education and Research. For more details about our latest research findings, you can read our paper published at [SSRR 2023](#to-be-added-after-conference).

*Please note that ARGUS is intended for use in a scientific context and does not offer the reliability and stability of fully developed commercial software.*


# Dependencies
To run the server, the following is needed:
- Linux
- [Docker & Docker Compose](https://docs.docker.com/engine/install/)
- (Optional) [Nvidia Docker](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html)

Without Nvidia Docker, the object detection pipeline will use the CPU to run our neural networks, and WebODM will also run without the GPU.

## Installing
1. Clone the repository.
2. Run `./install.sh` from the repository directory.

## Running with Installation
1. Run `./argus up`.

## Running without Installation
1. Clone the repository.
2. Navigate to the `argus` directory.
3. Run `./argus up --build`.

## Utilizing the systemd Service
1. Install ARGUS.
2. Enable the service with `systemctl enable argus`.

## Uninstalling

### Without Removing Images and User Data
Run `/opt/argus/uninstall.sh`.

### With Removing Images and User Data
Run `/opt/argus/uninstall.sh all`.

### Example
Cooming soon

## Accessing the WebApp

The WebApp typically runs on port 5000. You can use either your localhost or the IP address of the machine running the WebApp. It should be visible to all devices on the same network.

# Known Issues
- Firefox may encounter problems when uploading larger files, such as high-resolution panoramic photos.
- Since ARGUS is still in development, starting multiple tasks simultaneously can lead to unexpected behavior or, in rare cases, system crashes.
- Currently, ARGUS primarily supports and is tested with DJI drones (DJI M30T, as well as multiple Mavic and Mavic Enterprise models).
