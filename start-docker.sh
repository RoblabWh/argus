#!/bin/bash

APPNAME='ARGUS'
DATAPATH=~/$APPNAME/uploads

# create directory if needed
mkdir -p "$DATAPATH"

# check if rebuild flag is provided
rebuild=false
if [ "$1" == "--rebuild" ]; then
  rebuild=true
fi

# build image if not present
if [ "$rebuild" == true ] || [ -z "$(docker images -q $APPNAME)" ]; then
  docker build -t "$APPNAME" "${0%/*}"
fi

# run image
docker run \
    --gpus all \
    --runtime=nvidia \
    --add-host host.docker.internal:host-gateway \
    -p "5000:5000" \
    --rm \
    -it \
    -v /var/run/docker.sock:/var/run/docker.sock \
    -v "${DATAPATH}:/app/static/uploads" \
    -v "${APPNAME}_model_weights:/app/detection/model_weights" \
    "$APPNAME"
