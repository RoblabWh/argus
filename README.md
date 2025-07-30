# Argus Rewrite

This is a complete rewrite of Argus with the goal of making it more professional, reliable, and maintainable.

**Key Improvements:** 
- The new version will use a **PostgreSQL** database to manage and store reports more robustly.

- The frontend will be rebuilt in **React**, using shadcn/ui to deliver a modern, consistent UI and improved user experience.

- Mapping and other compute-intensive tasks will be moved to separate worker processes, coordinated via Redis for better scalability and modularity.

- The project will continue to use **Docker** to ensure easy installation and deployment, reducing friction for both developers and users.


The goal is to build a more robust and professional codebase, making Argus a future-proof platform that’s easier to develop, deploy, and extend.

 
  

*Until this branch is pushed to main, please use the current main branch version*


**installation and setup**

1. Docker nneds to be installed
2. clone complete repo (branch)
3. setup env
    1. copy env.example and rename to .env 
    2. set a openweatherapi key (or weather data can not be retireved) 
    3. If you want to access ARGUS from your network set the VITE_API_URL to your loacl ip adress "http://[ip_adress]:8000"
4. run  ```./argus.sh up --build```
5. open in Browser (port 5173)
