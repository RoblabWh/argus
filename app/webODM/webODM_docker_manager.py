import time
import docker
import subprocess

import yaml


class WebODMDockerManager:
    def __init__(self, port=8000):
        print("initializing webodm docker manager")
        self.port = port
        self.running = False


    def start_webodm_container(self):
        print("starting webodm container")

        #open ./webODM/submodule/docker-compose.yml and extend all "container_name" fields with _argus
        filedata = None

        with open('./webODM/submodule/docker-compose.yml', 'r') as file:
            filedata = yaml.safe_load(file)

        print(filedata)
        print(filedata.keys())
        keys = filedata['services'].keys()
        for key in keys:
            service = filedata['services'][key]
            if '_argus' not in service['container_name']:
                print(service['container_name'])
                if 'argus' not in service['container_name']:
                    service['container_name'] = service['container_name'] + '_argus'
                    print(service['container_name'])

        with open('./webODM/submodule/docker-compose.yml', 'w') as outfile:
            yaml.dump(filedata, outfile)




        try:
            process = subprocess.Popen(['./webODM/submodule/webodm.sh', 'start'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)

            # Optionally, you can capture and print the output if needed
            # while True:
            #     output = process.stdout.readline()
            #     if not output:
            #         break
            #     print(output.decode('utf-8').strip())
            #
            # # Optionally, you can capture and print the error output if needed
            # while True:
            #     error_output = process.stderr.readline()
            #     if not error_output:
            #         break
            #     print(error_output.decode('utf-8').strip())

        except Exception as e:
            print(f"Error starting WebODM: {e}")
        while True:
            time.sleep(20)
            if self.is_webodm_container_running():
                break
            else:
                print("waiting for webodm container to start")

    def is_webodm_container_running(self):
        print("checking if webodm container is running")
        try:
            # Initialize the Docker client
            client = docker.from_env()

            print(str([container.name for container in client.containers.list()]))

            container = client.containers.get('webapp_argus')  # Replace with the actual container name or ID
            print(container.status)
            return container.status == 'running'
        except docker.errors.NotFound:
            print("Container not found")
            return False  # Container not found, it's not running
        except Exception as e:
            print(f"Error: {e}")
            return False  # An error occurred, consider it not running