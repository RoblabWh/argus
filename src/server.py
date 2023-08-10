import json
import datetime
from argparse import Namespace

from model_weights_downloader import ModelWeightsDownloader
from project_manager import ProjectManager
from mapper_thread import MapperThread
from detection.datahandler import DataHandler
from detection.InferenceEngine import InferenceEngine


from flask import Flask, flash, request, redirect, url_for, render_template, jsonify
import os
import signal
from werkzeug.utils import secure_filename

import urllib.request


class ArgusServer:
    def __init__(self, upload_folder_path, project_manager):
        self.app = Flask(__name__)
        self.app.jinja_env.globals.update(thumbnail_for=self.thumbnail_for)

        UPLOAD_FOLDER = upload_folder_path
        self.app.secret_key = "DasIstBlauesLicht-UndWasMachtEs?-EsLeuchtetBlau"
        self.app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
        self.app.config['MAX_CONTENT_LENGTH'] = 500 * 10000 * 10000
        self.ALLOWED_EXTENSIONS = set(['png', 'jpg', 'jpeg', 'PNG', 'JPG', 'JPEG'])

        self.threads = []
        # self.map = {}
        self.project_manager = project_manager

        self.setup_routes()

    def setup_routes(self):
        self.app.add_url_rule('/',
                              view_func=self.projects_overview)
        self.app.add_url_rule('/create', methods=['POST'],
                              view_func=self.create_report)
        self.app.add_url_rule('/delete/<int:report_id>',
                              view_func=self.delete_report)
        self.app.add_url_rule('/<int:report_id>',
                              view_func=self.render_report)
        self.app.add_url_rule('/<int:report_id>/uploadFile', methods=['POST'],
                              view_func=self.upload_image_file)
        self.app.add_url_rule('/<int:report_id>/deleteFile', methods=['POST'],
                              view_func=self.delete_file)
        self.app.add_url_rule('/<int:report_id>/processFromUpload', methods=['POST', 'GET'],
                              view_func=self.initial_process)
        self.app.add_url_rule('/<int:report_id>/preprocessProgress', methods=['GET', 'POST'],
                              view_func=self.check_preprocess_progress)
        self.app.add_url_rule('/<int:report_id>/process_status', methods=['GET', 'POST'],
                              view_func=self.check_preprocess_status)
        self.app.add_url_rule('/<int:report_id>/edit', methods=['POST', 'GET'],
                              view_func=self.edit_report)
        self.app.add_url_rule('/get_map/<int:report_id>/<int:map_index>', methods=['GET', 'POST'],
                              view_func=self.send_next_map)
        self.app.add_url_rule('/stop_mapping_thread/<int:report_id>/', methods=['GET', 'POST'],
                              view_func=self.stop_thread)
        self.app.add_url_rule('/update_description/<int:report_id>', methods=['POST'],
                              view_func=self.update_description)
        self.app.add_url_rule("/update_title/<int:report_id>", methods=['POST'],
                              view_func=self.update_title)
        self.app.add_url_rule('/update_ir_settings/<int:report_id>/<string:settings>/', methods=['GET'],
                              view_func=self.update_ir_settings)
        self.app.add_url_rule('/gradient_lut/<int:gradient_id>', methods=['GET', 'POST'],
                              view_func=self.send_gradient_lut)
        self.app.add_url_rule('/run_detection/<int:report_id>', methods=['GET', 'POST'],
                              view_func=self.run_detection)
        self.app.add_url_rule('/update_detections_colors/<int:report_id>', methods=['POST'],
                              view_func=self.update_detections_colors)
        self.app.add_url_rule('/display/<filename>',
                              view_func=self.display_image)
        self.app.add_url_rule('/idgenerator/<filename>',
                              view_func=self.generate_id_for_image)
        self.app.add_url_rule('/shutdown',
                              view_func=self.shutdown)
        # self.app.add_url_rule('/<int:report_id>/upload', methods=['POST'],
        #                       view_func=self.upload_image)
        # self.app.add_url_rule('/<int:report_id>/process', methods=['GET', 'POST'],
        #                       view_func=self.process)

    def projects_overview(self):
        projects_dict_list = self.project_manager.get_projects()
        order_by_flight_date = self.calculate_order_based_on_flight_date(projects_dict_list)
        return render_template('projectsOverview.html', projects=projects_dict_list, flightOrder=order_by_flight_date)

    def create_report(self):
        name = request.form.get("name")
        description = request.form.get("description")
        self.project_manager.create_project(name, description)
        projects_dict_list = self.project_manager.get_projects()
        order_by_filght_date = self.calculate_order_based_on_flight_date(projects_dict_list)
        return render_template('projectsOverview.html', projects=projects_dict_list, flightOrder=order_by_filght_date)

    def delete_report(self, report_id):
        self.project_manager.delete_project(report_id)
        return self.projects_overview()

    def render_report(self, report_id):
        print("upload_form" + str(report_id))
        if (self.project_manager.has_project(report_id)):
            if not self.project_manager.get_project(report_id)['data']['flight_data']:
                # file_names = project_manager.get_project(report_id)['data']['file_names']
                return self.render_standard_report(report_id, template='simpleUpload.html')
                # return render_standard_report(report_id, template='startProcessing.html')
            return self.render_standard_report(report_id)
        else:
            projects_dict_list = self.project_manager.get_projects()
            order_by_filght_date = self.calculate_order_based_on_flight_date(projects_dict_list)
            return render_template('projectsOverview.html', projects=projects_dict_list,
                                   message="Report does not exist", flightOrder=order_by_filght_date)


    def upload_image_file(self, report_id):
        print("upload_image_file " + str(report_id))
        if 'image' not in request.files:
            print('no "image" found in request.files:', request.files)
            return json.dumps({'success': False}), 418, {'ContentType': 'application/json'}

        file = request.files['image']
        file_names = []

        if file and self.allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file_names.append("uploads/" + str(report_id) + "/" + filename)
            file.save(os.path.join(self.app.config['UPLOAD_FOLDER'] + str(report_id) + "/", filename))
        else:
            flash('Allowed image types are -> png, jpg, jpeg, gif')
            return json.dumps({'success': False}), 415, {'ContentType': 'application/json'}

        self.project_manager.update_file_names(report_id, file_names)
        self.project_manager.set_unprocessed_changes(report_id, True)
        self.project_manager.append_unprocessed_images(report_id, file_names)

        return json.dumps({'success': True}), 200, {'ContentType': 'application/json'}

    def delete_file(self, report_id):
        data = request.get_json()
        filename = data.get('filename')
        project = self.project_manager.get_project(report_id)
        file_names = project['data']['file_names']
        self.project_manager.set_unprocessed_changes(report_id, True)
        print("len of file_names: ", len(file_names))
        if filename:

            if self.delete_file_in_folder(report_id, filename, "/"):
                return 'File deleted successfully.'

            if self.delete_file_in_folder(report_id, filename, "/rgb/"):
                return 'File deleted successfully.'

            if self.delete_file_in_folder(report_id, filename, "/ir/"):
                return 'File deleted successfully.'

            if self.delete_file_in_folder(report_id, filename, "/panos/"):
                return 'File deleted successfully.'

            return 'File not found.'

        else:
            return 'Invalid request.'



    def initial_process(self, report_id):
        if request.method == 'POST':

            with_mapping = request.form.get('with_mapping')
            with_odm = request.form.get('with_odm')
            ai_detection = request.form.get('ai_detection')

            with_mapping = True if with_mapping is not None else False
            with_odm = True if with_odm is not None else False
            ai_detection = True if ai_detection is not None else False

            map_resolution = request.form.get('map resolution')
            resolutions = {
                'low': (1024, 1024),
                'medium': (2048, 2048),
                'high': (4096, 4096),
                'ultra': (6144, 6144)
            }
            max_width, max_height = resolutions.get(map_resolution, (2048, 2048))

            file_names = self.project_manager.get_file_names(report_id)
            data = self.project_manager.get_project(report_id)['data']

            print("initial_process " + str(report_id), "with_mapping: " + str(with_mapping), "with_odm: " + str(with_odm),
                    "ai_detection: " + str(ai_detection), "map_resolution: " + str(map_resolution))

            thread = MapperThread(with_mapping, with_odm, report_id, (max_width, max_height), file_names, data)
            self.threads.append(thread)
            thread.start()
            print("process started")
            return jsonify(thread.get_progress_preprocess())


    def check_preprocess_progress(self, report_id):
        print('asking for preprocessing progress of report ' + str(report_id))
        progress_preprocessing = -1

        for thread in self.threads:
            if thread.report_id == report_id:
                # print("check_preprocess_status" + str(report_id))
                progress_preprocessing = thread.get_progress_preprocess()
                if progress_preprocessing == 100 and not thread.metadata_delivered:
                    flight_data, camera_specs, weather, maps, file_names_rgb, file_names_ir, ir_settings, panos, \
                        couples_path_list, flight_trajectory = thread.get_results()
                    self.project_manager.update_flight_data(report_id, flight_data)
                    self.project_manager.update_camera_specs(report_id, camera_specs)
                    self.project_manager.update_weather(report_id, weather)
                    self.project_manager.update_maps(report_id, maps)
                    self.project_manager.update_ir_settings(report_id, ir_settings)
                    self.project_manager.add_panos(report_id, panos)
                    self.project_manager.update_slide_file_paths(report_id, couples_path_list)
                    self.project_manager.update_flight_trajectory(report_id, flight_trajectory)
                    self.project_manager.overwrite_file_names_sorted(report_id, file_names_rgb=file_names_rgb,
                                                                file_names_ir=file_names_ir)
                    self.project_manager.update_contains_unprocessed_images(report_id, False)
                    self.project_manager.set_unprocessed_changes(report_id, False)
                    thread.metadata_delivered = True
                    return self.render_standard_report(report_id)
                else:
                    return jsonify(progress_preprocessing)
                break
        return jsonify(progress_preprocessing)

    def check_preprocess_status(self, report_id):
        print('asking for status of report ' + str(report_id))
        progress_mapping = -1
        maps_done = []

        for thread in self.threads:
            if thread.report_id == report_id:
                # print("check_preprocess_status" + str(report_id))
                progress_mapping = thread.get_progress_mapping()
                # print(progress_preprocessing, progress_mapping)
                maps_done = thread.get_maps_done()
                maps_sent = thread.get_maps_sent()
                if progress_mapping == 100:
                    self.project_manager.update_maps(report_id, thread.get_maps())
                break

        progress_dict = {"percentage": progress_mapping, "maps_done": maps_done, "maps_loaded": maps_sent}
        return jsonify(progress_dict)

    def edit_report(self, report_id):
        print("editing report " + str(report_id))
        if (self.project_manager.has_project(report_id)):
            print("Directory exists")
            return self.render_upload_report(report_id)
            #self.render_standard_report(report_id, template='simpleUpload.html')
        else:
            projects_dict_list = self.project_manager.get_projects()
            order_by_filght_date = self.calculate_order_based_on_flight_date(projects_dict_list)
            return render_template('projectsOverview.html', projects=projects_dict_list,
                                   message="Report does not exist",
                                   flightOrder=order_by_filght_date)

    def send_next_map(self, report_id, map_index):
        print("get_map for id" + str(report_id) + " with: " + str(map_index))
        for thread in self.threads:
            if thread.report_id == report_id:
                maps_done = thread.get_maps_done()
                if maps_done[map_index]:
                    map = thread.get_maps()[map_index]
                    self.project_manager.update_maps(report_id, thread.get_maps())
                    thread.update_maps_sent(map_index)
                    map["file_url"] = url_for('static', filename=map["file"])
                    return jsonify(map)

        return jsonify({"file": "empty"})

    def stop_thread(self, report_id):
        print("stop_thread for id" + str(report_id))
        for thread in self.threads:
            if thread.report_id == report_id:
                self.threads.remove(thread)
                return "success"
        return "failure"


    def update_description(self, report_id):
        description = request.form.get('content')
        print("update_description for id" + str(report_id) + " with: " + str(description))
        description = self.process_html_strings(description)
        self.project_manager.update_description(report_id, description)
        return "success"

    def update_title(self, report_id):
        title = request.form.get('content')
        print("update_title for id" + str(report_id) + " with: " + str(title))
        title = self.process_html_strings(title, no_newline=True)
        self.project_manager.update_title_name(report_id, title)
        return "success"

    def update_ir_settings(self, report_id, settings):
        settings = settings.split(",")
        settings = [int(i) for i in settings]
        self.project_manager.update_ir_settings_from_website(report_id, settings)
        print("update_ir_settings for id" + str(report_id) + " with: " + str(settings))
        return "success"

    def send_gradient_lut(self, gradient_id):
        lut = json.load(open("./static/default/gradient_luts/gradient_lut_" + str(gradient_id) + ".json"))
        return lut


    def run_detection(self, report_id):
        DOCKER_ENV_KEY = os.environ.get('AM_I_IN_A_DOCKER_CONTAINER', False)
        if DOCKER_ENV_KEY:
            print('currently not supported in Docker')
        else:
            numbr_of_models = 2
            models_setting = request.form.get('model_options')
            if models_setting == "all":
                numbr_of_models = 5
            elif models_setting == "medium":
                numbr_of_models = 3

            self.detect_objects(numbr_of_models, report_id)
            detections = json.load(open(self.project_manager.get_annotation_file_path(report_id)))

            # return render_standard_report(report_id)
            return detections

    def update_detections_colors(self, report_id):
        color = [request.form.get('colorH'), request.form.get('colorS'), request.form.get('colorL')]
        category_name = request.form.get('category_name')
        print(request.form)
        print("update_detections_colors for id" + str(report_id) + " with: " + str(color) + " and category_name: " + str(
                category_name))
        self.project_manager.update_detections_colors(report_id, color, category_name)
        return "success"

    def detect_objects(self, numbr_of_models, report_id):
        networks_weights_folder = "./detection/model_weights"
        weights_paths_list = []

        weights_paths_list.append(
            networks_weights_folder + "/deformable_detr_twostage_refine_r50_16x2_50e_coco_fire_04")
        weights_paths_list.append(networks_weights_folder + "/autoassign_r50_fpn_8x2_1x_coco_fire_0")
        if numbr_of_models >= 3:
            weights_paths_list.append(networks_weights_folder + "/tood_r101_fpn_dconv_c3-c5_mstrain_2x_coco_fire_5")
            if numbr_of_models >= 4:
                weights_paths_list.append(
                    networks_weights_folder + "/vfnet_x101_32x4d_fpn_mdconv_c3-c5_mstrain_2x_coco_fire_1")
                if numbr_of_models >= 5:
                    weights_paths_list.append(networks_weights_folder + "/yolox_s_8x8_300e_coco_fire_300_4")

        images_path_list = self.project_manager.get_file_names_rgb(report_id)
        images_path_list = ["./static/" + path for path in images_path_list]
        config_path = "detection/config/custom/config.py"
        ann_path = self.project_manager.get_annotation_file_path(report_id)  # vom project manager geben lassen

        data_handler = DataHandler(config_path, ann_path)
        data_handler.set_image_paths(images_path_list, 2)
        data_handler.create_empty_ann()

        engine = InferenceEngine(network_folders=weights_paths_list)
        results = engine.inference_all(data_handler, 0.3)
        bboxes = data_handler.compare_results(results)
        data_handler.create_coco()
        # data_handler.save_images("result", bboxes, engine.models[0], 0.3)
        data_handler.save_results_in_json(bboxes)
        data_handler.structure_ann_by_images()

    def display_image(self, filename):
        return redirect(url_for('static', filename='uploads/' + filename), code=301)

    def thumbnail_for(self, path):
        path_thumbnail = path[:path.rindex('/') + 1] + 'thumbnails/' + path[path.rindex('/') + 1:]
        if not os.path.isfile('./static/' + path_thumbnail):
            path_thumbnail = path
        return path_thumbnail

    def generate_id_for_image(self, filename):
        return redirect(url_for('static', filename='uploads/' + filename), code=301)

    def shutdown(self):
        print("Server shutting down...")
        self.stop_server()
        return 'Server shutting down...'

    def stop_server(self):
        os.kill(os.getpid(), signal.SIGINT)

    def run(self):
        self.app.run(host="0.0.0.0", port=5000, debug=True, use_reloader=False)

    # Utulity functions:

    def calculate_order_based_on_flight_date(self, projects_dict_list):
        # Convert the creation times to datetime objects
        times = []
        for project in projects_dict_list:
            try:
                time = datetime.datetime.strptime(project["data"]["flight_data"][0]["value"], '%d.%m.%Y %H:%M')
                print('case a', time)
            except:
                try:
                    time = datetime.datetime.strptime(project["data"]["flight_data"][0]["value"], '%Y:%m:%d %H:%M:%S')
                    print('case b', time)
                except:
                    time = datetime.datetime.now()
                    print('case c', time)

            times += [time]

        # Get the indices of the projects sorted by creation time
        indices = sorted(range(len(times)), key=lambda i: times[i], reverse=True)
        return indices

    def render_standard_report(self, report_id, thread=None, template="concept.html"):
        data = self.project_manager.get_project(report_id)['data']
        flight_data = data["flight_data"]
        camera_specs = data["camera_specs"]
        weather = data["weather"]
        file_names = data["file_names"]
        file_names_ir = data["file_names_ir"]
        panos = data["panos"]
        ir_settings = data["ir_settings"]
        maps = data["maps"]

        has_ir = False
        if file_names_ir != []:
            has_ir = True

        try:
            detections_path = data["annotation_file_path"]
            detections = json.load(open(detections_path))
        except:
            detections = None

        slide_file_paths = []
        try:
            slide_file_paths = data["slide_file_paths"]
        except:
            pass

        flight_trajectory = []
        try:
            flight_trajectory = data["flight_trajectory"]
        except:
            pass

        contains_unprocessed_images = False
        try:
            contains_unprocessed_images = data["contains_unprocessed_images"]
        except:
            pass

        unprocessed_changes = False
        try:
            unprocessed_changes = data["unprocessed_changes"]
        except:
            pass

        has_rgb = False
        for slide in slide_file_paths:
            if slide[0] != "":
                has_rgb = True
                break

        message = None
        processing = False
        for thread in self.threads:
            processing = False
            if thread.report_id == report_id:
                processing = True
                # if(thread.progress_mapping == 100):
                #     processing = False
                # else:
                #     processing = True
                message = thread.message
                break

        gradient_lut = json.load(open("./static/default/gradient_luts/gradient_lut_1.json"))

        project = {"id": report_id, "name": self.project_manager.get_project_name(report_id),
                   "description": self.project_manager.get_project_description(report_id),
                   'creation_time': self.project_manager.get_project_creation_time(report_id)}
        return render_template(template, id=report_id, file_names=file_names, file_names_ir=file_names_ir,
                               panos=panos, has_rgb=has_rgb, has_ir=has_ir, flight_data=flight_data,
                               slide_file_paths=slide_file_paths, camera_specs=camera_specs, weather=weather,
                               flight_trajectory=flight_trajectory, maps=maps, project=project, message=message,
                               processing=processing, gradient_lut=gradient_lut, ir_settings=ir_settings,
                               detections=detections, unprocessed_images=contains_unprocessed_images,
                               unprocessed_changes=unprocessed_changes)
    def render_upload_report(self, report_id, template="simpleUpload.html"):
            data = self.project_manager.get_project(report_id)['data']
            file_names_rgb = data["file_names"]
            file_names_ir = data["file_names_ir"]
            file_names_panos = [p['file'] for p in data["panos"]]
            file_names_upload = file_names_rgb.copy() + file_names_ir.copy() + file_names_panos.copy()

            has_ir = False
            if file_names_ir != []:
                has_ir = True

            contains_unprocessed_images = False
            try:
                contains_unprocessed_images = data["contains_unprocessed_images"]
            except:
                pass


            processing = False
            for thread in self.threads:
                processing = False
                if thread.report_id == report_id:
                    processing = True
                    break


            project = {"id": report_id, "name": self.project_manager.get_project_name(report_id),
                       "description": self.project_manager.get_project_description(report_id),
                       'creation_time': self.project_manager.get_project_creation_time(report_id)}
            return render_template(template, id=report_id, project=project, file_names=file_names_upload,
                                   processing=processing)

    def delete_file_in_folder(self, report_id, filename, subfolder, thumbnail=False):
        file_path = "uploads/" + str(report_id) + subfolder + filename
        print("trying to delete file in folder " + file_path)
        if os.path.exists('static/' + file_path):
            os.remove('static/' + file_path)
            print("file deleted @" + file_path)
            if not thumbnail:
                self.project_manager.remove_from_file_names_rgb(report_id, file_path)
                self.project_manager.remove_from_file_names_ir(report_id, file_path)
                self.project_manager.remove_from_panos(report_id, file_path)
                self.project_manager.remove_from_unprocessed_images(report_id, file_path)
                self.delete_file_in_folder(report_id, filename, subfolder + "thumbnails/", thumbnail=True)
            return True
        return False

    def process_html_strings(self, html_string, no_newline=False):
        html_string = html_string.replace("\n", "")
        html_string = html_string.strip()
        if no_newline:
            html_string = html_string.replace("<br>", "")
        else:
            html_string = html_string.replace("<br>", "\n")
        html_string = html_string.replace("&amp;", "&")
        return html_string

    def allowed_file(self, filename):
        return '.' in filename and filename.rsplit('.', 1)[1].lower() in self.ALLOWED_EXTENSIONS

