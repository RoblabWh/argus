#!/bin/bash

sudo apt-get install python3-venv xterm

cd src/

python3 -m venv env

source env/bin/activate

./env/bin/python3 -m pip install --upgrade pip

pip install -r requirements.txt

#resize -s 33 125

#clear

python3 main_new.py "$@"
#prüfen in welchem os man ist, davon abhängig pwd oder andere pfad angeben

#im ImageMapper verzeichnis wo auch das Dockerfile liegt
#docker build -t image_mapper .
#docker run -p 5000:5000 --rm -it -v /var/run/docker.sock:/var/run/docker.sock -v $(pwd)/data:/app/static/uploads image_mapper
