import requests
import os
import cv2
from multiprocessing import Pool

class SlamManager:

    def __init__(self, address, port):
        self.address = address
        self.port = port
        self.url = 'http://' + self.address + ':' + str(self.port)
        print(self.url, flush=True)

    #static function for multiprocessing with pool that scales down an image and saves it with the same name, but within a subdirectoy called thumbnails
    @staticmethod
    def create_thumbnail(image_path):
        image = cv2.imread(image_path)
        image = cv2.resize(image, (0,0), fx=0.5, fy=0.5, interpolation=cv2.INTER_LINEAR)
        image_dir = os.path.dirname(image_path)
        image_name = os.path.basename(image_path)
        new_image_path = os.path.join(image_dir, 'thumbnails', image_name)
        cv2.imwrite(new_image_path, image)
        return True

    #function that creates thumbnails for all keyframes in a keyframe folder
    def create_thumbnails(self, keyframe_folder):
        keyframes = os.listdir(keyframe_folder)

        thumbnails_folder = os.path.join(keyframe_folder, 'thumbnails')
        if not os.path.exists(thumbnails_folder):
            os.makedirs(thumbnails_folder)

        keyframe_paths = [os.path.join(keyframe_folder, keyframe) for keyframe in keyframes]
        pool = Pool()
        pool.map(SlamManager.create_thumbnail, keyframe_paths)
        return True

    def flip_video(self, video_path):
        flipped_video_path = os.path.join(os.path.dirname(video_path), 'flipped_' + os.path.basename(video_path))
        #use "ffmpeg -i input.mp4 -metadata:s:v rotate=180 -codec copy output.mp4" to flip video
        os.system('ffmpeg -i ' + video_path + ' -metadata:s:v rotate=180 -codec copy ' + flipped_video_path)

        os.remove(video_path)
        print("flipped video_path", flipped_video_path, flush=True)
        print("video_path", video_path, flush=True)
        os.rename(flipped_video_path, video_path)


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