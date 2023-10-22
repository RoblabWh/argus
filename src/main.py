import datetime
import sys
from project_manager import ProjectManager
from model_weights_downloader import ModelWeightsDownloader
from server import ArgusServer
import os
import docker
import urllib.request

# def start_detection_container():
#     client = docker.from_env()
#
#     # Define the image tag
#     image_tag = "object_detection_image"
#
#     # Check if the image with the specified tag exists
#     existing_images = client.images.list(name=image_tag)
#     existing_images = False
#
#     if not existing_images:
#         # The image does not exist, so build it
#         dockerfile_path = "./detection/Dockerfile"
#         context_path = "./"
#         image, build_logs = client.images.build(path=context_path, dockerfile=dockerfile_path, tag=image_tag)
#     else:
#         print(f"Using existing image: {image_tag}")
#
#     # Start the Docker container
#     container = client.containers.run(
#         image=image_tag,
#         detach=True,
#         ports={"5005/tcp": 5005},
#     )




    # # Wait for the container to finish (if needed)
    # container.wait()
    #
    # # Stop and remove the container when done (if needed)
    # container.stop()
    # container.remove()


def main(system_code_path):
    UPLOAD_FOLDER = './static/uploads/'

    #execute the python program in file model_weights_downloader.py
    model_weights_downloader = ModelWeightsDownloader()
    model_weights_downloader.check_model_weights()

    #start_detection_container()

    start = datetime.datetime.now().replace(microsecond=0)

    project_manager = ProjectManager(UPLOAD_FOLDER)
    project_manager.initiate_project_list()

    server = ArgusServer(UPLOAD_FOLDER, project_manager, system_code_path)
    server.run()




if __name__ == '__main__':
    DOCKER_ENV_KEY = os.environ.get('AM_I_IN_A_DOCKER_CONTAINER', False)
    if DOCKER_ENV_KEY:
        system_code_path = sys.argv[1] + '/src'
        print('running insinde docker container, system_code_path is:', system_code_path)
    else:
        system_code_path = os.getcwd()
        print('running outside docker container, system_code_path is:', system_code_path)
    main(system_code_path)



    #TODO Detections:
    # Detection pipeline into own Docker container

    #TODO Uploads:
    # Giving an immediate feedback after selecting files for upload (like first loading image)

    #TODO Report:
    # after closing a report during processing, and then reopening during processing, the unfinished maps do not load
    #   (until refresh)
    # if the IR colorscheme is not monochromatic, do estimate temperature vales, at pixels with only greyscale values

    #TODO Edit-Report:
    # if the report gets edited but not reprocessed (maybe by going back one page), a waring asks for reprocessing
    # edit not possible while processing
    # checking what has changed before reprocessing everything (or at least before recalcuating the maps)
    #TODO edit nur für geänderte inhalte

    #TODO wetterstation ort






