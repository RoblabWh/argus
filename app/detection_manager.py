import requests
class DetectionManager:
    def __init__(self, address, port):
        self.address = address
        self.port = port
        self.url = 'http://' + self.address + ':' + str(self.port)
        print(self.url, flush=True)


    def detect_objects(self, options, report_id, image_folder, ann_path):

        data = {'report_id': report_id,
                'models': options["numbr_of_models"],
                'max_splits': options["max_splits"],
                'image_folder': image_folder + "/rgb",
                'ann_path': ann_path
                }
        #send data to detection server
        requests.post(self.url+'/process', json=data)
        return True

    def detect_objects_slam(self, options, report_id, image_folder, ann_path):
        data = {'report_id': report_id,
                'models': options["numbr_of_models"],
                'max_splits': options["max_splits"],
                'image_folder': image_folder,
                'ann_path': ann_path
                }
        #send data to detection server
        requests.post(self.url+'/process', json=data)
        return True

    def get_detection_status(self, report_id):
        response = requests.get(self.url + '/get_processes', headers={'Accept': 'application/json'})
        all_processes = response.json()
        for process in all_processes:
            if process['report_id'] == report_id:
                if process['done']:
                    response = requests.get(self.url + '/remove_thread/' + str(report_id))
                    return "finished"
                else:
                    return "running"
        return "running"


