# Argus Rewrite

This is a complete rewrite of Argus with the goal of making it more professional, reliable, and maintainable.

**Key Improvements:** 
- The new version will use a **PostgreSQL** database to manage and store reports.

- The frontend will be rebuilt in **React**, using shadcn/ui to deliver a modern, consistent UI and improved user experience.

- Mapping and other compute-intensive tasks will be moved to separate worker processes, coordinated via celery/redis for better scalability and modularity.

- The project will continue to use **Docker** to ensure easy installation and deployment, reducing friction for both developers and users.


The goal is to build a more robust and professional codebase, making Argus a future-proof platform that’s easier to develop, deploy, and extend.


---


**installation and setup**

1. Docker needs to be installed (install nvidia-docker)
2. clone complete repo (branch) (make sure to use --recursivce) git clone --branch major-rewrite --recursive https://github.com/RoblabWh/argus.git
4. run  ```./argus.sh up --build```
    - a local .env file will be created during the first launch (or always when the .env is missing), based on env.example
    - the ip adress of the backend will be set automatically (needed acess over the network) - the ip can be updated autoamtically on start by setting ```--refresh-ip```
    - if you want to load weather data, set OPEN_WEATHER_API_KEY with your own API key from [openweathermap](https://openweathermap.org/)
    - if you made manual changes to the .env, restart the containers
    - to use WebODM clone the official webodm container and adjust the webodm path and username + password in the argus env (and set ENABLE_WEBODM to true) 
5. open in Browser (port 5173)




-----


### Until this branch is pushed to main, please use the current main branch version



### Image and Metadata Requirements

ARGUS can display images from a variety of cameras and drones. However, to process these images into orthophotos, specific metadata is required.
The mapping is based on the following data:

- **Camera model name** – Used to map the metadata keys of each camera model to the correct variables.- This has to be done for each camera model. If not set ARGUS tries to retrieve the values with some default keys
- **Creation date** – Date and time the image was captured.
- **Image width and height** – Can always be extracted automatically.
- **Projection type** – Used to filter out panoramic images. Only necessary if actual panoramic images are present.
- **GPS latitude and longitude**
- **Relative altitude** (distance to ground) – If not found in the metadata, a default value can be set by the user on the upload page (note: using a default may reduce accuracy).
- **Altitude** – Absolute altitude of the camera/drone.
- **Field of view (FOV)** – (also fov correction. default is 1.0, if mapping is off, this factor can be used to alter the fov).
- **UAV roll, pitch, and yaw** – Orientation of the drone (roll is currently not used).
- **Gimbal/Camera roll, pitch, and yaw** – Orientation of the camera (roll is currently not used).



Thermal/ Infrared (IR) Images
- **Image source tag** – The preferred and most robust method. IR images can be identified by a value (e.g., thermal or infrared) in the ImageSource tag. Both, the metadta key and the value for thermal images must be set for the camera model.
- **Image dimensions or filename pattern** – Alternatively, a predefined image height/width or a filename pattern (regular expression) can be used for detection. This must also be configured beforehand but is less reliable than using the ImageSource tag.
- **IR scale (IR_scale)** – Used to correctly scale the IR image when overlaying it on top of the RGB image, can be part of the camera model settings, does not need to be sotred in images metadta
