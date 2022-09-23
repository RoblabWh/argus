#!/bin/bash

sudo apt-get install python3-venv xterm

cd src/

python3 -m venv env

source env/bin/activate

./env/bin/python3 -m pip install --upgrade pip

pip install -r requirements.txt

#resize -s 33 125

#clear

python3 main.py "$@"
