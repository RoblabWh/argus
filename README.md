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
2. clone complete repo (branch) (make sure to use --recursivce)
4. run  ```./argus.sh up --build```
    - a local .env file will be created during the first launch (or always when the .env is missing), based on env.example
    - the ip adress of the backend will be set automatically (needed acess over the network) - the ip can be updated autoamtically on start by setting ```--refresh-ip```
    - if you want to load weather data, set OPEN_WEATHER_API_KEY with your own API key from [openweathermap](https://openweathermap.org/)
    - if you made manual changes to the .env, restart the containers
    - to use WebODM clone the official webodm container and adjust the webodm path and username + password in the argus env (and set ENABLE_WEBODM to true) 
5. open in Browser (port 5173)




-----


### Until this branch is pushed to main, please use the current main branch version


<!-- Für Settings:
API Key - Waether API
WebODM Account und Settings aus env
Farben Detections 
DRZ Backend URL
Name Autor (für DRZ Backend default
-->
