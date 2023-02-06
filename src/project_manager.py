import os
import json
import shutil
from datetime import datetime
from image_mapper_for_falsk import ImageMapper


class ProjectManager:
    def __init__(self, path_to_images):
        self.projects = []
        self.highest_id = -1
        self.current_project_id = None
        self.projects_path = path_to_images
        self.image_mapper = {}

    def create_project(self, name, description):
        id = self.get_next_id()
        print("creating project with id: " + str(id))
        os.mkdir(self.projects_path + str(id))
        data = self.generate_empty_data_dict()
        creation_time = datetime.now().strftime("%d.%m.%Y %H:%M:%S")
        project = ({'name': name, 'description': description, 'id': id, 'creation_time': creation_time, 'data': data})
        self.projects.append(project)
        #save project to static/uploads/id/project.json
        with open(self.projects_path + str(id) + "/project.json", "w") as json_file:
            json.dump(project, json_file)

        self.highest_id += 1
        self.projects = sorted(self.projects, key=lambda d: d['id'], reverse=True)
        return project

    def load_project_from_directory(self, directory):
        # load project.json from static/uploads/id
        # if no project.json exists, return None
        project = None
        if os.path.isfile(self.projects_path + directory + "/project.json"):
            print("loading project from directory: " + directory)
            with open(self.projects_path + directory + "/project.json", "r") as json_file:
                project = json.load(json_file)
        return project

    def initiate_project_list(self):
        # check for every directory in static/uploads/ if there is project.json
        # if yes, load project and add to project list
        for directory in os.listdir(self.projects_path):
            if os.path.isdir(self.projects_path + directory):
                project = self.load_project_from_directory(directory)
                if project != None:
                    self.projects.append(project)
                    if project['id'] > self.highest_id:
                        self.highest_id = project['id']

        self.projects = sorted(self.projects, key=lambda d: d['id'], reverse=True)

    def get_project(self, id):
        # print("getting project with id: " + str(id))
        for project in self.projects:
            if project['id'] == id:
                return project
        return None

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
        # print("filenames before: " + str(data['file_names']))
        # print("filenames to add: " + str(file_names))
        data['file_names'] += file_names
        #write updated data to project.json
        with open(self.projects_path + str(id) + "/project.json", "w") as json_file:
            json.dump(project, json_file)

        return data['file_names']

    def overwrite_file_names_sorted(self, id, file_names_rgb=None, file_names_ir=None):
        project = self.get_project(id)
        data = project['data']
        if file_names_rgb != None:
            data['file_names'] = file_names_rgb
        if file_names_ir != None:
            data['file_names_ir'] = file_names_ir
        #write updated data to project.json
        with open(self.projects_path + str(id) + "/project.json", "w") as json_file:
            json.dump(project, json_file)

        return data['file_names']

    def update_description(self, id, description):
        project = self.get_project(id)
        project['description'] = description
        with open(self.projects_path + str(id) + "/project.json", "w") as json_file:
            json.dump(project, json_file)
        return project['description']

    def update_flight_data(self, id, flight_data):
        return self.update_data_by_keyword(id, 'flight_data', flight_data)

    def update_camera_specs(self, id, camera_specs):
        return self.update_data_by_keyword(id, 'camera_specs', camera_specs)

    def update_weather(self, id, weather):
        return self.update_data_by_keyword(id, 'weather', weather)

    def update_maps(self, id, maps):
        return self.update_data_by_keyword(id, 'maps', maps)

    def update_ir_settings(self, id, ir_settings):
        return self.update_data_by_keyword(id, 'ir_settings', ir_settings)

    def update_panos(self, id, panos):
        return self.update_data_by_keyword(id, 'panos', panos)

    def add_panos(self, id, panos):
        panos = self.get_panos(id) + panos
        self.update_data_by_keyword(id, 'panos', panos)

    def update_data_by_keyword(self, id, keyword, data):
        project = self.get_project(id)
        project['data'][keyword] = data
        with open(self.projects_path + str(id) + "/project.json", "w") as json_file:
            json.dump(project, json_file)
        return project['data'][keyword]

    def delete_project(self, id):
        project = self.get_project(id)
        if project != None:
            self.projects.remove(project)
            #delete directory
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

    def get_data_by_keyword(self, id, keyword):
        project = self.get_project(id)
        data = project['data']
        return data[keyword]

    def get_project_name(self, report_id):
        project = self.get_project(report_id)
        return project['name']

    def get_project_description(self, report_id):
        project = self.get_project(report_id)
        # print("get project description", project['description'])
        return project['description']

    def get_project_creation_time(self, report_id):
        project = self.get_project(report_id)
        try:
            return project['creation_time']
        except:
            return "no creation time found"

    def get_image_mapper(self, report_id):
        try:
            mapper = self.image_mapper[str(report_id)]
            return mapper
        except:
            mapper = ImageMapper(self.projects_path)
            self.image_mapper[str(report_id)] = mapper
            return mapper

    def update_ir_settings_from_website(self, report_id, settings):
        project = self.get_project(report_id)
        ir_settings = project['data']['ir_settings']

        ir_settings['ir_min_temp'] = settings[0]
        ir_settings['ir_max_temp'] = settings[1]
        ir_settings['ir_color_scheme'] = settings[2]

        self.update_ir_settings(report_id, ir_settings)
