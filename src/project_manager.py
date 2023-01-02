import os
import json
import shutil
class ProjectManager:
    def __init__(self):
        self.projects = []
        self.highest_id = -1
        self.current_project_id = None
        self.projects_path = "./static/uploads/"

    def create_project(self, name, description):
        id = self.get_next_id()
        print("creating project with id: " + str(id))
        os.mkdir(self.projects_path + str(id))
        data = self.generate_empty_data_dict()
        project = ({'name': name, 'description': description, 'id': id, 'data': data})
        self.projects.append(project)
        #save project to static/uploads/id/project.json
        with open(self.projects_path + str(id) + "/project.json", "w") as json_file:
            json.dump(project, json_file)

        self.highest_id += 1
        return project

    def load_project_from_directory(self, directory):
        # load project.json from static/uploads/id
        # if no project.json exists, return None
        project = None
        if os.path.isfile(self.projects_path + directory + "/project.json"):
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

    def get_project(self, id):
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

    def generate_empty_data_dict(self):
        data = {"file_names": [], "flight_data": [], "camera_specs": [], "weather": [], "map": []}
        return data

    def update_file_names(self, id, file_names):
        # append filenames to filenames inside of data of project with id
        project = self.get_project(id)
        data = project['data']
        print("filenames before: " + str(data['file_names']))
        print("filenames to add: " + str(file_names))
        data['file_names'] += file_names
        #write updated data to project.json
        with open(self.projects_path + str(id) + "/project.json", "w") as json_file:
            json.dump(project, json_file)

        return data['file_names']

    def update_flight_data(self, id, flight_data):
        return self.update_data_by_keyword(id, 'flight_data', flight_data)

    def update_camera_specs(self, id, camera_specs):
        return self.update_data_by_keyword(id, 'camera_specs', camera_specs)

    def update_weather(self, id, weather):
        return self.update_data_by_keyword(id, 'weather', weather)

    def update_map(self, id, map):
        return self.update_data_by_keyword(id, 'map', map)

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
        return self.get_data_by_keyword(id, 'file_names')

    def get_flight_data(self, id):
        return self.get_data_by_keyword(id, 'flight_data')

    def get_camera_specs(self, id):
        return self.get_data_by_keyword(id, 'camera_specs')

    def get_weather(self, id):
        return self.get_data_by_keyword(id, 'weather')

    def get_map(self, id):
        return self.get_data_by_keyword(id, 'map')

    def get_data_by_keyword(self, id, keyword):
        project = self.get_project(id)
        data = project['data']
        return data[keyword]