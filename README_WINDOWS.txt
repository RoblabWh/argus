README
======
activate virtual environment:

cd src

python -m venv env

.\env\Scripts\activate

python -m pip install --upgrade pip

pip install -r .\windowsRequirements.txt

python pyQTgui.py

------
used with python version 3.9.6
------
if installing the pyexifinfo fails,
you need to download the exiftool
standalone executable from https://exiftool.org/install.html
rename it to exiftool.exe and move it to the C:\Windows folder
(adjust partition letter if windows is installed on another partition)