#check if a directory called data exists in current directory

if [ ! -d "data" ]; then
  mkdir data
fi

docker build -t image_mapper .
docker run -p 5000:5000 --rm -it -v /var/run/docker.sock:/var/run/docker.sock -v $(pwd)/data:/app/static/uploads image_mapper
