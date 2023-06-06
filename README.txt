README
======

There are several ways to run the ARGUS WebApp.

For Linux Users
===============
If you have Docker installed, you can run the start-with-docker.sh script.
This will build the image and run the container.
It will also mount a directory called data in the current directory to the container.
This is where all images and project descriptions will be stored.
If there is no data directory, it will be created.

As an alternative you can run the start.sh script.
This will use venev to create a virtual environment and install all dependencies.
It is important to note that you need to install the exiftool manually on your system.


For Windows Users
=================
You will need to have Docker installed.
Then you can run the start-windows-docker.bat script.
This will build the image and run the container.
It will also mount a directory called data in the current directory to the container.
This is where all images and project descriptions will be stored.
If there is no data directory, it will be created.

Currently, it is not possible to run the WebApp without Docker on Windows.
If you want to access the WebApp from another computer on the same network, please use a linux system, as described above.



Accessing the WebApp
====================
The WebApp is typically running in port 5000.
You can either use your loaclhost or the IP address of the machine running the WebApp (as long as you are using linux).
if you are using the provided scripts to start the WebApp, your browser should automatically open the WebApp in a web browser.

