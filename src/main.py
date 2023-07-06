import datetime

from project_manager import ProjectManager
from model_weights_downloader import ModelWeightsDownloader
from server import ArgusServer
import urllib.request

def main():
    UPLOAD_FOLDER = './static/uploads/'

    #execute the python program in file model_weights_downloader.py
    # model_weights_downloader = ModelWeightsDownloader()
    # model_weights_downloader.check_model_weights()

    start = datetime.datetime.now().replace(microsecond=0)

    project_manager = ProjectManager(UPLOAD_FOLDER)
    project_manager.initiate_project_list()

    server = ArgusServer(UPLOAD_FOLDER, project_manager)
    server.run()


if __name__ == '__main__':
    main()



    #TODO Detections:
    # Detection pipeline into own Docker container

    #TODO Uploads:
    # Prohibiting uploads of multiple files with the same name
    # Giving an immediate feedback after selecting files for upload (like first loading image)
    # when opening change Settings/ reprocess only RGB images are shown

    #TODO Report:
    # after closing a report during processing, and then reopening during processing, the unfinished maps do not load
    #   (until refresh)
    # if the IR colorscheme is not monochromatic, do estimate temperature vales, at pixels with only greyscale values






