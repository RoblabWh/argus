In order to use the installer you must download the exiftool windows standalone executable, e.g.
https://exiftool.org/exiftool-12.41.zip, unzip it and rename it to exiftool.exe, move it to your
Windows Directory*
There also exists a script that installs exiftool automatically. To run it rightclick it and run as admin. 

Then run the Installer and execute ImageMapper.exe, the popped up terminal can be ignored and minimized


*You can figure this one out by pressing Win + R, enter "cmd", and then enter "echo %windir%" into the commandline.
It will output you the folder, to which you have to move the exiftool.exe.

Notes:
The version for --noconsole currently works way worse, because everytime exiftool is used a terminal
opens and closes, I didn't find a fix for that yet.