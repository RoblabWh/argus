import time
import docker
import subprocess

class WebODMDockerManager:
    def __init__(self, port=8000):
        print("initializing webodm docker manager")
        self.port = port
        self.running = False


    def start_webodm_container(self):
        print("starting webodm container")
        # Define the command to start the WebODM container in detached mode
        docker_command = [
            'docker',
            'run',
            '-d',  # Run in detached mode (in the background)
            '-p', f'{self.port}:8000',  # Map port 8000 inside the container to port 8000 on the host
            # '-v', '/path/to/your/input/images:/datasets:ro',  # Mount input images directory
            # '-v', '/path/to/your/output/directory:/var/www/data:rw',  # Mount output directory
            'opendronemap/webodm_webapp',  # WebODM Docker image name
        ]

        # Start the WebODM container in the background
        subprocess.Popen(docker_command)
        time.sleep(15)

    def is_webodm_container_running(self):
        print("checking if webodm container is running")
        try:
            # Initialize the Docker client
            client = docker.from_env()

            # Check if the WebODM container is running
            container = client.containers.get('opendronemap/webodm_webapp ')  # Replace with the actual container name or ID
            print(container.status)
            return container.status == 'running'
        except docker.errors.NotFound:
            print("Container not found")
            return False  # Container not found, it's not running
        except Exception as e:
            print(f"Error: {e}")
            return False  # An error occurred, consider it not running