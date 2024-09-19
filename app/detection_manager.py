import json

import requests
class DetectionManager:
    def __init__(self, address, port, project_manager):
        self.address = address
        self.port = port
        self.url = 'http://' + self.address + ':' + str(self.port)
        self.project_manager = project_manager

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

    def get_detection_status(self, report_id):
        response = requests.get(self.url + '/get_processes', headers={'Accept': 'application/json'})
        all_processes = response.json()
        for process in all_processes:
            if process['report_id'] == report_id:
                if process['done']:
                    response = requests.get(self.url + '/remove_thread/' + str(report_id))
                    self.postprocess_detection_results(report_id)
                    return "finished"
                else:
                    return "running"
        return "not found"

    def postprocess_detection_results(self, report_id):
        # load detection results
        detections_path = self.project_manager.get_annotation_file_path(report_id)
        with open(detections_path, 'r') as f:
            detections = json.load(f)

            maps = self.project_manager.get_maps(report_id)
            image_coords_dict = {}
            for map in maps:
                for image in map['image_coordinates']:
                    filename = image['file_name'].split('/')[-1]
                    try:
                        image_coords_dict[filename] = image['coordinates_gps']
                    except:
                        print("No gps coordinates found for image", filename)

            # add gps corners to detections
            for image in detections['images']:
                filename = image['file_name']
                try:
                    image['coordinates_gps'] = image_coords_dict[filename]
                except:
                    print("No gps coordinates found for image", filename)

        #now go through detections{'annotations'} and add gps coordinates to each annotation based on th pixel coordinates of the gps image corners
        for annotation in detections['annotations']:
            try:
                image_id = annotation['image_id']
                image = detections['images'][image_id]
                image_coords = image['coordinates_gps']
                height, width = image['height'], image['width']
                gps_coords = self.calculate_gps_coords(image_coords, annotation['bbox'][:2], width, height)
                annotation['gps_coords'] = gps_coords

            except Exception as e:
                print("Error calculating gps coordinates for annotation", annotation['id'], e)

        #save the updated detections
        with open(detections_path, 'w') as f:
            json.dump(detections, f)



    def calculate_gps_coords(self, gps_corners, pixel_coords, image_width, image_height):
        # gps_corners = [top_left, top_right, bottom_right, bottom_left]
        # pixel_coords = [x, y]
        # cakculate a vector between the two top and the two bottom corners

        factor_x = pixel_coords[0] / image_width
        factor_y = pixel_coords[1] / image_height

        vector_top = [gps_corners[1][0] - gps_corners[0][0], gps_corners[1][1] - gps_corners[0][1]]
        vector_bottom = [gps_corners[2][0] - gps_corners[3][0], gps_corners[2][1] - gps_corners[3][1]]

        x_top = gps_corners[0][0] + factor_x * vector_top[0]
        y_top = gps_corners[0][1] + factor_x * vector_top[1]

        x_bottom = gps_corners[3][0] + factor_x * vector_bottom[0]
        y_bottom = gps_corners[3][1] + factor_x * vector_bottom[1]

        x_gps = x_top + factor_y * (x_bottom - x_top)
        y_gps = y_top + factor_y * (y_bottom - y_top)

        return [x_gps, y_gps]

