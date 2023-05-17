#!/bin/bash

APPNAME='argus'
DATAPATH=~/$APPNAME/uploads

# create directory if needed
mkdir -p "$DATAPATH"

# build image if not present
if [ -z "$(docker images -q $APPNAME)" ]; then
  docker build -t "$APPNAME" "${0%/*}"
fi
# run image
docker run -p "5000:5000" --rm -it -v /var/run/docker.sock:/var/run/docker.sock -v "${DATAPATH}:/app/static/uploads" -v "${APPNAME}_model_weights:/app/detection/model_weights" "$APPNAME"
