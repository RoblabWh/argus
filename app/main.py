import os
from project_manager import ProjectManager
from nodeodm_manager import NodeodmManager
from webodm_manager import WebodmManager
from detection_manager import DetectionManager
from slam_manager import SlamManager
from server import ArgusServer

def main():
    PROJECTS_PATH = './static/projects/'

    project_manager = ProjectManager(PROJECTS_PATH)
    project_manager.initiate_project_list()
    nodeodm_manager = NodeodmManager('nodeodm', 3000)
    webodm_manager = WebodmManager('webodm', 8000, os.environ['ARGUS_WEBODM_PORT'], "admin", "admin")
    token = webodm_manager.authenticate()
    if token is not None:
        webodm_manager.configure_node(token, nodeodm_manager.address, nodeodm_manager.port)
    detection_manager = DetectionManager('argus_detection', 5001, project_manager)
    slam_manager = SlamManager('argus_vslam', 7000)

    server = ArgusServer("0.0.0.0", 5000, project_manager, nodeodm_manager, webodm_manager, detection_manager, slam_manager)
    server.run()




if __name__ == '__main__':
    main()




    #TODO Uploads:
    # Giving an immediate feedback after selecting files for upload (like first loading image)

    #TODO Report:
    # after closing a report during processing, and then reopening during processing, the unfinished maps do not load
    #   (until refresh)

    #TODO Edit-Report:
    # edit not possible while processing
    # checking what has changed before reprocessing everything (or at least before recalcuating the maps)
    #TODO edit nur für geänderte inhalte

    #TODO wetterstation ort
