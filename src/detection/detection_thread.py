import os
import threading
import time
import json

import docker
from os import listdir
from os.path import isfile, join

#TODO
# [x] Docker Container starten und detection ausführen
# [x] Ergebnisse in json file beim project speichern
# [x] Ergebnisse passend umstrukturieren
# [x] Ergebnisse auf die Website laden
# [ ] ann.json umbenennen, sodass mehrere Detections gleichzeitig laufen könnten
# [x] Docker Container stoppen (?)
# [x] Neue Gewichte herunterladen
# [ ] Stiching der Ergebnisse -> Julien neue Klasse herunterladen
# [ ] Beim Öffnen eines reports prüfen, ob eine detection thread aktiv ist und UI dann das anpassen  + Abfrage starten
# [ ] Detection Thread nur neu starten, wenn kein thread für die ID noch existiert



class DetectionThread(threading.Thread):
    def __init__(self, report_id, image_list, ann_path, options={}):
        self.report_id = report_id
        self.image_list = image_list
        self.ann_path = ann_path
        self.options = options
        self.numbr_of_models = options.get('numbr_of_models', 1)
        self.split_images = options.get('split_images', False)
        self.done = False
        super().__init__()

    def run(self):
        print("Detection started with options: ", self.options)

        # Create a Docker client
        client = docker.from_env()

        image_name = 'object_detection_image'  # Choose a name for your image
        #Check if the image with the specified tag exists
        existing_images = client.images.list(name=image_name)

        #existing_images = False

        if not existing_images:
            print(f"Building new image with name: {image_name}")
            client.images.build(path='.', dockerfile='./detection/Dockerfile', tag=image_name)
        else:
            print(f"Using existing image: {image_name}")

        # Define the paths to the local folders you want to mount
        working_dir = os.getcwd()
        path_to_images = working_dir + '/static/uploads/' + str(self.report_id) + '/rgb'
        path_to_code = working_dir + '/detection'
        #get the current working directory dynamically
        print(working_dir)

        # Define the paths where you want to mount the folders inside the container
        container_path_to_images = '/mmdetection/data'
        container_path_to_code = '/mmdetection/code'

        # Define the command to run inside the container
        # python ./code/ir-detect.py --netfolders ./network_weights/trained_networks/rtmdet_x_8xb32-300e_coco/small_trained_correctbbx/ --inputfolder ./data/test_datasets/small_test/ --create_coco True
        # python ./code/ir-detect.py --netfolders ./code/model_weights/rtmdet_x_8xb32-300e_coco/small_trained_correctbbx/ --inputfolder ./data --create_coco True
        script_to_run = 'ir-detect.py'
        used_model = 'model_weights/rtmdet_x_8xb32-300e_coco/small_trained_correctbbx/'
        split_images = '--split_images' if self.split_images else ''
        command_to_run = f'python ./code/{script_to_run} --netfolders {container_path_to_code}/{used_model} --inputfolder {container_path_to_images} --create_coco True {split_images}'

        # Create a container with volume mounts
        # docker run --gpus all --shm-size=8g -it -v /detections/:/mmdetection/code object_detection_image
        container = client.containers.run(
            image=image_name,
            volumes=[
                path_to_images + ':' + container_path_to_images,
                path_to_code + ':' + container_path_to_code
            ],
            detach=True,
            runtime="nvidia",  # Add this line for GPU support
            shm_size='8g',  # Set the shared memory size to 8GB
            command=command_to_run
        )

        print('container started: ' + str(container.status))

        # Wait for the container to finish
        container.wait()
        container_logs = container.logs()
        print('container finished. logs: \n', container_logs.decode())

        container.stop()
        container.remove()


        # load results from json file located under /detections/results
        path_to_json = path_to_code + '/results/ann.json'
        with open(path_to_json) as json_file:
            data = json.load(json_file)
            print('found', len(data["annotations"]), 'objects')
            reformatted_data = self.reformat_data(data)
            save_path = working_dir + '/static/uploads/' + str(self.report_id)
            self.save_detections(reformatted_data, save_path)



        # To stop and remove the container when you're done

        self.done = True
        print("Detection finished")

    def reformat_data_old(self, ann):
        """
        opens the ann json file and structures it by images
        then saves as a new json file with the name suffix _structured
        """
        # open json file

        images = ann["images"]
        annotations = ann["annotations"]
        ann_by_images = {}
        for image in images:
            ann_by_images[image["id"]] = []
        for annotation in annotations:
            ann_by_images[annotation["image_id"]].append(annotation)
        ann["annotations"] = ann_by_images
        # add an etntry to each category that tells the sum of its annotations
        for category in ann["categories"]:
            category["sum"] = 0
            category["lowest_score"] = 1
            category["colorHSL"] = [(300 - int((category["id"] + 1) / len(ann["categories"]) * 360)) % 360, 100,
                                    50]
        # add an entry to each categorie that tells the sum of all its appearances in the annotations
        # also add an entry to each categorie that tells the lowest score of all its appearances in the annotations
        for image_id in ann["annotations"]:
            for annotation in ann["annotations"][image_id]:
                category_index = annotation["category_id"]
                category = ann["categories"][category_index-1]
                category["sum"] += 1
                if annotation["score"] < category["lowest_score"]:
                    category["lowest_score"] = annotation["score"]
        # add an entry to each image that tells the sum of all its annotations per category
        for image in images:
            image["sum"] = []
            for category in ann["categories"]:
                image["sum"].append(0)
            for annotation in ann["annotations"][image["id"]]:
                category_id = annotation["category_id"]
                image["sum"][category_id - 1] += 1

        return ann

    def reformat_data(self, ann):
        for category in ann["categories"]:
            category["colorHSL"] = [(300 - int((category["id"] + 1) / len(ann["categories"]) * 360)) % 360, 100, 50]
        return ann

    def save_detections(self, data, path):
        with open(path + '/detection_annotations.json', 'w') as outfile:
            json.dump(data, outfile)
