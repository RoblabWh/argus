![Argus Logo](https://github.com/RoblabWh/argus/blob/main/app/static/default/Argus_icon_dark_title-long_white_BG_scaled.PNG?raw=true)

# ARGUS - Aerial Rescue and Geospatial Utility System

**The ARGUS WebApp is currently in development.**

ARGUS is a documentation and analysis app designed for structured work with drone images in rescue operations. Its main functions include creating orthophotos from mapping flights with UAVs, presenting flight data and individual images in a structured manner, and evaluating infrared images. Additionally, ARGUS offers extensive object recognition functionalities with specially developed classifiers based on our own datasets ([paper link](https://arxiv.org/abs/2310.05512), [dataset link](https://www.kaggle.com/datasets/julienmeine/rescue-object-detection)) from real-world missions. The established drone software OpenDroneMaps ([ODM link](https://www.opendronemap.org/) ) is also integrated into ARGUS.
Since ARGUS is a WebApp, it can be accessed from every device within the same network as the server. It is recommended to use Chrome (or any Chrome-based browser).
Currently, Argus has only been tested with data from DJI drones (Matrice M30T, Mavic Enterprise, Mavic 2, Mavic 3). Using data from other drones can lead to problems.

This WebApp was developed at the Westphalian University of Applied Sciences (Westfälische Hochschule) as part of the E-DRZ research project, funded by the German Federal Ministry of Education and Research. For more details about our latest research findings, you can read our paper published at [SSRR 2023](#to-be-added-after-conference).

*Please note that ARGUS is intended for use in a scientific context and does not offer the reliability and stability of fully developed commercial software.*


# Dependencies
To run the server, the following is needed:
- Linux
- Docker & Docker Compose [(installation guide)](https://docs.docker.com/engine/install/)
- (Optional) Nvidia Docker [(installation guide)](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html)

Without Nvidia Docker, the object detection pipeline will use the CPU to run our neural networks, and WebODM will also run without the GPU.

## Installing
1. Clone the repository.
2. Run `./install.sh` from the repository directory. # take a coffee, building all images need up to 20 minutes

## Running with Installation
1. Run `argus up`

## Running without Installation
1. Clone the repository.
2. Navigate to the `argus` directory.
3. Run `./argus.sh up --build`

## Utilizing the systemd Service
1. Install ARGUS.
2. Enable the service with `systemctl enable argus`.

## Uninstalling

### Without Removing Images and User Data
Run `/opt/argus/uninstall.sh`.

### With Removing Images and User Data
Run `/opt/argus/uninstall.sh all`.

## Accessing the WebApp
The WebApp typically runs on port 5000. You can use either your localhost or the IP address of the machine running the WebApp. It should be visible to all devices on the same network.

### Example
We have an already processed example project of a flooding in Germany in 2021 available [(ArgusExample01.zip)](https://dF2wQbFNW2zuCpK:fire@w-hs.sciebo.de/public.php/webdav/argus/ArgusExample01.zip
). Use the import feature under "new report" on the projects overview page to load the project. 

Short Demo video on YouTube: [ARGUS - Aerial Rescue and Geospatial Utility System](https://www.youtube.com/watch?v=URO4lSgkyF8)


# Papers
1. Redefining Recon: Bridging Gaps with UAVs, 360° Cameras, and Neural Radiance Fields; Hartmut Surmann, Niklas Digakis, Jan-Nicklas Kremer, Julien Meine, Max Schulte, Niklas Voigt, [IEEE International Symposium on Safety, Security, and Rescue Robotics (SSRR2023), Fukushima, Japan, 13-15. Nov. 2023.](https://github.com/RoblabWh/argus/blob/main/papers/ssrr2023-surmann.pdf) (cite this).
2. UAVs and Neural Networks for search and rescue missions, Hartmut Surmann, Artur Leinweber, Gerhard Senkowski, Julien Meine, Dominik Slomma, [56th International Symposium on Robotics (ISR Europe) | September 26-27, 2023](https://arxiv.org/abs/2310.05512).
3. Lessons from Robot-Assisted Disaster Response Deployments by the German Rescue Robotics Center Task Force, Hartmut Surmann, Ivana Kruijff-Korbayova, Kevin Daun, Marius Schnaubelt, Oskar von Stryk, Manuel Patchou, Stefan Boecker, Christian Wietfeld, Jan Quenzel, Daniel Schleich, Sven Behnke, Robert Grafe, Nils Heidemann, Dominik Slomma,  [Journal of Field robotics, Wiley, 2023](https://onlinelibrary.wiley.com/doi/full/10.1002/rob.22275)
4. Deployment of Aerial Robots during the Flood Disaster in Erftstadt / Blessem in July 2021, Hartmut Surmann, Dominik Slomma, Robert Grafe, Stefan Grobelny, [2022 8th International Conference on Automation, Robotics and Applications (ICARA), Prague, Czech Republic, 2022, pp. 97-102](https://ieeexplore.ieee.org/document/9738529).
5. Deployment of Aerial Robots after a major fire of an industrial hall with hazardous substances, a report, Hartmut Surmann, Dominik Slomma, Stefan Grobelny, Robert Grafe, [2021 IEEE International Symposium on Safety, Security, and Rescue Robotics (SSRR2021), New York City, NY, USA, 2021, pp. 40-47](https://ieeexplore.ieee.org/document/9597677).

# Known Issues   
- Firefox may encounter problems when uploading larger files, such as high-resolution panoramic photos.
- Since ARGUS is still in development, starting multiple tasks simultaneously can lead to unexpected behavior or, in rare cases, system crashes.
- Currently, ARGUS primarily supports and is tested with DJI drones (DJI M30T, as well as multiple Mavic and Mavic Enterprise models).
- In order to generate fast orthophotos, the UAVs gimbal should orient the camera orthogonal towards ground (-90°).
- If WebODM has many 'WARNING Bad Request: /api/token-auth/' during startup and the redirection from ARGUS does not work, try pulling a new WebODM image with './argus.sh pull --ignore-buildable' and rebuild the server with './argus.sh up --build'.
