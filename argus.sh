set -e

# get path to argus
ARGUS_PATH="$(dirname "$(realpath "${BASH_SOURCE[0]}")")"
echo "Argus path is $ARGUS_PATH"

if [ ! -f .env ]; then
  echo "Creating default .env file..."
  cp .env.example .env
  echo "Please edit the .env file with your real secrets."
fi


# Check for GPU etc
#  - the system will be checked to dynamically build the compose file. (not implemented yet)


# build the docker compose command based on the current system (not implemented yet)
docker_compose="docker compose -f $ARGUS_PATH/docker-compose.yml"

# run docker compose with provided arguments
echo "Runing command: $docker_compose $*"
$docker_compose "$@"
