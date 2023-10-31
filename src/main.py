import datetime
from project_manager import ProjectManager
from server import ArgusServer

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


def main():
    PROJECTS_PATH = './static/projects/'

    project_manager = ProjectManager(PROJECTS_PATH)
    project_manager.initiate_project_list()

    server = ArgusServer(project_manager)
    server.run()




if __name__ == '__main__':
    main()



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
