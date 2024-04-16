import os
from project_manager import ProjectManager
from nodeodm_manager import NodeodmManager
from webodm_manager import WebodmManager
from detection_manager import DetectionManager
from server import ArgusServer

def main():
    PROJECTS_PATH = './static/projects/'

    project_manager = ProjectManager(PROJECTS_PATH)
    project_manager.initiate_project_list()
    nodeodm_manager = NodeodmManager('nodeodm', 3000)
    webodm_external_port = os.environ['ARGUS_WEBODM_PORT']
    if 'ARGUS_WEBODM_INTERNAL' in os.environ:
        webodm_internal_port = 8000
    else:
        webodm_internal_port = webodm_external_port
    webodm_manager = WebodmManager(os.environ['ARGUS_WEBODM_ADDRESS'], webodm_internal_port, webodm_external_port, os.environ['ARGUS_WEBODM_USERNAME'], os.environ['ARGUS_WEBODM_PASSWORD'])
    token = webodm_manager.authenticate()
    if token is not None:
        webodm_manager.configure_node(token, nodeodm_manager.address, nodeodm_manager.port)
    detection_manager = DetectionManager('argus_detection', 6000)

    server = ArgusServer("0.0.0.0", 5000, project_manager, nodeodm_manager, webodm_manager, detection_manager)
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
