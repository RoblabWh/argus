import hashlib
import os
import json
import time
import shutil
import uuid
import zipfile
from datetime import datetime


class ProjectManager:
    def __init__(self, projects_path):
        self.projects = []
        self.project_groups = []
        self.projects_image_objects = {}
        self.highest_id = -1
        self.current_project_id = None
        if not os.path.exists(projects_path):
            os.makedirs(projects_path)
        self.projects_path = projects_path
        self.CURRENT_PROJECT_FILE_VERSION = 1.1
        self.projects_dirs = ["rgb", "ir", "panos", "rgb/thumbnails" , "ir/thumbnails", "panos/thumbnails"]
        self.project_group_file = os.path.join(self.projects_path, "project_groups.json")
        # self.update_project_groups_file()
        #self.image_mapper = {}


    def create_project(self, name, description):
        #id = self.get_next_id()
        id = self.create_new_basics()
        data = self.generate_empty_data_dict()
        version = self.CURRENT_PROJECT_FILE_VERSION
        creation_time = datetime.now().strftime("%d.%m.%Y %H:%M:%S")
        project = ({'name': name, 'description': description, 'id': id, 'creation_time': creation_time,
                    'version': version, 'data': data})
        self.projects.append(project)
        with open(os.path.join(self.projects_path, str(id), "project.json"), "w") as json_file:
            json.dump(project, json_file)

        #make subdirectories for project as dtermined in varable "project_dirs"
        for dir in self.projects_dirs:
            os.makedirs(os.path.join(self.projects_path, str(id), dir))

        self.highest_id += 1
        self.projects = sorted(self.projects, key=lambda d: d['id'], reverse=True)
        return project

    def create_new_basics(self):
        id = self.generate_project_id()
        print("creating project with id: " + str(id))
        os.mkdir(os.path.join(self.projects_path, str(id)))
        return id

    def initialize_project_from_import(self):
        return self.create_new_basics()

    def contains_project_json(self, id, zip_path):
        # unpack zip into same directory
        print("zip_path: " + zip_path, flush=True)
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(self.projects_path + str(id))

        all_files = os.listdir(self.projects_path + str(id))
        print("unpacked files: " + str(all_files), flush=True)

        for file in os.listdir(os.path.join(self.projects_path, str(id))):
            print("file: " + file, flush=True)
            if file == "project.json":
                return True

        shutil.rmtree(os.path.join(self.projects_path, str(id)), ignore_errors=True)
        return False

    def import_project(self, project_id):
        try:
            print("loading project.json with id: " + str(project_id), flush=True)

            project = self.load_project_from_directory(str(project_id))
            print("imported_id " + str(project['id']), flush=True)
            project = self.changeID(project, project_id)
            print("changed_id " + str(project['id']), flush=True)
            self.projects.append(project)
            self.projects = sorted(self.projects, key=lambda d: d['id'], reverse=True)

            with open(os.path.join(self.projects_path, str(project_id), "project.json"), "w") as json_file:
                json.dump(project, json_file)

        except:
            if not self.delete_project(project_id):
                shutil.rmtree(os.path.join(self.projects_path, str(project_id)), ignore_errors=True)
            raise Exception("error while importing project.json - report_id: " + str(project_id))

    def changeID(self, project, new_id):
        #print("changing id from " + str(project['id']) + " to " + str(new_id), flush=True)
        old_id = project['id']
        project['id'] = new_id
        data = project['data']
        for path in data['file_names']:
            path = path.replace(str(old_id), str(new_id), 1)
        #print('changed filenames paths', flush=True)

        # check if 'file_names_ir' exists
        if 'file_names_ir' in data:
            for path in data['file_names_ir']:
                path = path.replace(str(old_id), str(new_id), 1)
        #print('changed filenames_ir paths', flush=True)

        if 'panos' in data:
            for pano in data['panos']:
                pano['file'] = pano['file'].replace(str(old_id), str(new_id), 1)
        #print('changed panos paths', flush=True)

        if 'maps' in data:
            for map in data['maps']:

                file = map['file'].replace(str(old_id), str(new_id), 1)
                map['file'] = file

                file_url = map['file_url'].replace(str(old_id), str(new_id), 1)
                map['file_url'] = file_url

                if map['image_coordinates'] is not None:
                    for image_coordinate in map['image_coordinates']:
                        coordinate = image_coordinate['file_name'].replace(str(old_id), str(new_id), 1)
                        image_coordinate['file_name'] = coordinate
        #print('changed maps paths', flush=True)

        for slides in data['slide_file_paths']:
            for i in range(len(slides)):
                slides[i] = slides[i].replace(str(old_id), str(new_id), 1)
        #print('changed slide_file_paths paths', flush=True)

        if 'annotation_file_path' in data:
            data['annotation_file_path'] = data['annotation_file_path'].replace(str(old_id), str(new_id), 1)
        #print('changed annotation_file_path paths', flush=True)
        return project

    # def replace_project_id_in_path(self, path, new_id):
    #     parts = path.split(os.path.sep)
    #     # Find the index of 'projects' in the path
    #     try:
    #         projects_index = parts.index('projects')
    #     except ValueError:
    #         return path
    #
    #     parts[projects_index + 1] = new_id
    #     new_path = os.path.join(*parts)
    #
    #     return new_path

    def load_project_from_directory(self, project_id):
        # load project.json from static/uploads/id
        # if no project.json exists, return None
        project = None
        if os.path.isfile(os.path.join(self.projects_path, project_id, "project.json")):
            print("loading project from directory: " + project_id)
            with open(os.path.join(self.projects_path, project_id, "project.json"), "r") as json_file:
                project = json.load(json_file)
                self._check_for_annotations(project)


        # check if there is a project['version'] and if not, add it with self.CURRENT_PROJECT_FILE_VERSION
        try:
            version = project['version']
        except:
            project['version'] = self.CURRENT_PROJECT_FILE_VERSION

        return project

    def _check_for_annotations(self, project):
        if not project:
            return
        if not 'data' in project:
            return

        if not 'annotation_file_path' in project['data']:
            return

        annotation_file_path = project['data']['annotation_file_path']
        #load annotations
        if not os.path.isfile(annotation_file_path):
            return
        with open(annotation_file_path, 'r') as json_file:
            annotations = json.load(json_file)
            if not 'version' in annotations:
                annotations = self._update_annotations_to_v1(annotations)
                annotations['version'] = 1.0
                with open(annotation_file_path, 'w') as json_file:
                    json.dump(annotations, json_file)


    def _update_annotations_to_v1(self, annotations):
        # if no version Tag is available it is assumed, that the file is originally from the old mm_detection pipeline
        # therfore the "category_id" in the detections list needs to be corrected by adding 1
        for detection in annotations['annotations']:
            detection['category_id'] += 1

        return annotations



    def initiate_project_list(self):
        # check for every directory in static/projects/ if there is project.json
        # if yes, load project and add to project list
        for project_id in os.listdir(self.projects_path):
            try:
                if os.path.isdir(os.path.join(self.projects_path, project_id)):
                    project = self.load_project_from_directory(project_id)
                    if project != None:
                        self.projects.append(project)
                        # if project['id'] > self.highest_id:
                        #     self.highest_id = project['id']
            except:
                print("error while loading project with id: " + str(project_id), flush=True)

        if os.path.isfile(self.project_group_file):
            with open(self.project_group_file, "r") as json_file:
                self.project_groups = json.load(json_file)

        self.projects = sorted(self.projects, key=lambda d: d['id'], reverse=True)

    def get_project(self, id):
        for project in self.projects:
            #print("project id: " + str(project['id']), "id: " + str(id), flush=True)
            if project['id'] == id:
                return project
        return None

    def project_path(self, project_id):
        return str(os.path.join(self.projects_path, str(project_id)))

    def get_projects(self):
        if self.projects == []:
            self.initiate_project_list()
        return self.projects

    def get_projects_basic_data(self):
        projects = self.get_projects()
        basic_data = []
        for project in projects:
            basic_data.append({
                'id': project['id'],
                'name': project['name'],
                'description': project['description'],
                'creation_time': project['creation_time']})
        return basic_data

    def set_current_project(self, id):
        self.current_project_id = id

    def get_current_project(self):
        return self.get_project(self.current_project_id)

    def get_current_project_id(self):
        return self.current_project_id

    def get_next_id(self):
        return self.highest_id + 1

    def generate_project_id(self):
        #generate int id with date,time hhmmss and a 4 digit hash based on the systems name

        timestamp = datetime.now().strftime("%y%m%d%H%M%S")

        #get system name
        system_name = os.uname().nodename
        print("system name: " + system_name)

        #generate int hash
        hash = int(hashlib.sha256(system_name.encode('utf-8')).hexdigest(), 16) % 10**4
        print("hash: " + str(hash))

        while True:
            if len(str(hash)) == 4:
                break
            else:
                if len(str(hash)) < 4:
                    hash = hash * 10
                else:
                    hash = int(str(hash)[:-1])

        #cast to string and concatenate
        project_id = int(timestamp + str(hash))
        #cast to int
        project_id = int(project_id)

        print("generated project id: " + str(project_id))

        return project_id

    def load_data(self, id):
        project = self.get_project(id)
        data = project['data']
        if data == {}:
            data = self.generate_empty_data_dict()
        return data

    def has_project(self, id):
        project = self.get_project(id)
        if project != None:
            return True
        return False

    def generate_empty_data_dict(self):
        data = {"file_names": [], "file_names_ir" : [], "panos": [], "flight_data": [], "camera_specs": [], "weather": [], "maps": [], "ir_settings": {}}
        return data

    def update_file_names(self, id, file_names):
        # append filenames to filenames inside of data of project with id
        project = self.get_project(id)
        data = project['data']
        data['file_names'] += file_names
        with open(os.path.join(self.projects_path, str(id), "project.json"), "w") as json_file:
            json.dump(project, json_file)

        return data['file_names']

    def update_single_file_path(self, id, old_path, new_path):
        project = self.get_project(id)
        data = project['data']
        file_names = data['file_names']
        try:
            file_names[file_names.index(old_path)] = new_path
            print("replaced path: " + old_path + " with new path: " + new_path, flush=True)
        except:
            print("file " + old_path + " not found in file_names list", flush=True)


        with open(self.projects_path + str(id) + "/project.json", "w") as json_file:
            json.dump(project, json_file)

        return data['file_names']

    def append_unprocessed_images(self, id, file_names):
        project = self.get_project(id)
        data = project['data']

        try:
            couples = data['slide_file_paths']
        except:
            couples = []

        for file_name in file_names:
            couples.append(["", "", file_name])

        data['slide_file_paths'] = couples
        data['contains_unprocessed_images'] = True
        print("appending unprocessed images to project with id: " + str(id))
        with open(self.projects_path + str(id) + "/project.json", "w") as json_file:
            json.dump(project, json_file)

        return data['slide_file_paths']

    def overwrite_file_names_sorted(self, id, file_names_rgb=None, file_names_ir=None):
        project = self.get_project(id)
        data = project['data']
        if file_names_rgb != None:
            data['file_names'] = file_names_rgb
        if file_names_ir != None:
            data['file_names_ir'] = file_names_ir
        #print("len of file_names: " + str(len(data['file_names'])), "len of file_names_ir: " + str(len(data['file_names_ir'])))
        with open(self.projects_path + str(id) + "/project.json", "w") as json_file:
            json.dump(project, json_file)

        return data['file_names']

    def update_description(self, id, description):
        project = self.get_project(id)
        project['description'] = description
        with open(self.projects_path + str(id) + "/project.json", "w") as json_file:
            json.dump(project, json_file)
        return project['description']

    def update_title_name(self, id, title_name):
        project = self.get_project(id)
        project['name'] = title_name
        with open(self.projects_path + str(id) + "/project.json", "w") as json_file:
            json.dump(project, json_file)
        return project['name']

    def update_flight_data(self, id, flight_data):
        return self.update_data_by_keyword(id, 'flight_data', flight_data)

    def update_camera_specs(self, id, camera_specs):
        return self.update_data_by_keyword(id, 'camera_specs', camera_specs)

    def update_weather(self, id, weather):
        return self.update_data_by_keyword(id, 'weather', weather)

    def update_maps(self, id, maps):
        return self.update_data_by_keyword(id, 'maps', maps)

    def update_flight_trajectory(self, id, flight_trajectory):
        return self.update_data_by_keyword(id, 'flight_trajectory', flight_trajectory)

    def update_ir_settings(self, id, ir_settings):
        return self.update_data_by_keyword(id, 'ir_settings', ir_settings)

    def update_panos(self, id, panos):
        return self.update_data_by_keyword(id, 'panos', panos)

    def add_panos(self, id, panos):
        panos = self.get_panos(id) + panos
        self.update_data_by_keyword(id, 'panos', panos)

    def remove_from_panos(self, id, pano_file):
        panos = self.get_panos(id)
        for p in panos:
            if pano_file in p['file']:
                panos.remove(p)
                self.update_data_by_keyword(id, 'panos', panos)
                return True

    def update_data_by_keyword(self, id, keyword, data):
        project = self.get_project(id)
        project['data'][keyword] = data
        with open(os.path.join(self.projects_path, str(id), "project.json"), "w") as json_file:
            json.dump(project, json_file)
        return project['data'][keyword]

    def delete_project(self, id):
        project = self.get_project(id)
        group_id = self.get_project_group_by_project_id(id)
        if group_id != None:
            self.remove_project_from_group(group_id, id)
        if project != None:
            print("deleted project with id: " + str(id) + " and path: " + os.path.join(self.projects_path, str(id)), flush=True)
            self.projects.remove(project)
            shutil.rmtree(os.path.join(self.projects_path, str(id)), ignore_errors=True)
            #os.rmdir(self.projects_path + str(id))
            return True
        return False

    def get_file_names(self, id):
        return self.get_data_by_keyword(id, 'file_names') + self.get_data_by_keyword(id, 'file_names_ir') + self.get_file_names_panos(id)

    def get_file_names_rgb(self, id):
        return self.get_data_by_keyword(id, 'file_names')

    def get_file_names_ir(self, id):
        return self.get_data_by_keyword(id, 'file_names_ir')

    def get_panos(self, id):
        return self.get_data_by_keyword(id, 'panos')

    def get_file_names_panos(self, id):
        panos = self.get_panos(id)
        panos_paths = []
        for pano in panos:
            panos_paths.append(pano['file'])
        return panos_paths

    def get_flight_data(self, id):
        return self.get_data_by_keyword(id, 'flight_data')

    def get_camera_specs(self, id):
        return self.get_data_by_keyword(id, 'camera_specs')

    def get_weather(self, id):
        return self.get_data_by_keyword(id, 'weather')

    def get_maps(self, id):
        return self.get_data_by_keyword(id, 'maps')

    def get_flight_trajectory(self, id):
        return self.get_data_by_keyword(id, 'flight_trajectory')

    def get_data_by_keyword(self, id, keyword):
        project = self.get_project(id)
        data = project['data']
        return data[keyword]

    def get_project_name(self, report_id):
        project = self.get_project(report_id)
        return project['name']

    def get_project_description(self, report_id):
        project = self.get_project(report_id)
        return project['description']

    def get_project_creation_time(self, report_id):
        project = self.get_project(report_id)
        try:
            return project['creation_time']
        except:
            return "no creation time found"

    def get_ir_settings(self, report_id):
        project = self.get_project(report_id)
        return project['data']['ir_settings']

    def get_webodm_project_id(self, report_id):
        try:
            project = self.get_project(report_id)
            return project['data']['webodm_project_id']
        except:
            return None

    def set_webodm_project_id(self, report_id, webodm_project_id):
        self.update_data_by_keyword(report_id, 'webodm_project_id', webodm_project_id)

    def update_ir_settings_from_website(self, report_id, settings):
        project = self.get_project(report_id)
        ir_settings = project['data']['ir_settings']

        ir_settings['ir_min_temp'] = settings[0]
        ir_settings['ir_max_temp'] = settings[1]
        ir_settings['ir_color_scheme'] = settings[2]

        self.update_ir_settings(report_id, ir_settings)

    def get_annotation_file_path(self, report_id):
        project = self.get_project(report_id)
        path = ""
        try:
            path = project['data']['annotation_file_path']
        except:
            path = self.generate_new_annotation_file_path(report_id)

        return path

    def generate_new_annotation_file_path(self, report_id):
        project = self.get_project(report_id)
        path = self.projects_path + str(report_id) + "/detection_annotations.json"
        project['data']['annotation_file_path'] = path
        self.update_data_by_keyword(report_id, 'annotation_file_path', path)
        return path

    def update_slide_file_paths(self, report_id, slide_file_paths):
        self.update_data_by_keyword(report_id, 'slide_file_paths', slide_file_paths)

    def update_detections_colors(self, report_id, color, category_name):
        project = self.get_project(report_id)
        path = project['data']['annotation_file_path']

        with open(path, "r") as json_file:
            detections = json.load(json_file)
            categories = detections['categories']

            for i in range(len(categories)):
                if(categories[i]['name'] == category_name):
                    categories[i]['colorHSL'] = [float(color[0]), float(color[1]), float(color[2])]

            detections['categories'] = categories

        with open(path, "w") as json_file:
            json.dump(detections, json_file)

    def delete_annotation(self, report_id, annotation_id):
        project = self.get_project(report_id)
        annotation_id = int(annotation_id)
        path = project['data']['annotation_file_path']

        with open(path, "r") as json_file:
            print("loading detections", flush=True)
            detections = json.load(json_file)
            annotations = detections['annotations']

            print(len(annotations), flush=True)

            for i in range(len(annotations)):
                if(annotations[i]['id'] == annotation_id):
                    print("deleting annotation with id: " + str(annotation_id) + " from list with length " + str(len(annotations)), flush=True)
                    annotations.pop(i)
                    print("new length: " + str(len(annotations)), flush=True)
                    break

            detections['annotations'] = annotations

        with open(path, "w") as json_file:
            json.dump(detections, json_file)

    def edit_annotation(self, report_id, annotation_id, new_category_id, new_bbox):
        project = self.get_project(report_id)
        annotation_id = int(annotation_id)
        new_category_id = int(new_category_id)
        path = project['data']['annotation_file_path']

        with open(path, "r") as json_file:
            detections = json.load(json_file)
            annotations = detections['annotations']

            for i in range(len(annotations)):
                if(annotations[i]['id'] == annotation_id):
                    annotations[i]['category_id'] = new_category_id
                    annotations[i]['bbox'] = new_bbox
                    break

            detections['annotations'] = annotations

        with open(path, "w") as json_file:
            json.dump(detections, json_file)

    def edit_annotation_category(self, report_id, annotation_id, new_category_id):
        project = self.get_project(report_id)
        annotation_id = int(annotation_id)
        new_category_id = int(new_category_id)
        path = project['data']['annotation_file_path']

        with open(path, "r") as json_file:
            detections = json.load(json_file)
            annotations = detections['annotations']

            for i in range(len(annotations)):
                if(annotations[i]['id'] == annotation_id):
                    annotations[i]['category_id'] = new_category_id
                    annotations[i]['manual'] = True
                    break

            detections['annotations'] = annotations

        with open(path, "w") as json_file:
            json.dump(detections, json_file)

    def add_annotation(self, report_id, category_id, bbox, image_id):
        project = self.get_project(report_id)
        path = project['data']['annotation_file_path']
        new_id = 0

        with open(path, "r") as json_file:
            detections = json.load(json_file)
            annotations = detections['annotations']


            for annotation in annotations:
                if annotation['id'] > new_id:
                    new_id = annotation['id']
            new_id += 1

            new_annotation = {"id": new_id, "image_id": image_id,  "bbox": bbox, "score": 1.0, "category_id": category_id, "segmentation": [], "manual": True}
            annotations.append(new_annotation)

            detections['annotations'] = annotations

        with open(path, "w") as json_file:
            json.dump(detections, json_file)

        return new_id

    def set_unprocessed_changes(self, report_id, unprocessed_changes):
        self.update_data_by_keyword(report_id, 'unprocessed_changes', unprocessed_changes)

    def update_contains_unprocessed_images(self, report_id, contains_unprocessed_images):
        self.update_data_by_keyword(report_id, 'contains_unprocessed_images', contains_unprocessed_images)

    def remove_from_file_names_rgb(self, report_id, file_path):
        file_names = self.get_file_names_rgb(report_id)
        if file_path in file_names:
            file_names.remove(file_path)
        self.overwrite_file_names_sorted(report_id, file_names_rgb=file_names)

    def remove_from_file_names_ir(self, report_id, file_path):
        file_names = self.get_file_names_ir(report_id)
        if file_path in file_names:
            file_names.remove(file_path)
        self.overwrite_file_names_sorted(report_id, file_names_ir=file_names)

    def remove_from_unprocessed_images(self, report_id, file_path):
        project = self.get_project(report_id)
        data = project['data']

        try:
            couples = data['slide_file_paths']
        except:
            couples = []

        for couple in couples:
            if file_path in couple:
                couples.remove(couple)
                break

        data['slide_file_paths'] = couples
        if len(couples) == 0:
            data['contains_unprocessed_images'] = False
        else:
            data['contains_unprocessed_images'] = True
        with open(os.path.join(self.projects_path, str(report_id), "project.json"), "w") as json_file:
            json.dump(project, json_file)

    def generate_project_zip(self, report_id):
        path = self.projects_path + str(report_id)
        shutil.make_archive(path, 'zip', path)
        return path + ".zip"

    def generate_maps_zip(self, report_id):
        maps = self.get_maps(report_id)
        maps_paths = []
        for map in maps:
            maps_paths.append(map['file'])

        # zip files under project path with name maps.zip
        path = self.projects_path + str(report_id) + "/maps"

        #shutil.make_archive(path, 'zip', *maps_paths)
        self.zip_files(path + ".zip", maps_paths)
        return path + ".zip"

    def zip_files(self, output_zip, files):
        with zipfile.ZipFile(output_zip, 'w') as zipf:
            for file in files:
                # Add each file to the zip archive with its relative path
                #zipf.write(file, os.path.relpath(file))
                # Add each file to the zip archive without its relative path
                zipf.write(file, os.path.basename(file))

    def add_image_objects(self, report_id, rgb, ir, panos):
        try:
            if self.projects_image_objects[str(report_id)] == None:
                print("creating new image objects since they were none for report_id: " + str(report_id), flush=True)
                self.projects_image_objects[str(report_id)] = {'rgb': [], 'ir': [], 'panos': []}
        except:
            print("creating new image objects dict after error for report_id: " + str(report_id), flush=True)
            self.projects_image_objects[str(report_id)] = {'rgb': [], 'ir': [], 'panos': []}


        self.projects_image_objects[str(report_id)]['rgb'] += rgb
        self.projects_image_objects[str(report_id)]['ir'] += ir
        self.projects_image_objects[str(report_id)]['panos'] += panos

        #add paths to correct list in project or maybe not yet...

    def set_image_objects(self, report_id, rgb, ir, panos):
        self.projects_image_objects[str(report_id)] = {'rgb': rgb, 'ir': ir, 'panos': panos}

    def get_image_objects(self, report_id):
        try:
            return self.projects_image_objects[str(report_id)]
        except:
            self.projects_image_objects[str(report_id)] = {'rgb': [], 'ir': [], 'panos': []}
            return self.projects_image_objects[str(report_id)]

    def get_image_objects_rgb(self, report_id):
        return self.get_image_objects(report_id)['rgb']

    def get_image_objects_ir(self, report_id):
        return self.get_image_objects(report_id)['ir']

    def get_image_objects_panos(self, report_id):
        return self.get_image_objects(report_id)['panos']

    def get_image_objects_rgb_count(self, report_id):
        return len(self.get_image_objects_rgb(report_id))

    def get_image_objects_ir_count(self, report_id):
        return len(self.get_image_objects_ir(report_id))

    def get_image_objects_panos_count(self, report_id):
        return len(self.get_image_objects_panos(report_id))

    def delete_image_object(self, report_id, file_name, rgb=False , ir=False, pano=False):
        try:
            image_objects = []
            rgb_imgs = self.get_image_objects_rgb(report_id)
            ir_imgs = self.get_image_objects_ir(report_id)
            pano_imgs = self.get_image_objects_panos(report_id)

            if rgb:
                image_objects = rgb_imgs
            elif ir:
                image_objects = ir_imgs
            elif pano:
                image_objects = pano_imgs

            for image in image_objects:
                if file_name in image.get_image_path():
                    image_objects.remove(image)
                    break

            if rgb:
                self.set_image_objects(report_id, image_objects, ir_imgs, pano_imgs)
            elif ir:
                self.set_image_objects(report_id, rgb_imgs, image_objects, pano_imgs)
            elif pano:
                self.set_image_objects(report_id, rgb_imgs, ir_imgs, image_objects)

        except Exception as e:
            print("error while deleting image object: " + str(e), flush=True)

    def update_project_groups_file(self):
        with open(self.project_group_file, "w") as json_file:
            json.dump(self.project_groups, json_file)

    def get_project_group(self, group_id):
        for group in self.project_groups:
            if group['id'] == group_id:
                return group
        return None

    def create_project_group(self, name, description):
        project_group_id = self.generate_project_id()
        project_group = {'id': project_group_id, 'name': name, 'description': description, 'projects': []}
        self.project_groups.append(project_group)
        self.update_project_groups_file()
        return project_group_id

    def add_existing_project_to_group(self, group_id, project_id):
        project_group = self.get_project_group(group_id)
        print("adding project_id: " + str(project_id), flush=True)
        print(project_group, flush=True)
        project_group['projects'].append(project_id)
        self.update_project_groups_file()
        return project_group

    def remove_project_from_group(self, group_id, project_id):
        project_group = self.get_project_group(group_id)
        project_group['projects'].remove(project_id)
        self.update_project_groups_file()
        return project_group

    def get_project_group_by_project_id(self, project_id):
        for group in self.project_groups:
            for p_id in group['projects']:
                if project_id == p_id:
                    return group['id']
        return None

    def delete_project_group(self, group_id):
        project_group = self.get_project_group(group_id)
        self.project_groups.remove(project_group)
        self.update_project_groups_file()

    def get_project_groups(self):
        return self.project_groups

    def update_project_group_name(self, group_id, name):
        project_group = self.get_project_group(group_id)
        project_group['name'] = name
        self.update_project_groups_file()
        return project_group

    def update_project_group_description(self, group_id, description):
        project_group = self.get_project_group(group_id)
        project_group['description'] = description
        self.update_project_groups_file()
        return project_group