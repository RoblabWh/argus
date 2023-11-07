#!/bin/bash
set -e

# get path to argus
ARGUS_PATH="$(dirname "$(realpath "${BASH_SOURCE[0]}")")"

if [ "$(basename "$ARGUS_PATH")" != "argus" ]; then
    echo "Argus install path is not a direcory with name \"argus\", aborting."
    exit 1
fi

# ask for root access
sudo -v

# remove the docker containers, images and volumes
if [ "$1" == "all" ]; then
    "$ARGUS_PATH/argus.sh" down --rmi all --volumes
else
    "$ARGUS_PATH/argus.sh" down
fi

# remove installed files
sudo rm /usr/local/bin/argus
sudo rm -r "$ARGUS_PATH"
sudo rm /etc/systemd/system/argus.service
sudo systemctl daemon-reload
