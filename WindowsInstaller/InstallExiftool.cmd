@echo off
IF EXIST %windir%/exiftool.exe ( echo exists) ELSE (
  mkdir %windir%\tmp\exiftool
  cd %windir%\tmp\exiftool
  curl https://exiftool.org/exiftool-12.41.zip --output exiftool.zip
  powershell -Command "Expand-Archive %windir%\tmp\exiftool\exiftool.zip -DestinationPath %windir%\tmp\exiftool"
  ren *.exe ????????.*
  move exiftool.exe %windir%
  rmdir /s /q %windir%\tmp\
)