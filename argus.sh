#!/bin/bash
set -e

# get path to argus
ARGUS_PATH="$(dirname "$(realpath "${BASH_SOURCE[0]}")")"
echo "Argus path is $ARGUS_PATH"

# export default env for all unset vars
set -a
. "$ARGUS_PATH/default.env"
set +a

# detect if a gpu is available
set +e
if [ -z ${ARGUS_GPU_NVIDIA+x} ]; then
	export ARGUS_GPU_NVIDIA=false

	if lspci | grep -q 'NVIDIA' || lspci | grep -q "VGA.*NVIDIA" || \
		(command -v nvidia-smi >/dev/null 2>&1 && [[ $(nvidia-smi -L | grep "GPU 0:" | awk -F ': ' '{print $2}' | awk -F '(' '{print $1}') == *"NVIDIA"* ]]); then
		echo "NVIDIA GPU has been found"
		if cat /etc/docker/daemon.json | grep -q nvidia-container-runtime; then
			export ARGUS_GPU_NVIDIA=true
		else
			echo "Missing nvidia docker toolkit, falling back to CPU"
		fi
	fi
fi
if [ -z ${ARGUS_GPU_INTEL+x} ]; then
	export ARGUS_GPU_INTEL=false

	if lspci | grep -q "VGA.*Intel"; then
		echo "INTEL GPU has been found"
		export ARGUS_GPU_INTEL=true
		export ARGUS_RENDER_GROUP_ID=$(getent group render | cut -d":" -f3)
	fi
fi
if [ -z ${ARGUS_GPU_AMD+x} ]; then
	export ARGUS_GPU_AMD=false

	if lspci | grep -q "VGA.*AMD"; then
		echo "AMD GPU has been found"
		export ARGUS_GPU_AMD=true
	fi
fi
set -e

# add docker compose overlay yml for gpu if detected
docker_compose="docker compose -f $ARGUS_PATH/docker-compose.yml -f $ARGUS_PATH/docker-compose.nodeodm.yml"
if $ARGUS_GPU_NVIDIA; then
	echo "Using NVIDIA GPU"
	docker_compose="$docker_compose -f $ARGUS_PATH/docker-compose.gpu.nvidia.yml"
elif $ARGUS_GPU_INTEL; then
	echo "Using INTEL GPU"
	docker_compose="$docker_compose -f $ARGUS_PATH/docker-compose.gpu.intel.yml"
elif $ARGUS_GPU_AMD; then
	echo "Using AMD GPU"
	echo "NodeODM has no support for AMD GPU at the moment, falling back to CPU"
else
	echo "Using CPU"
fi

# detect if internal webodm should be used
if [ "${ARGUS_WEBODM_ADDRESS}" = "webodm" ]; then
	docker_compose="$docker_compose -f $ARGUS_PATH/docker-compose.webodm.yml"
fi

# run docker compose with provided arguments
echo "Runing command: $docker_compose $@"
$docker_compose "$@"
