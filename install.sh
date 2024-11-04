#!/bin/bash
set -e

# get path to argus
ARGUS_PATH="$(dirname "$(realpath "${BASH_SOURCE[0]}")")"
ARGUS_INSTALL_PATH=/opt/argus

# ask for root access
sudo -v

# build the argus containers and download the rest
. "$ARGUS_PATH/argus.sh" build --build-arg NUM_THREADS=4
. "$ARGUS_PATH/argus.sh" pull --ignore-buildable

# install argus to known global path
sudo mkdir -p "$ARGUS_INSTALL_PATH"
sudo cp -r "$ARGUS_PATH/argus.sh" "$ARGUS_PATH"/docker-compose*.yml "$ARGUS_PATH/webodm_settings.py" "$ARGUS_PATH/uninstall.sh" "$ARGUS_INSTALL_PATH"
sudo ln -sf "$ARGUS_INSTALL_PATH/argus.sh" /usr/local/bin/argus

# write env to file
echo "Writing configuration:"
printenv | grep '^ARGUS_' | sudo tee "$ARGUS_INSTALL_PATH/default.env"

# install and load systemd service for argus
sudo cp "$ARGUS_PATH/argus.service" /etc/systemd/system/
sudo systemctl daemon-reload
