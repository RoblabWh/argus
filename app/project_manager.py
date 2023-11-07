import os
import json
import shutil
from datetime import datetime


class ProjectManager:
    def __init__(self, projects_path):
        self.projects = []
        self.highest_id = -1
        self.current_project_id = None
        if not os.path.exists(projects_path):
            os.makedirs(projects_path)
        self.projects_path = projects_path
        #self.image_mapper = {}


    def create_project(self, name, description):
        id = self.get_next_id()
        print("creating project with id: " + str(id))
        os.mkdir(os.path.join(self.projects_path, str(id)))
        data = self.generate_empty_data_dict()
        creation_time = datetime.now().strftime("%d.%m.%Y %H:%M:%S")
        project = ({'name': name, 'description': description, 'id': id, 'creation_time': creation_time, 'data': data})
        self.projects.append(project)
        with open(os.path.join(self.projects_path, str(id), "project.json"), "w") as json_file:
            json.dump(project, json_file)

        self.highest_id += 1
        self.projects = sorted(self.projects, key=lambda d: d['id'], reverse=True)
        return project

    def load_project_from_directory(self, project_id):
        # load project.json from static/uploads/id
        # if no project.json exists, return None
        project = None
        if os.path.isfile(os.path.join(self.projects_path, project_id, "project.json")):
            print("loading project from directory: " + project_id)
            with open(os.path.join(self.projects_path, project_id, "project.json"), "r") as json_file:
                project = json.load(json_file)
        return project

    def initiate_project_list(self):
        # check for every directory in static/uploads/ if there is project.json
        # if yes, load project and add to project list
        for project in os.listdir(self.projects_path):
            if os.path.isdir(os.path.join(self.projects_path, project)):
                project = self.load_project_from_directory(project)
                if project != None:
                    self.projects.append(project)
                    if project['id'] > self.highest_id:
                        self.highest_id = project['id']

        self.projects = sorted(self.projects, key=lambda d: d['id'], reverse=True)

    def get_project(self, id):
        for project in self.projects:
            if project['id'] == id:
                return project
        return None

    def project_path(self, project_id):
        return os.path.join(self.projects_path, str(project_id))

    def get_projects(self):
        if self.projects == []:
            self.initiate_project_list()
        return self.projects

    def set_current_project(self, id):
        self.current_project_id = id

    def get_current_project(self):
        return self.get_project(self.current_project_id)

    def get_current_project_id(self):
        return self.current_project_id

    def get_next_id(self):
        return self.highest_id + 1

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
        data = {"file_names": [], "file_names_ir" : [], "panos": [], "flight_data": [], "camera_specs": [], "weather": [], "maps": [], "ir_settings": []}
        return data

    def update_file_names(self, id, file_names):
        # append filenames to filenames inside of data of project with id
        project = self.get_project(id)
        data = project['data']
        data['file_names'] += file_names
        with open(os.path.join(self.projects_path, str(id), "project.json"), "w") as json_file:
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
        print("len of file_names: " + str(len(data['file_names'])), "len of file_names_ir: " + str(len(data['file_names_ir'])))
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
            if p['file'] == pano_file:
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
        if project != None:
            self.projects.remove(project)
            shutil.rmtree(self.projects_path + str(id), ignore_errors=True)
            #os.rmdir(self.projects_path + str(id))
            return True
        return False

    def get_file_names(self, id):
        return self.get_data_by_keyword(id, 'file_names') + self.get_data_by_keyword(id, 'file_names_ir')

    def get_file_names_rgb(self, id):
        return self.get_data_by_keyword(id, 'file_names')

    def get_file_names_ir(self, id):
        return self.get_data_by_keyword(id, 'file_names_ir')

    def get_panos(self, id):
        return self.get_data_by_keyword(id, 'panos')

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

    def set_unprocessed_changes(self, report_id, unprocessed_changes):
        self.update_data_by_keyword(report_id, 'unprocessed_changes', unprocessed_changes)

    def update_contains_unprocessed_images(self, report_id, contains_unprocessed_images):
        self.update_data_by_keyword(report_id, 'contains_unprocessed_images', contains_unprocessed_images)

    def remove_from_file_names(self, report_id, file_path):
        file_names = self.get_file_names(report_id)
        file_names.remove(file_path)
        self.overwrite_file_names_sorted(report_id, file_names_rgb=file_names)

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
