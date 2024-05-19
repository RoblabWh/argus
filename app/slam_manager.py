import requests
import os

class SlamManager:

    def __init__(self, address, port):
        self.address = address
        self.port = port
        self.url = 'http://' + self.address + ':' + str(self.port)
        print(self.url, flush=True)

    def start_slam(self, report_id, video, config, orb_vocab, slam_options, keyfrm_path, landmark_path, keyfrm_folder_path, slam_output_path):
        data = {'report_id': report_id,
                'video': video[0],
                'orb_vocab': orb_vocab[0],
                'config': config[0],
                'slam_options': slam_options,
                'keyfrm_path': keyfrm_path,
                'landmark_path': landmark_path,
                'keyfrm_folder_path': keyfrm_folder_path,
                'slam_output_path': slam_output_path} #maybe add an output thing for keyframes

        requests.post(self.url+'/slam', json=data)
        return True

    def get_slam_status(self, report_id):
        response = requests.get(self.url+'/get_slam_status', headers={'Accept': 'application/json'})
        all_processes = response.json()
        for process in all_processes:
            if process['report_id'] == report_id:
                if process['done']:
                    response = requests.get(self.url + '/remove_thread/' + str(report_id))
                    print("delete thread:", response, flush=True)
                    return "finished"
                else:
                    return "running"
        return "running"

    def get_slam_map(self, report_id):
        response = requests.get(self.url+'/get_slam_maps', headers={'Accept': 'application/json'})
        all_maps = response.json()
        for map in all_maps:
            if map['report_id'] == report_id:
                print(map['data'])
                return "map found"

        return "map not found"