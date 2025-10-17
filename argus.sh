#!/bin/bash
set -e

# Get path to Argus (your app)
ARGUS_PATH="$(dirname "$(realpath "${BASH_SOURCE[0]}")")"
echo "Argus path is $ARGUS_PATH"

# Parse CLI arguments
FORCE_UPDATE_IP=true
ARGS=()

for arg in "$@"; do
  if [ "$arg" == "--keep-ip" ]; then
    FORCE_UPDATE_IP=false
  else
    ARGS+=("$arg")
  fi
done

# Create .env from example if missing
if [ ! -f "$ARGUS_PATH/.env" ]; then
  echo "Creating default .env file..."
  cp "$ARGUS_PATH/.env.example" "$ARGUS_PATH/.env"
  echo "Please edit the .env file with your real secrets."
fi

# Load environment variables into shell session
set -a
source "$ARGUS_PATH/.env"
set +a

# Determine local IP address
LOCAL_IP=$(ip route get 8.8.8.8 | awk '{for(i=1;i<=NF;i++) if ($i=="src") print $(i+1)}')
if [ -z "$LOCAL_IP" ]; then
  echo "Warning: Could not determine local IP, falling back to 127.0.0.1"
  LOCAL_IP="127.0.0.1"
fi

# Set default if not already defined in .env
PORT_API=${PORT_API:-8008}

# Dynamically compute new API_URLs
COMPUTED_VITE_API_URL="http://${LOCAL_IP}:${PORT_API}"

# Update or set VITE_API_URL
if [[ -z "$VITE_API_URL" || "$FORCE_UPDATE_IP" == true ]]; then
  echo "Setting or updating VITE_API_URL to $COMPUTED_VITE_API_URL"
  sed -i "s|^VITE_API_URL=.*|VITE_API_URL=$COMPUTED_VITE_API_URL|" "$ARGUS_PATH/.env" || \
    echo "VITE_API_URL=$COMPUTED_VITE_API_URL" >> "$ARGUS_PATH/.env"
  export VITE_API_URL="$COMPUTED_VITE_API_URL"
else
  echo "VITE_API_URL is already set to $VITE_API_URL. Use --refresh-ip to update it."
fi


########################################
# WebODM startup (optional via .env)
########################################

ENABLE_WEBODM=${ENABLE_WEBODM:-false}
WEBODM_PATH=${WEBODM_PATH:-"$HOME/WebODM"}
WEBODM_IMAGE_NAME="opendronemap/webodm_webapp"
COMPUTED_WEBODM_URL="http://${LOCAL_IP}:8000"  # WebODM defaults to port 8000

# Update or set WEBODM_URL
if [[ -z "$WEBODM_URL" || "$FORCE_UPDATE_IP" == true ]]; then
  echo "Setting or updating WEBODM_URL to $COMPUTED_WEBODM_URL"
  sed -i "s|^WEBODM_URL=.*|WEBODM_URL=$COMPUTED_WEBODM_URL|" "$ARGUS_PATH/.env" || \
    echo "WEBODM_URL=$COMPUTED_WEBODM_URL" >> "$ARGUS_PATH/.env"
  export WEBODM_URL="$COMPUTED_WEBODM_URL"
else
  echo "WEBODM_URL is already set to $WEBODM_URL. Use --refresh-ip to update it."
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

# Start WebODM in background and keep track of PID
if [ "$ENABLE_WEBODM" = true ]; then
  if [ -d "$WEBODM_PATH" ] && [ -f "$WEBODM_PATH/webodm.sh" ]; then
    echo "Starting WebODM..."
    
    if docker ps --format '{{.Image}}' | grep -q "^${WEBODM_IMAGE_NAME}$"; then
      echo "WebODM container running from image '$WEBODM_IMAGE_NAME' is already running."
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
  fi
fi

# Start your main app (blocks until exited)
docker_compose="docker compose -f $ARGUS_PATH/docker-compose.yml"
echo "Running: $docker_compose ${ARGS[*]}"
$docker_compose "${ARGS[@]}"