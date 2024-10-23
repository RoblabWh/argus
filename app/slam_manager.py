import requests
import os

class SlamManager:

    def __init__(self, address, port):
        self.address = address
        self.port = port
        self.url = 'http://' + self.address + ':' + str(self.port)
        print(self.url, flush=True)

    def start_slam(self, report_id, video, config, mask, orb_vocab, slam_options, other_options,keyfrm_path, landmark_path, keyfrm_folder_path, map_db_output, slam_output_path):
        try:
            mask_file = mask[0]
        except:
            mask_file = None
        data = {'report_id': report_id,
                'video': video[0],
                'orb_vocab': orb_vocab[0],
                'config': config[0],
                'mask': mask_file,
                'slam_options': slam_options,
                'other_options': other_options,
                'keyfrm_path': keyfrm_path,
                'landmark_path': landmark_path,
                'keyfrm_folder_path': keyfrm_folder_path,
                'map_db_output': map_db_output,
                'slam_output_path': slam_output_path} #maybe add an output thing for keyframes
        requests.post(self.url+'/slam', json=data)
        return True

    def start_stitcher(self, report_id, input_videos, output_video, stitcher_calibration):
        data = {'report_id': report_id,
                'input_videos': input_videos,
                'output_video': output_video,
                'stitcher_calibration': stitcher_calibration}
        requests.post(self.url+'/stitcher', json=data)
        return True

    def get_slam_status(self, report_id):
        response = requests.get(self.url+'/get_slam_status', headers={'Accept': 'application/json'})
        all_processes = response.json()
        for process in all_processes:
            if process['report_id'] == report_id:
                if process['done']:
                    response = requests.get(self.url + '/remove_thread/' + str(report_id))
                    print("delete thread:", response, flush=True)
                    return ("finished", "progress", process['progress'])
                else:
                    if process['update']:
                        return ("update","progress", process['progress'])
                    else:
                        return ("running","progress", process['progress'])
        return "not found"

    def get_stitcher_status(self, report_id):
        response = requests.get(self.url+'/get_stitcher_status', headers={'Accept': 'application/json'})
        all_processes = response.json()
        for process in all_processes:
            if process['report_id'] == report_id:
                if process['done']:
                    response = requests.get(self.url + '/remove_thread/' + str(report_id))
                    print("delete thread:", response, flush=True)
                    return ("finished", "progress", process['progress'])
                else:
                    if process['update']:
                        return ("update", "progress", process['progress'])
                    else:
                        return ("running", "progress", process['progress'])
        return "running"

    def get_slam_map(self, report_id):
        response = requests.get(self.url+'/get_slam_maps', headers={'Accept': 'application/json'})
        all_maps = response.json()
        for map in all_maps:
            if map['report_id'] == report_id:
                print(map['data'])
                return "map found"

        return "map not found"