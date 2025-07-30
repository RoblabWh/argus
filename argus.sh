set -e

# get path to argus
ARGUS_PATH="$(dirname "$(realpath "${BASH_SOURCE[0]}")")"
echo "Argus path is $ARGUS_PATH"


# Parse arguments
FORCE_UPDATE_IP=false
ARGS=()

for arg in "$@"; do
  if [ "$arg" == "--refresh-ip" ]; then
    FORCE_UPDATE_IP=true
  else
    ARGS+=("$arg")
  fi
done


# Get local IP address (used for VITE_API_URL (by pinging google))
LOCAL_IP=$(ip route get 8.8.8.8 | awk '{for(i=1;i<=NF;i++) if ($i=="src") print $(i+1)}')
if [ -z "$LOCAL_IP" ]; then
  echo "Warning: Could not determine local IP, falling back to 127.0.0.1"
  LOCAL_IP="127.0.0.1"
fi
VITE_API_URL="http://${LOCAL_IP}:8000"


if [ ! -f .env ]; then
  echo "Creating default .env file..."
  cp .env.example .env
  echo "Please edit the .env file with your real secrets."
fi

# Check and possibly update VITE_API_URL
if grep -q '^VITE_API_URL=' "$ARGUS_PATH/.env"; then
  if [ "$FORCE_UPDATE_IP" = true ]; then
    echo "Updating VITE_API_URL to $VITE_API_URL"
    sed -i "s|^VITE_API_URL=.*|VITE_API_URL=$VITE_API_URL|" "$ARGUS_PATH/.env"
  else
    echo "VITE_API_URL already set. Use --refresh-ip to update it."
  fi
else
  echo "Setting VITE_API_URL to $VITE_API_URL"
  echo "VITE_API_URL=$VITE_API_URL" >> "$ARGUS_PATH/.env"
fi


# Check for GPU etc
#  - the system will be checked to dynamically build the compose file. (not implemented yet)


# build the docker compose command based on the current system (not implemented yet)
docker_compose="docker compose -f $ARGUS_PATH/docker-compose.yml"

# run docker compose with provided arguments
echo "Runing command: $docker_compose $*"
$docker_compose "${ARGS[@]}"
