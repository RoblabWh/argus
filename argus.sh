#!/bin/bash
set -e

echo "
:::'###::::'########:::'######:::'##::::'##::'######::
::'## ##::: ##.... ##:'##... ##:: ##:::: ##:'##... ##:
:'##:. ##:: ##:::: ##: ##:::..::: ##:::: ##: ##:::..::
'##:::. ##: ########:: ##::'####: ##:::: ##:. ######::
 #########: ##.. ##::: ##::: ##:: ##:::: ##::..... ##:
 ##.... ##: ##::. ##:: ##::: ##:: ##:::: ##:'##::: ##:
 ##:::: ##: ##:::. ##:. ######:::. #######::. ######::
..:::::..::..:::::..:::......:::::.......::::......:::
"


#######################################
# Parse CLI args
#######################################
UPDATE_API_URL=false
UPDATE_WEBODM_URL=false
ARGS=()
for arg in "$@"; do
  case "$arg" in
    -h|--help)
      echo "Usage: ./argus.sh [OPTIONS] [docker compose args]"
      echo ""
      echo "Options:"
      echo "  --update-api-url      Rewrite VITE_API_URL in .env using the current local IP"
      echo "  --update-webodm-url   Rewrite WEBODM_URL in .env using the current local IP (port 8000)"
      echo "  --update-all-urls     Rewrite both VITE_API_URL and WEBODM_URL"
      echo "  -h, --help            Show this help message and exit"
      echo ""
      echo "Any unrecognized options are passed through to docker compose."
      echo ""
      echo "Examples:"
      echo "  ./argus.sh up -d                  Start Argus in detached mode"
      echo "  ./argus.sh --update-webodm-url up Start Argus and reset the WebODM URL to local IP"
      echo "  ./argus.sh --update-all-urls up   Reset all URLs to local IP and start"
      exit 0
      ;;
    --update-api-url)    UPDATE_API_URL=true ;;
    --update-webodm-url) UPDATE_WEBODM_URL=true ;;
    --update-all-urls)   UPDATE_API_URL=true; UPDATE_WEBODM_URL=true ;;
    *) ARGS+=("$arg") ;;
  esac
done

#######################################
# Resolve Argus path
#######################################
ARGUS_PATH="$(dirname "$(realpath "${BASH_SOURCE[0]}")")"
echo "Argus path: $ARGUS_PATH"

#######################################
# Create .env if missing
#######################################
if [ ! -f "$ARGUS_PATH/.env" ]; then
    echo "Creating .env from example..."
    cp "$ARGUS_PATH/.env.example" "$ARGUS_PATH/.env"
    echo "Edit .env before first run."
fi

#######################################
# Load .env
#######################################
set -a
source "$ARGUS_PATH/.env"
set +a

#######################################
# Detect system IP for VITE_API_URL etc.
#######################################
LOCAL_IP=$(ip route get 8.8.8.8 | awk '{for(i=1;i<=NF;i++) if ($i=="src") print $(i+1)}')
if [ -z "$LOCAL_IP" ]; then
  echo "Warning: Could not determine local IP, falling back to 127.0.0.1"
  LOCAL_IP="127.0.0.1"
fi

PORT_API=${PORT_API:-8008}
COMPUTED_VITE_API_URL="http://${LOCAL_IP}:${PORT_API}"

if [[ -z "$VITE_API_URL" ]]; then
  echo "VITE_API_URL not set, initializing to $COMPUTED_VITE_API_URL"
  sed -i "s|^VITE_API_URL=.*|VITE_API_URL=$COMPUTED_VITE_API_URL|" "$ARGUS_PATH/.env" || \
    echo "VITE_API_URL=$COMPUTED_VITE_API_URL" >> "$ARGUS_PATH/.env"
  export VITE_API_URL="$COMPUTED_VITE_API_URL"
elif [ "$UPDATE_API_URL" = true ]; then
  echo "Updating VITE_API_URL to $COMPUTED_VITE_API_URL"
  sed -i "s|^VITE_API_URL=.*|VITE_API_URL=$COMPUTED_VITE_API_URL|" "$ARGUS_PATH/.env" || \
    echo "VITE_API_URL=$COMPUTED_VITE_API_URL" >> "$ARGUS_PATH/.env"
  export VITE_API_URL="$COMPUTED_VITE_API_URL"
else
  echo "VITE_API_URL is set to $VITE_API_URL (use --update-api-url to override with local IP)"
fi

#######################################
# GPU Detection (NVIDIA only relevant)
#######################################
GPU_TYPE="cpu"
echo "Checking for NVIDIA GPU..."

HAS_NVIDIA_HARDWARE=false

set +e  
# NVIDIA Hardware detection via lspci or nvidia-smi
if command -v nvidia-smi &>/dev/null; then
    HAS_NVIDIA_HARDWARE=true
elif lspci | grep -qi 'nvidia'; then
    HAS_NVIDIA_HARDWARE=true
fi

if [ "$HAS_NVIDIA_HARDWARE" = true ]; then
    echo "NVIDIA GPU detected."

    # Check docker runtime
    if grep -q 'nvidia-container-runtime' /etc/docker/daemon.json 2>/dev/null; then
        GPU_TYPE="nvidia"
        echo "NVIDIA container runtime found → GPU mode enabled."
    else
        echo "NVIDIA GPU present but missing container runtime → using CPU mode."
    fi
else
    echo "No NVIDIA hardware detected → using CPU mode."
fi
set -e

echo "Final GPU type: $GPU_TYPE"


########################################
# WebODM startup (optional via .env)
########################################
ENABLE_WEBODM=${ENABLE_WEBODM:-false}
WEBODM_PATH=${WEBODM_PATH:-"$HOME/WebODM"}
WEBODM_IMAGE_NAME="opendronemap/webodm_webapp"
COMPUTED_WEBODM_URL="http://${LOCAL_IP}:8000"  # WebODM defaults to port 8000

# Update WEBODM_URL only if not set, or --update-webodm-url/--update-all-urls was passed
if [[ -z "$WEBODM_URL" ]]; then
  echo "WEBODM_URL not set, initializing to $COMPUTED_WEBODM_URL"
  sed -i "s|^WEBODM_URL=.*|WEBODM_URL=$COMPUTED_WEBODM_URL|" "$ARGUS_PATH/.env" || \
    echo "WEBODM_URL=$COMPUTED_WEBODM_URL" >> "$ARGUS_PATH/.env"
  export WEBODM_URL="$COMPUTED_WEBODM_URL"
elif [ "$UPDATE_WEBODM_URL" = true ]; then
  echo "Updating WEBODM_URL to $COMPUTED_WEBODM_URL"
  sed -i "s|^WEBODM_URL=.*|WEBODM_URL=$COMPUTED_WEBODM_URL|" "$ARGUS_PATH/.env" || \
    echo "WEBODM_URL=$COMPUTED_WEBODM_URL" >> "$ARGUS_PATH/.env"
  export WEBODM_URL="$COMPUTED_WEBODM_URL"
else
  echo "WEBODM_URL is set to $WEBODM_URL (use --update-webodm-url to override with local IP)"
fi
WEBODM_URL=${WEBODM_URL:-http://localhost:8000}
WEBODM_STARTED=false

cleanup() {
  echo "Caught signal, cleaning up..."

  if [ "$WEBODM_STARTED" = true ]; then
    echo "Stopping WebODM..."
    (cd "$WEBODM_PATH" && ./webodm.sh stop)
  fi

  echo "Stopping Docker Compose..."

  exit 0
}

trap cleanup SIGINT SIGTERM EXIT

# Start WebODM only if enabled and not already reachable
if [ "$ENABLE_WEBODM" = true ]; then
  echo "Checking WebODM reachability at $WEBODM_URL..."
  WEBODM_REACHABLE=false
  if curl -s --max-time 3 --head "$WEBODM_URL/login/" | grep -q "200 OK"; then
    WEBODM_REACHABLE=true
    echo "WebODM is already reachable at $WEBODM_URL, skipping startup."
  fi

  if [ "$WEBODM_REACHABLE" = false ]; then
    if [ -d "$WEBODM_PATH" ] && [ -f "$WEBODM_PATH/webodm.sh" ]; then
      echo "WebODM not reachable, starting from $WEBODM_PATH..."

      if docker ps --format '{{.Image}}' | grep -q "^${WEBODM_IMAGE_NAME}$"; then
        echo "WebODM container already running, skipping start."
      else
        (cd "$WEBODM_PATH" && ./webodm.sh start &)
        WEBODM_STARTED=true
      fi

      echo "Waiting for WebODM API at $WEBODM_URL..."
      for i in {1..10}; do
        if curl -s --head "$WEBODM_URL/login/" | grep "200 OK" > /dev/null; then
          echo "WebODM is ready!"
          break
        fi
        echo "Still waiting... ($i)"
        sleep 2
      done
    else
      echo "Warning: WebODM not reachable at $WEBODM_URL and WEBODM_PATH not found or not set."
      echo "  If WebODM is hosted remotely, ensure WEBODM_URL in .env points to the correct address."
      echo "  If WebODM is local, set WEBODM_PATH to its installation directory."
    fi
  fi
fi

#######################################
# Compose file selection
#######################################
docker_compose="docker compose -f $ARGUS_PATH/docker-compose.yml -f $ARGUS_PATH/docker-compose.linux.yml" 

case $GPU_TYPE in
    nvidia)
        docker_compose="$docker_compose -f $ARGUS_PATH/docker-compose.nvidia.yml"
        ;;
    cpu|*)
        docker_compose="$docker_compose" # -f $ARGUS_PATH/docker-compose.cpu.yml"
        ;;
esac

#######################################
# Run docker compose
#######################################
echo "Running: $docker_compose ${ARGS[@]} "
$docker_compose "${ARGS[@]}"
