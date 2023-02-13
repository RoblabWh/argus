@echo off

if "%OS%" == "Windows_NT" (
  echo "Windows detected"
  if not exist "data" (
    mkdir data
    echo "Data folder created"
  ) else (
    echo "Data folder already exists"
  )
  docker build -t image_mapper .
  docker run --rm -it -p 5000:5000 -v %cd%\data:/app/static/uploads image_mapper
) else (
  echo "Unsupported operating system"
)
pause
