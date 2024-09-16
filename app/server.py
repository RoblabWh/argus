import json
import datetime

from mapping.mapper_thread import MapperThread
from mapping.image_mapper_process import ImageMapperProcess
from thermal.thermal_analyser import ThermalAnalyser
from mapping.filter_thread import FilterThread
from data_share_manager import DataShareManager
from export.util import popen_and_call

# from gunicorn.app.base import BaseApplication
from flask import Flask, flash, request, redirect, url_for, render_template, jsonify, send_file
import os
import signal
from werkzeug.utils import secure_filename

# class FlaskApp(BaseApplication):
#     def __init__(self, app, options=None):
#         self.options = options or {}
#         self.application = app
#         super().__init__()
#
#     def load_config(self):
#         for key, value in self.options.items():
#             if key in self.cfg.settings and value is not None:
#                 self.cfg.set(key.lower(), value)
#
#     def load(self):
#         return self.application

class ArgusServer:
    def __init__(self, address, port, project_manager, nodeodm_manager, webodm_manager, detection_manager, slam_manager):
        self.app = Flask(__name__)
        self.app.jinja_env.globals.update(global_for=self.global_for)
        self.app.jinja_env.globals.update(thumbnail_for=self.thumbnail_for)

        self.app.secret_key = "DasIstBlauesLicht-UndWasMachtEs?-EsLeuchtetBlau"
        self.app.config['UPLOAD_FOLDER'] = project_manager.projects_path
        self.app.config['MAX_CONTENT_LENGTH'] = 500 * 10000 * 10000
        self.app.config['TEMPLATES_AUTO_RELOAD'] = True
        self.ALLOWED_EXTENSIONS = set(['png', 'jpg', 'jpeg', 'PNG', 'JPG', 'JPEG'])
        self.ALLOWED_VIDEO_EXTENSIONS = set(['mp4', 'MP4','avi','AVI'])
        self.ALLOWED_INSV_EXTENSIONS = set(['insv', 'INSV'])
        self.ALLOWED_EXTENSIONS_PROJECT = set(['zip'])

        self.threads = []
        self.export_threads = []
        self.detection_threads = []
        self.image_filter_threads = []
        # self.map = {}

        self.address = address
        self.port = port
        self.project_manager = project_manager
        self.nodeodm_manager = nodeodm_manager
        self.webodm_manager = webodm_manager
        self.detection_manager = detection_manager
        self.slam_manager = slam_manager
        self.thermal_analyser = ThermalAnalyser(project_manager)
        self.data_share_manager = DataShareManager("localhost", "admin", "admin")

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
        self.app.add_url_rule('/<int:report_id>/update',
                              view_func=self.render_report_update)
        self.app.add_url_rule('/<int:report_id>/uploadFile', methods=['POST'],
                              view_func=self.upload_image_file)
        self.app.add_url_rule('/<int:report_id>/uploadVideoFileDropzone', methods=['POST'],
                              view_func=self.upload_video_file_dropzone)
        self.app.add_url_rule('/<int:report_id>/uploadInsv1FileDropzone', methods=['POST'],
                              view_func=self.upload_insv1_file_dropzone)
        self.app.add_url_rule('/<int:report_id>/uploadInsv2FileDropzone', methods=['POST'],
                              view_func=self.upload_insv2_file_dropzone)
        self.app.add_url_rule('/<int:report_id>/uploadMaskFile', methods=['POST'],
                              view_func=self.upload_mask_file)
        self.app.add_url_rule('/<int:report_id>/deleteFile', methods=['POST'],
                              view_func=self.delete_file)
        self.app.add_url_rule('/<int:report_id>/deleteVideoFile', methods=['POST'],
                              view_func=self.delete_video_file)
        self.app.add_url_rule('/<int:report_id>/deleteMaskFile', methods=['POST'],
                              view_func=self.delete_mask_file)
        self.app.add_url_rule('/<int:report_id>/deleteInsv1File', methods=['POST'],
                              view_func=self.delete_insv1_file)
        self.app.add_url_rule('/<int:report_id>/deleteInsv2File', methods=['POST'],
                              view_func=self.delete_insv2_file)
        self.app.add_url_rule('/<int:report_id>/checkUploadedImages', methods=['GET', 'POST'],
                              view_func=self.check_upload_processing_progress)
        self.app.add_url_rule('/<int:report_id>/checkUploadedFiles', methods=['GET', 'POST'],
                              view_func=self.check_upload_processing_progress_slam)
        self.app.add_url_rule('/<int:report_id>/checkUploadedInsvFiles', methods = ['GET', 'POST'],
                              view_func=self.check_upload_processing_progress_insv)
        self.app.add_url_rule('/<int:report_id>/processFromUpload', methods=['POST', 'GET'],
                              view_func=self.initial_process)
        self.app.add_url_rule('/<int:report_id>/startSlamProcess', methods=['POST', 'GET'],
                              view_func=self.start_slam)
        self.app.add_url_rule('/<int:report_id>/startStitcherProcess', methods=['POST', 'GET'],
                              view_func=self.start_stitcher)
        self.app.add_url_rule('/slam_map_update', methods=['POST', 'GET'],
                              view_func=self.slam_map_update)
        self.app.add_url_rule('/<int:report_id>/preprocessProgress', methods=['GET', 'POST'],
                              view_func=self.check_preprocess_progress)
        self.app.add_url_rule('/<int:report_id>/process_status', methods=['GET', 'POST'],
                              view_func=self.check_preprocess_status)
        self.app.add_url_rule('/<int:report_id>/slam_map_process_status', methods=['GET', 'POST'],
                              view_func=self.check_slam_map_process_status)
        self.app.add_url_rule('/slam_status/<int:report_id>', methods=['POST', 'GET'],
                              view_func=self.check_slam_status)
        self.app.add_url_rule('/stitcher_status/<int:report_id>', methods=['POST', 'GET'],
                              view_func=self.check_stitcher_status)
        self.app.add_url_rule('/load_video_from_stitcher/<int:report_id>', methods=['POST'],
                              view_func=self.load_video_from_stitcher)
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
        self.app.add_url_rule('/load_detection_results/<int:report_id>', methods=['GET', 'POST'],
                              view_func=self.load_detection_results)
        self.app.add_url_rule('/load_keyframes/<int:report_id>', methods=['GET', 'POST'],
                              view_func=self.load_keyframes)
        self.app.add_url_rule('/load_vertices/<int:report_id>', methods=['GET', 'POST'],
                              view_func=self.load_vertices)
        self.app.add_url_rule('/load_landmarks/<int:report_id>', methods=['GET', 'POST'],
                              view_func=self.load_landmarks)
        self.app.add_url_rule('/detection_status/<int:report_id>', methods=['GET', 'POST'],
                              view_func=self.check_detection_status)
        self.app.add_url_rule('/delete_annotation/<int:report_id>', methods=['POST'],
                                view_func=self.delete_annotation)
        self.app.add_url_rule('/edit_annotation/<int:report_id>', methods=['POST'],
                                view_func=self.edit_annotation)
        self.app.add_url_rule('/edit_annotation_type/<int:report_id>', methods=['POST'],
                                view_func=self.edit_annotation_type)
        self.app.add_url_rule('/add_annotation/<int:report_id>', methods=['POST'],
                                view_func=self.add_annotation)
        self.app.add_url_rule('/process_in_webodm/<int:report_id>', methods=['GET', 'POST'],
                                view_func=self.process_in_webodm)
        self.app.add_url_rule('/get_webodm_port', methods=['GET', 'POST'],
                              view_func=self.get_webodm_port)
        self.app.add_url_rule('/webodm_project_exists/<int:report_id>', methods=['GET', 'POST'],
                              view_func=self.webodm_project_exists)
        self.app.add_url_rule('/get_webodm_last_task/<int:report_id>', methods=['GET', 'POST'],
                              view_func=self.get_webodm_last_task)
        self.app.add_url_rule('/get_webodm_all_tasks/<int:report_id>', methods=['GET', 'POST'],
                              view_func=self.get_webodm_all_tasks)
        self.app.add_url_rule('/<int:report_id>/prepare_download', methods=['GET', 'POST'],
                              view_func=self.download_prepare_project)
        self.app.add_url_rule('/<int:report_id>/prepare_download_slam', methods=['GET', 'POST'],
                              view_func=self.download_prepare_slam_project)
        self.app.add_url_rule('/<int:report_id>/download', methods=['GET', 'POST'],
                              view_func=self.download_project)
        self.app.add_url_rule('/<int:report_id>/export_nerf', methods=['POST', 'GET'],
                              view_func=self.export_db_to_nerf)
        self.app.add_url_rule('/<int:report_id>/is_export_finished', methods=['POST', 'GET'],
                              view_func=self.nerf_export_finished)
        self.app.add_url_rule('/import_project', methods=['GET', 'POST'],
                              view_func=self.import_project)
        self.app.add_url_rule('/ir_temp_data_of_image/<int:report_id>', methods=['GET', 'POST'],
                              view_func=self.get_ir_temp_data_of_image)
        self.app.add_url_rule("/get_slam_map/<int:report_id>", methods=['GET', 'POST'],
                              view_func=self.get_slam_map)
        self.app.add_url_rule('/poi_test',
                              view_func=self.render_poi_test)
        self.app.add_url_rule('/set_IAIS_settings', methods=['POST'],
                                view_func=self.set_IAIS_settings)
        self.app.add_url_rule('/test_POI', methods=['POST'],
                                view_func=self.test_POI)
        self.app.add_url_rule('/get_poi_list', methods=['GET'],
                                view_func=self.get_POI_list)
        self.app.add_url_rule('/delete_poi', methods=['POST'],
                                view_func=self.delete_POI)

    def projects_overview(self):
        projects_dict_list = self.project_manager.get_projects()
        order_by_flight_date = self.calculate_order_based_on_flight_date(projects_dict_list)
        return render_template('projectsOverview.html', projects=projects_dict_list, flightOrder=order_by_flight_date)

    def create_report(self):
        name = request.form.get("name")
        description = request.form.get("description")
        type = request.form.get("report-type")
        if type == "mapping":
            self.project_manager.create_project(name, description)
        elif type == "slam":
            self.project_manager.create_slam_project(name, description)
        projects_dict_list = self.project_manager.get_projects()
        order_by_filght_date = self.calculate_order_based_on_flight_date(projects_dict_list)
        return render_template('projectsOverview.html', projects=projects_dict_list, flightOrder=order_by_filght_date)

    def delete_report(self, report_id):
        self.project_manager.delete_project(report_id)
        return self.projects_overview()

    def render_report(self, report_id):
        print("upload_form for id: " + str(report_id), flush=True)
        if (self.project_manager.has_project(report_id)):
            if self.project_manager.get_project(report_id)['type'] == "mapping_project":
                if not self.project_manager.get_project(report_id)['data']['flight_data']:
                    # file_names = project_manager.get_project(report_id)['data']['file_names']
                    return self.render_standard_report(report_id, template='simpleUpload.html')
                    # return render_standard_report(report_id, template='startProcessing.html')
                return self.render_standard_report(report_id)
            elif self.project_manager.get_project(report_id)['type'] == "slam_project":
                if  len(self.project_manager.get_project(report_id)['data']['keyframes']) > 0:
                    return self.render_slam_report(report_id, template='stella_vslam_report.html')
                elif len(self.project_manager.get_project(report_id)['data']['video']) > 0:
                    return self.render_slam_report(report_id, template='stella_vslam_upload.html')
                elif (len(self.project_manager.get_project(report_id)['data']['insv1']) + len(self.project_manager.get_project(report_id)['data']['insv2']))> 0:
                    return self.render_slam_insv_upload(report_id, template='stella_vslam_upload_insv.html')
                else:
                    return self.render_slam_report(report_id, template='stella_vslam_upload.html')
        else:
            projects_dict_list = self.project_manager.get_projects()
            order_by_filght_date = self.calculate_order_based_on_flight_date(projects_dict_list)
            return render_template('projectsOverview.html', projects=projects_dict_list,
                                   message="Report does not exist", flightOrder=order_by_filght_date)

    def render_report_update(self, report_id):
        print("upload_form for id: " + str(report_id), flush=True)
        if (self.project_manager.has_project(report_id)):
            if self.project_manager.get_project(report_id)['type'] == "slam_project":
                try:
                    keyfrms = self.project_manager.get_keyframe_file_path(report_id)
                    landmarks = self.project_manager.get_landmark_file_path(report_id)
                    return self.render_slam_report(report_id, template='stella_vslam_upload.html')
                except:
                    return self.render_slam_report(report_id, template='stella_vslam_upload.html')
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
            save_path = os.path.join(self.project_manager.projects_path, str(report_id), filename)
            file_names.append(save_path)
            file.save(save_path)
        else:
            flash('Allowed image types are -> png, jpg, jpeg, gif')
            return json.dumps({'success': False}), 415, {'ContentType': 'application/json'}

        self.project_manager.update_file_names(report_id, file_names)
        self.project_manager.set_unprocessed_changes(report_id, True)
        self.project_manager.append_unprocessed_images(report_id, file_names)

        thread = FilterThread(save_path, report_id)
        self.image_filter_threads.append(thread)
        thread.start()

        return json.dumps({'success': True, 'path': save_path}), 200, {'ContentType': 'application/json'}

    #handles the backend video file upload by dropzone, checks if it has the correct type and saves it with the project manager
    #also handles the insv file, and saves it
    def upload_video_file_dropzone(self, report_id):
        print("upload_video_file_dropzone " + str(report_id), flush=True)
        if 'video' not in request.files:
            print('no "video" found in request.files:', request.files, flush=True)
            return json.dumps({'success': False}), 418, {'ContentType': 'application/json'}
        file = request.files['video']
        file_name = []
        if file and self.allowed_video_file(file.filename):
            filename = secure_filename(file.filename)
            save_path = os.path.join(self.project_manager.projects_path, str(report_id), filename)
            file_name.append(save_path)
            file.save(save_path)
        else:
            if file and self.allowed_insv_file(file.filename):
                # invisi file got uploaded, so we open a new html page for stitching the two videos together owo
                filename = secure_filename(file.filename)
                save_path = os.path.join(self.project_manager.projects_path, str(report_id), filename)
                file_name.append(save_path)
                file.save(save_path)
                self.project_manager.set_insv_file(report_id, file_name)
                return json.dumps({'success': True, 'path': save_path}), 200, {'ContentType': 'application/json'}
            else:
                flash('Allowed video types are -> mp4')
                return json.dumps({'success': False}), 415, {'ContentType': 'application/json'}

        self.project_manager.set_video_file(report_id, file_name)

        return json.dumps({'success': True, 'path': save_path}), 200, {'ContentType': 'application/json'}

    #insv1 file upload for the stella_vslam_upload_insv.html saves it with the project manager
    def upload_insv1_file_dropzone(self, report_id):
        print("upload_insv1_file_dropzone " + str(report_id), flush=True)
        if 'insv1' not in request.files:
            print('no "insv" found in request.files:', request.files, flush=True)
            return json.dumps({'success': False}), 418, {'ContentType': 'application/json'}
        file = request.files['insv1']
        file_name = []
        if self.project_manager.already_has_insv_file(report_id, file.filename):
            print('file already uploaded', request.files, flush=True)
            return json.dumps({'success': False}), 418, {'ContentType': 'application/json'}
        if file and self.allowed_insv_file(file.filename):
            filename = secure_filename(file.filename)
            save_path = os.path.join(self.project_manager.projects_path, str(report_id), filename)
            file_name.append(save_path)
            file.save(save_path)
        else:
            flash('Allowed video types are -> insv')
            return json.dumps({'success': False}), 415, {'ContentType': 'application/json'}

        self.project_manager.set_insv1_file(report_id, file_name)

        return json.dumps({'success': True, 'path': save_path}), 200, {'ContentType': 'application/json'}

    #insv2 file upload for the stella_vslam_upload_insv.html saves it with the project manager
    def upload_insv2_file_dropzone(self, report_id):
        print("upload_insv2_file_dropzone " + str(report_id), flush=True)
        if 'insv2' not in request.files:
            print('no "insv" found in request.files:', request.files, flush=True)
            return json.dumps({'success': False}), 418, {'ContentType': 'application/json'}
        file = request.files['insv2']
        file_name = []
        if self.project_manager.already_has_insv_file(report_id, file.filename):
            print('file already uploaded', request.files, flush=True)
            return json.dumps({'success': False}), 418, {'ContentType': 'application/json'}
        if file and self.allowed_insv_file(file.filename):
            filename = secure_filename(file.filename)
            save_path = os.path.join(self.project_manager.projects_path, str(report_id), filename)
            file_name.append(save_path)
            file.save(save_path)
        else:
            flash('Allowed video types are -> insv')
            return json.dumps({'success': False}), 415, {'ContentType': 'application/json'}

        self.project_manager.set_insv2_file(report_id, file_name)

        return json.dumps({'success': True, 'path': save_path}), 200, {'ContentType': 'application/json'}

    #upload mask file stores it with the project manager
    def upload_mask_file(self, report_id):
        print("upload_mask_file " + str(report_id))
        if 'maskfile' not in request.files:
            print('no "mask" found in request.files:', request.files)
            return json.dumps({'success': False}), 418, {'ContentType': 'application/json'}
        file = request.files['maskfile']
        file_name = []
        if file and self.allowed_file(file.filename):
            filename = secure_filename(file.filename)
            save_path = os.path.join(self.project_manager.projects_path, str(report_id), filename)
            file_name.append(save_path)
            file.save(save_path)
        else:
            flash('Allowed mask types are -> png')
            return json.dumps({'success': False}), 415, {'ContentType': 'application/json'}

        self.project_manager.set_mask_file(report_id, file_name)  # maybe create a thread to read video file metadata

        return json.dumps({'success': True, 'path': save_path}), 200, {'ContentType': 'application/json'}

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
                self.project_manager.delete_image_object(report_id, filename, rgb=True)
                return 'File deleted successfully.'

            if self.delete_file_in_folder(report_id, filename, "/ir/"):
                self.project_manager.delete_image_object(report_id, filename, ir=True)
                return 'File deleted successfully.'

            if self.delete_file_in_folder(report_id, filename, "/panos/"):
                self.project_manager.delete_image_object(report_id, filename, pano=True)
                return 'File deleted successfully.'

            return 'File not found.'

        else:
            return 'Invalid request.'

    #function to delete the video file in files and project manager
    def delete_video_file(self, report_id):
        data = request.get_json()
        project = self.project_manager.get_project(report_id)
        video_file = project['data']['video']
        print(video_file, flush=True) #type list
        print("len of file_names: ", len(video_file))
        if video_file:

            if self.delete_video_file_in_folder(report_id, video_file[0]):
                return 'File deleted successfully.'

            return 'File not found.'

        else:
            return 'Invalid request.'

    # function to delete the mask file in files and project manager
    def delete_mask_file(self, report_id): #fix the delete methods on the server py and project manager
        data = request.get_json()
        project = self.project_manager.get_project(report_id)
        config_file = project['data']['mask']
        self.project_manager.set_unprocessed_changes(report_id, True)
        print("len of file_names: ", len(config_file))
        if config_file:

            if self.delete_mask_file_in_folder(report_id, config_file[0]):
                return 'File deleted successfully.'

            return 'File not found.'

        else:
            return 'Invalid request.'

    # function to delete the insv1 file in files and project manager
    def delete_insv1_file(self, report_id):
        data = request.get_json()
        project = self.project_manager.get_project(report_id)
        insv1_file = project['data']['insv1']
        self.project_manager.set_unprocessed_changes(report_id, True)
        print("len of file_names: ", len(insv1_file))
        if insv1_file:
            if self.delete_insv1_file_in_folder(report_id, insv1_file[0]):
                return 'File deleted successfully.'
            return 'File not found.'
        else:
            return 'Invalid request.'

    # function to delete the insv2 file in files and project manager
    def delete_insv2_file(self, report_id):
        data = request.get_json()
        project = self.project_manager.get_project(report_id)
        insv2_file = project['data']['insv2']
        self.project_manager.set_unprocessed_changes(report_id, True)
        print("len of file_names: ", len(insv2_file))
        if insv2_file:
            if self.delete_insv2_file_in_folder(report_id, insv2_file[0]):
                return 'File deleted successfully.'
            return 'File not found.'
        else:
            return 'Invalid request.'

    def check_upload_processing_progress(self, report_id):
        print('asking for upload progress of report ' + str(report_id))
        done = True
        done_threads = []
        rgb_images = []
        ir_images = []
        pano_images = []
        path_changes = {}

        for thread in self.image_filter_threads:
            if thread.report_id != report_id:
                print("-! thread not for this report, skipping", flush=True)
                continue

            if thread.done:
                old_path, new_path = thread.get_old_and_new_path()
                self.project_manager.update_single_file_path(report_id, old_path, new_path)
                path_changes[old_path] = new_path

                ir, pano, image = thread.get_result()
                done_threads.append(thread)
                if ir:
                    ir_images.append(image)
                elif pano:
                    pano_images.append(image)
                else:
                    rgb_images.append(image)
            else:
                done = False

        for thread in done_threads:
            self.image_filter_threads.remove(thread)

        self.project_manager.add_image_objects(report_id, rgb_images, ir_images, pano_images)

        if done:
            # self.project_manager.set_unprocessed_changes(report_id, False)
            # self.project_manager.update_contains_unprocessed_images(report_id, False)
            n_rgb = self.project_manager.get_image_objects_rgb_count(report_id)
            n_ir = self.project_manager.get_image_objects_ir_count(report_id)
            n_pano = self.project_manager.get_image_objects_panos_count(report_id)
            ir_readable = True
            if n_ir > 0:
                ir_readable = self.thermal_analyser.are_settings_extractable(
                    self.project_manager.get_image_objects_ir(report_id)[0].get_image_path())

            return jsonify(
                {'done': done, "dataSummary": {"rgb": n_rgb, "ir": n_ir, "panos": n_pano, "ir_readable": ir_readable},
                 "pathChanges": path_changes})

        return jsonify({'done': done, "dataSummary": {}, "pathChanges": path_changes})

    def check_upload_processing_progress_slam(self, report_id):  #fix method
        print('asking for upload progress of report ' + str(report_id))
        done = True
        done_threads = []
        video = []
        mask = []
        video_metadata = {}
        project = self.project_manager.get_project(report_id)
        data = project["data"]
        if data["video"]:
            video = data["video"]
            video_metadata = data["video_metadata"]
        if data['mask']:
            mask = data["mask"]
        return jsonify({'done': done, "dataSummary": {}, "video": video, "mask": mask})

    def check_upload_processing_progress_insv(self, report_id):
        insv1 = []
        insv2 = []
        project = self.project_manager.get_project(report_id)
        data = project["data"]
        if data["insv1"]:
            insv1 = data["insv1"]
        if data["insv2"]:
            insv2 = data["insv2"]
        return jsonify({'insv1': insv1, "insv2": insv2})

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

            print("initial_process " + str(report_id), "with_mapping: " + str(with_mapping),
                  "with_odm: " + str(with_odm),
                  "ai_detection: " + str(ai_detection), "map_resolution: " + str(map_resolution))

            thread = MapperThread(self.project_manager, self.webodm_manager, with_mapping, with_odm, report_id,
                                  (max_width, max_height), file_names, data)
            self.threads.append(thread)
            thread.start()
            print("process started")
            return jsonify(thread.get_progress_preprocess())

    #the method to start slam, it will tell the slam_manager to start slam, which will tell the slam container to execute the script with the correct parameters
    def start_slam(self, report_id):
        if request.method == 'POST':
            no_sleep = request.form.get('no_sleep')
            frame_skip = request.form.get('frame_skip')
            keyframe_chooser = request.form.get('keyframe-chooser')
            print(keyframe_chooser, flush=True)
            generate_overview_map = request.form.get('generate_overview_map')
            update_frequency = int(request.form.get('update_frequency'))
            no_sleep = True if no_sleep is not None else False
            slam_settings = {"no_sleep": no_sleep, "frame_skip": frame_skip, "keyframe-profile": keyframe_chooser}
            generate_map = True if generate_overview_map is not None else False
            self.project_manager.set_slam_settings(report_id, slam_settings)
            self.project_manager.set_mapping_settings(report_id, generate_overview_map)
            # set generate map settings with project manager

            # load default file from static and add it to project folder
            self.project_manager.add_default_orb_vocab(report_id)

            # generates config file from video metadata (and settings later)
            if not self.project_manager.generate_config_file(report_id):
                return jsonify("something went wrong")

            # set or link orb vocab file from static

            project = self.project_manager.get_project(report_id)
            data = project['data']

            print("starting slam " + str(report_id), "no sleep: " + str(no_sleep),
                  "frame_skip: " + str(frame_skip), flush=True)

            print(self.project_manager.get_keyframe_file_path(report_id), flush=True)
            print(self.project_manager.get_landmark_file_path(report_id), flush=True)
            print(self.project_manager.get_slam_output_file_path(report_id), flush=True)
            print(self.project_manager.get_map_db_folder(report_id) + str(report_id) + ".db", flush=True)

            # slam thread or smth
            self.slam_manager.start_slam(report_id=report_id,
                                         video=data["video"],
                                         orb_vocab=data["orb_vocab"],
                                         config=data["config"],
                                         mask=data["mask"],
                                         slam_options={"no_sleep": no_sleep, "frame_skip": frame_skip},
                                         other_options={"generate_overview_map": generate_overview_map,
                                                        "update_frequency": update_frequency},
                                         keyfrm_path=self.project_manager.get_keyframe_file_path(report_id),
                                         landmark_path=self.project_manager.get_landmark_file_path(report_id),
                                         keyfrm_folder_path=self.project_manager.get_keyframe_folder(report_id),
                                         map_db_output=self.project_manager.get_map_db_folder(report_id) + str(
                                             report_id) + ".db",
                                         slam_output_path=self.project_manager.get_slam_output_file_path(report_id))
        return jsonify(
            "null")  # self.render_slam_report(report_id, start_slam=True, template='stella_vslam_upload.html');

    #method to start the stitcher with the two insv files and a default output option, also copies calibration files to the project
    # with project_manager.add_default_stitcher_config
    def start_stitcher(self, report_id):
        if request.method == 'POST':
            project = self.project_manager.get_project(report_id)
            data = project['data']
            insv1 = data["insv1"]
            insv2 = data["insv2"]
            if "_00_" in insv1[0]:
                insvFront = insv1[0]
                insvBack = insv2[0]
            else:
                insvFront = insv2[0]
                insvBack = insv1[0]
            input_videos = [insvFront, insvBack]

            output_video = self.project_manager.get_default_stitcher_video_name(report_id)

            self.project_manager.add_default_stitcher_config(report_id)

            print("starting stitcher " + str(report_id), flush=True)

            stitcher_calibration = data['stitcher_config'][0]

            #slam thread or smth
            self.slam_manager.start_stitcher(report_id=report_id,
                input_videos = input_videos, output_video=output_video,
                stitcher_calibration=stitcher_calibration)
        return jsonify("null") #self.render_slam_report(report_id, start_slam=True, template='stella_vslam_upload.html');

    def slam_map_update(self):
        data = request.get_json()
        report_id = data["report_id"]
        map_msg = data["map_publish"]
        print(report_id)
        return jsonify("null")

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
                    self.project_manager.update_panos(report_id, panos)
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

    #function that checks the progress of the mapping thread for vslam
    def check_slam_map_process_status(self, report_id):
        progress = -1
        for thread in self.threads:
            if thread.report_id == report_id:
                progress_preprocess = thread.get_progress_preprocess()
                progress_mapping = thread.get_progress_mapping()
                overallprogress = (progress_preprocess * 0.8) + (progress_mapping * 0.2) #progress between 0 and 1
                trajectory = thread.get_saved_trajectory_result()
                mapping_result = thread.get_saved_mapping_result()
                vertices = thread.get_vertices_json()
                if(progress_mapping == 1):
                    #add and load mapping results
                    trajectory = thread.get_saved_trajectory_result()
                    mapping_result = thread.get_saved_mapping_result()
                    vertices = thread.get_vertices_json()
                    print(mapping_result, flush=True)
                    self.project_manager.update_mapping_result(report_id, mapping_result, trajectory, vertices)
                    print('mapping done')
                break
        result = {"progress": overallprogress, "mapping_result": mapping_result, "trajectory": trajectory, "vertices": vertices}
        return jsonify(result)

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
                    map["file_url"] = map["file"]
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
        print("update_ir_settings for id" + str(report_id) + " with: " + str(settings), flush=True)
        self.project_manager.update_ir_settings_from_website(report_id, settings)
        return "success"

    def send_gradient_lut(self, gradient_id):
        lut = json.load(open("./static/default/gradient_luts/gradient_lut_" + str(gradient_id) + ".json"))
        return lut

    def get_ir_temp_data_of_image(self, report_id):
        filename = request.form.get('filename')
        print("get_ir_temp_data_of_image for id" + str(report_id) + " with: " + str(filename), flush=True)
        temp_matrix = self.thermal_analyser.get_image_temp_matrix(report_id, filename)
        temperature_matrix = temp_matrix.tolist()
        return jsonify({'temperature_matrix': temperature_matrix})

    def run_detection(self, report_id):
        numbr_of_models = 2
        models_setting = request.form.get('model_options')
        if models_setting == "all":
            numbr_of_models = 5
        elif models_setting == "medium":
            numbr_of_models = 3

        processing_setting = request.form.get('processing_options')
        print("run_detection for id" + str(report_id) + " with: " + str(numbr_of_models) + " models and " + str(
            processing_setting) + " processing")
        split_images = False
        max_splits = 0
        print(f'processing_setting: {processing_setting}')
        if processing_setting != "full":
            max_splits = 99
            if processing_setting == "one_split":
                max_splits = 1

        print(self.project_manager.project_path(report_id), flush=True)
        print(self.project_manager.get_annotation_file_path(report_id), flush=True)
        if self.project_manager.get_project(report_id)['type'] == "mapping_project":
            self.detection_manager.detect_objects(options={"numbr_of_models": numbr_of_models, "max_splits": max_splits},
                                              report_id=report_id,
                                              image_folder=self.project_manager.project_path(report_id),
                                              ann_path=self.project_manager.get_annotation_file_path(report_id))
        if self.project_manager.get_project(report_id)['type'] == "slam_project":
            self.detection_manager.detect_objects_slam(options={"numbr_of_models": numbr_of_models, "max_splits": max_splits},
                                                report_id=report_id,
                                                image_folder=self.project_manager.get_keyframe_folder(report_id),
                                                ann_path=self.project_manager.get_annotation_file_path(report_id))

        return jsonify("null")  #detections

    def update_detections_colors(self, report_id):
        color = [request.form.get('colorH'), request.form.get('colorS'), request.form.get('colorL')]
        category_name = request.form.get('category_name')
        print(request.form)
        print(
            "update_detections_colors for id" + str(report_id) + " with: " + str(color) + " and category_name: " + str(
                category_name))
        self.project_manager.update_detections_colors(report_id, color, category_name)
        return "success"

    def check_detection_status(self, report_id):
        print('asking for detection status of report ' + str(report_id) + " with " + str(
            len(self.detection_threads)) + " threads")
        return self.detection_manager.get_detection_status(report_id)

    def check_slam_status(self, report_id):
        status = self.slam_manager.get_slam_status(report_id)
        if status[0] == "finished":
            try:
                keyfrms = self.project_manager.get_keyframe_file_path(report_id)
                landmarks = self.project_manager.get_landmark_file_path(report_id)
                keyfrm_folder = self.project_manager.get_keyframe_folder(report_id)
                output = self.project_manager.get_mapping_output_folder(report_id)
                self.project_manager.load_keyframe_images(report_id)
                mapping_settings = self.project_manager.get_mapping_settings(report_id)
                #start image mapper thread stuff
                if mapping_settings is not None:
                    extensions = ['.jpg', '.png']
                    fov = [80,80]
                    print("starting mapping process", flush=True)
                    thread = ImageMapperProcess(keyfrm_folder, output, extensions, fov, keyfrms, report_id)
                    self.threads.append(thread)
                    thread.start()
                return jsonify(status=status)
            except:
                return jsonify(status=status)
        if status[0] == "update":
            try:
                keyfrms = self.project_manager.get_keyframe_file_path(report_id)
                landmarks = self.project_manager.get_landmark_file_path(report_id)
                return jsonify(status=status,keyframes=keyfrms, landmarks=landmarks)
            except:
                return jsonify("something went wrong with slam")
        return jsonify(status=status)

    def check_stitcher_status(self, report_id):
        status = self.slam_manager.get_stitcher_status(report_id)
        return jsonify(status=status)

    def load_video_from_stitcher(self, report_id):
        success = self.project_manager.load_video_from_stitcher(report_id)
        return jsonify(success=success)

    def export_db_to_nerf(self, report_id):
        if self.project_manager.load_map_db_file(report_id):
            #create output folder for nerf export
            map_db = self.project_manager.get_map_db(report_id)
            output_folder = self.project_manager.get_nerf_export_folder(report_id)
            args = "./export/export_sqlite3_to_nerf.py " + map_db[0] + " " + output_folder
            export_thread = {'report_id': report_id, 'done': False}
            self.export_threads.append(export_thread)
            popen_and_call(self.on_export_db_to_nerf_finish, report_id, args.split())
            result = {"success": True}
            return jsonify(result)
        else:
            result = {"success": False}
            return jsonify(result)

    def on_export_db_to_nerf_finish(self, report_id):
        for export_thread in self.export_threads:
            if export_thread['report_id'] == report_id:
                export_thread['done'] = True
        print(self.export_threads, flush=True)

    def nerf_export_finished(self, report_id):
        result = None
        for i, export_thread in enumerate(self.export_threads):
            if export_thread['report_id'] == report_id:
                if export_thread['done']:
                    result = {"thread_found": True, "finished": True}
                    break
                else:
                    result = {"thread_found": True, "finished": False}
                    break
        if result is not None:
            if result["finished"]:
                self.export_threads.pop(i)
            return jsonify(result)
        result = {"thread_found": False, "finished": False}
        return jsonify(result)

    def get_slam_map(self, report_id):
        print('asking for slam map of report ' + str(report_id))
        return self.slam_manager.get_slam_map(report_id)

    def delete_annotation(self, report_id):
        annotation_id = request.form.get('annotation_id')
        print("delete_annotation for id" + str(report_id) + " with: " + str(annotation_id), flush=True)
        self.project_manager.delete_annotation(report_id, annotation_id)
        return "success"

    def edit_annotation(self, report_id):
        print("complete request form: " + str(request.form), flush=True)
        annotation_id = request.form.get('annotation_id')
        category_id = request.form.get('category_id')
        annotation_bbox = request.form.get('annotation_bbox')
        annotation_bbox = json.loads(annotation_bbox)
        print("edit_annotation for id" + str(report_id) + " with: " + str(annotation_id) + " and " + str(category_id) + " and " + str(annotation_bbox), flush=True)
        self.project_manager.edit_annotation(report_id, annotation_id, category_id, annotation_bbox)
        return "success"

    def edit_annotation_type(self, report_id):
        annotation_id = request.form.get('annotation_id')
        category_id = request.form.get('category_id')
        print("edit_annotation_type for id" + str(report_id) + " with: " + str(annotation_id) + " and " + str(category_id), flush=True)
        self.project_manager.edit_annotation_category(report_id, annotation_id, category_id)
        return "success"

    def add_annotation(self, report_id):
        annotation_class = int(request.form.get('annotation_class'))
        annotation_bbox = request.form.get('annotation_bbox')
        #convert string to list
        annotation_bbox = json.loads(annotation_bbox)
        annotation_imageid = int(request.form.get('annotation_imageid'))
        #parse string to int
        annotation_imageid = int(annotation_imageid)
        print("add_annotation for id" + str(report_id) + " with: " + str(annotation_class), flush=True)
        ann_id = self.project_manager.add_annotation(report_id, annotation_class, annotation_bbox, annotation_imageid)
        #return the id of the new annotation and success
        return jsonify({"success": True, "annotation_id": ann_id})
        #return "success"

    def load_detection_results(self, report_id):
        #get path of projects annotation file
        path = self.project_manager.get_annotation_file_path(report_id)
        #load results from json file located under /detections/results
        with open(path) as json_file:
            data = json.load(json_file)
            #print(data)
            return jsonify(data)

    def load_keyframes(self, report_id):
        #get path of projects annotation file
        path = self.project_manager.get_keyframe_file_path(report_id)
        #load results from json file
        with open(path) as json_file:
            data = json.load(json_file)
            return jsonify(data)

    def load_landmarks(self, report_id):
        #get path of projects annotation file
        path = self.project_manager.get_landmark_file_path(report_id)
        #load results from json file
        with open(path) as json_file:
            data = json.load(json_file)
            return jsonify(data)

    def load_vertices(self, report_id):
        #get path of projects annotation file
        data = self.project_manager.get_project(report_id)['data']
        mapping_output = data['mapping_output']
        try:
            vertices = mapping_output[2]
            with open(vertices) as json_file:
                vertices_data = json.load(json_file)
                return jsonify(vertices_data)
        except:
            return jsonify("error")

    def process_in_webodm(self, report_id):
        token = self.webodm_manager.authenticate()
        if token is None:
            return jsonify({"success": False})

        wo_project_id = None
        try:
            wo_project_id = self.project_manager.get_webodm_project_id(report_id)
            if not self.webodm_manager.project_exists(token, wo_project_id):
                wo_project_id = self.webodm_manager.create_project(token,
                                                                   self.project_manager.get_project_name(report_id),
                                                                   self.project_manager.get_project_description(
                                                                       report_id))
        except:
            wo_project_id = self.webodm_manager.get_project_id(token, self.project_manager.get_project_name(report_id),
                                                               self.project_manager.get_project_description(report_id))
            if wo_project_id is None:
                wo_project_id = self.webodm_manager.create_project(token,
                                                                   self.project_manager.get_project_name(report_id),
                                                                   self.project_manager.get_project_description(
                                                                       report_id))
            if wo_project_id is not None:
                self.project_manager.set_webodm_project_id(report_id, wo_project_id)

        if wo_project_id is not None:
            self.webodm_manager.upload_and_process_images(token, wo_project_id,
                                                          self.project_manager.get_file_names_rgb(report_id))
            return jsonify({"success": True, "port": self.webodm_manager.public_port})
        else:
            print("Failed to open or create a webodm project with name {}".format(
                self.project_manager.get_project_name(report_id)), flush=True)
            return jsonify({"success": False})

    def webodm_project_exists(self, report_id):
        print("webodm_project_exists for id" + str(report_id), flush=True)
        token = self.webodm_manager.authenticate()
        if token is None:
            return jsonify({"success": False})

        wo_project_id = None
        try:
            wo_project_id = str(self.project_manager.get_webodm_project_id(report_id))
            if not self.webodm_manager.project_exists(token, wo_project_id):
                return jsonify({"success": False})
        except Exception as e:
            print(e, flush=True)
            wo_project_id = self.webodm_manager.get_project_id(token, self.project_manager.get_project_name(report_id),
                                                               self.project_manager.get_project_description(report_id))
            if wo_project_id is not None:
                self.project_manager.set_webodm_project_id(report_id, wo_project_id)

        if wo_project_id is None:
            return jsonify({"success": False})
        else:
            return jsonify({"success": True, "project_id": wo_project_id, "port": self.webodm_manager.public_port})

    def get_webodm_port(self):
        return jsonify({"port": self.webodm_manager.public_port})

    def get_webodm_last_task(self, report_id):
        token = self.webodm_manager.authenticate()
        if token is None:
            return jsonify({"success": False})

        wo_project_id = None
        try:
            wo_project_id = self.project_manager.get_webodm_project_id(report_id)
            if not self.webodm_manager.project_exists(token, wo_project_id):
                return jsonify({"success": False})
        except:
            wo_project_id = self.webodm_manager.get_project_id(token, self.project_manager.get_project_name(report_id),
                                                               self.project_manager.get_project_description(report_id))
            if wo_project_id is not None:
                self.project_manager.set_webodm_project_id(report_id, wo_project_id)

        if wo_project_id is None:
            return jsonify({"success": False})
        else:
            id = self.webodm_manager.get_last_task_data(token, wo_project_id, "id")
            print("wo_project_id: " + str(wo_project_id) + " - id: " + str(id), flush=True)
            return jsonify(
                {"success": True, "project_id": wo_project_id, "task_id": id, "port": self.webodm_manager.public_port})

    def get_webodm_all_tasks(self, report_id):
        token = self.webodm_manager.authenticate()
        if token is None:
            return jsonify({"success": False})

        wo_project_id = None
        try:
            wo_project_id = self.project_manager.get_webodm_project_id(report_id)
            if not self.webodm_manager.project_exists(token, wo_project_id):
                return jsonify({"success": False})
        except:
            wo_project_id = self.webodm_manager.get_project_id(token, self.project_manager.get_project_name(report_id),
                                                               self.project_manager.get_project_description(report_id))
            if wo_project_id is not None:
                self.project_manager.set_webodm_project_id(report_id, wo_project_id)

        if wo_project_id is None:
            return jsonify({"success": False})

        tasks = self.webodm_manager.get_all_tasks(token, wo_project_id)
        return jsonify({"success": True, "tasks": tasks})

    def download_prepare_project(self, report_id):
        download_package = request.form.get('export-chooser')
        print("download_package: " + str(download_package), flush=True)
        print(request.form, flush=True)
        zip_name = None
        zip_path = None

        if download_package == 'project_export':
            #send the whole project folder as a zip file
            zip_path = self.project_manager.generate_project_zip(report_id)
            zip_name = os.path.basename(zip_path)
            print("zip_path: " + str(zip_path), flush=True)
        elif download_package == 'maps':
            zip_path = self.project_manager.generate_maps_zip(report_id)
            zip_name = os.path.basename(zip_path)
        elif download_package == 'pdf':
            #TODO: generate pdf
            pass

        if zip_path is not None:
            return jsonify({"success": True, "zip_name": zip_name, "zip_path": zip_path})
        else:
            return jsonify({"success": False})

    def download_prepare_slam_project(self, report_id):
        download_package = request.form.get('export-chooser')
        print("download_package: " + str(download_package), flush=True)
        print(request.form, flush=True)
        zip_name = None
        zip_path = None

        if download_package == 'project_export':
            #send the whole project folder as a zip file
            zip_path = self.project_manager.generate_project_zip(report_id)
            zip_name = os.path.basename(zip_path)
            print("zip_path: " + str(zip_path), flush=True)
        elif download_package == 'keyframes':
            zip_path = self.project_manager.generate_keyframes_zip(report_id)
            zip_name = os.path.basename(zip_path)
        elif download_package == 'map':
            zip_path = self.project_manager.generate_slam_map_zip(report_id)
            if zip_path is not None:
                zip_name = os.path.basename(zip_path)
        elif download_package == 'nerf':
            zip_path = self.project_manager.generate_slam_nerf_export_zip(report_id)
            if zip_path is not None:
                zip_name = os.path.basename(zip_path)

        if zip_path is not None:
            return jsonify({"success": True, "zip_name": zip_name, "zip_path": zip_path})
        else:
            return jsonify({"success": False})


    def download_project(self, report_id):
        file_name = request.form.get('filename')
        path = request.form.get('path')
        print("download_project: " + str(file_name) + " - " + str(path), flush=True)
        if file_name and path:
            return send_file(path, as_attachment=True, download_name=file_name)
        else:
            return jsonify({"success": False})

    def import_project(self):
        file = request.files['import-file']
        if file and self.allowed_file_project(file.filename):
            # create a new project and empty folder for the project with a new id
            id = self.project_manager.initialize_project_from_import()

            # paste zip file into the empty folder
            save_path = os.path.join(self.project_manager.projects_path, str(id), file.filename)
            file.save(save_path)

            # check if the zip file contains a project.json file
            if self.project_manager.contains_project_json(id, save_path):
                # if yes, load the project.json file and update the project with the data from the file
                try:
                    self.project_manager.import_project(id)
                    return redirect(url_for('render_report', report_id=id), code=301)
                except Exception as e:
                    #get exception
                    return "failed to import project, error: " + str(e), 422
            else:
                return "failed to import project, no project.json file found", 415
        else:
            return "failed to import project, no zip file found", 404

    def display_image(self, filename):
        return redirect(self.global_for(filename), code=301)

    def global_for(self, path):
        if path.startswith("./"):
            return path[1:]
        elif path.startswith("/"):
            return path
        else:
            return "/" + path

    def thumbnail_for(self, path):
        thumbnail_path = os.path.join(os.path.dirname(path), 'thumbnails', os.path.basename(path))
        if not os.path.isfile(thumbnail_path):
            thumbnail_path = path
        return thumbnail_path

    def generate_id_for_image(self, filename):
        return redirect(url_for(self.project_manager.local_projects_path, filename=filename), code=301)

    def shutdown(self):
        print("Server shutting down...")
        self.stop_server()
        return 'Server shutting down...'

    def stop_server(self):
        os.kill(os.getpid(), signal.SIGINT)

    def run(self):
        self.app.run(host=self.address, port=self.port, debug=True, use_reloader=False)

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

    def render_slam_insv_upload(self, report_id, template='stella_vslam_upload_insv.html'):
        data = self.project_manager.get_project(report_id)['data']
        insv1 = data['insv1']
        try:
            insv1_file_size = os.path.getsize(insv1[0])
        except:
            insv1_file_size = 0
        insv2 = data['insv2']
        try:
            insv2_file_size = os.path.getsize(insv2[0])
        except:
            insv2_file_size = 0
        processing = False
        message = None
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
        return render_template(template, id=report_id, insv1 = insv1, insv1_file_size = insv1_file_size,
                               insv2 = insv2, insv2_file_size = insv2_file_size,
                               project=project, message=message, gradient_lut=gradient_lut)  # create a different ren

    def render_slam_report(self, report_id, thread=None, template="stella_vslam_report.html"):  #need new slamReport.html
        data = self.project_manager.get_project(report_id)['data']
        video = data["video"]
        try:
            video_file_size = os.path.getsize(video[0])
        except:
            video_file_size = None
        mask = data["mask"]
        slam_settings = data["slam_settings"]
        keyframe_images = data["keyframes"]
        map_db = data["map_db"]
        point_cloud = data["point_cloud"]
        keyframe_folder = self.project_manager.get_keyframe_folder(report_id)
        nerf_export = self.project_manager.has_nerf_export(report_id)
        if (len(keyframe_images) > 0):
            has_keyframe_images = True
        else:
            has_keyframe_images = False

        try:
            keyfrms_path = data["keyframe_file_path"]
            keyfrms = json.load(open(keyfrms_path))
        except:
            keyfrms = None

        try:
            detections_path = data["annotation_file_path"]
            detections = json.load(open(detections_path))
        except:
            detections = None

        try:
            landmark_path = data["landmark_file_path"]
            landmarks = json.load(open(landmark_path))
        except:
            landmarks = None

        try:
            slam_output_path = data['slam_output_file_path']
            slam_output = json.load(open(slam_output_path))
        except:
            slam_output = None

        try:
            slam_mapping_output = data['mapping_output'] #mapping output
            try:
                vertices = slam_mapping_output[2]
            except:
                vertices = None
        except:
            slam_mapping_output = None

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
        return render_template(template, id=report_id, video=video, video_file_size=video_file_size, mask=mask,
                               slam_settings=slam_settings, keyframe_images=keyframe_images, map_db=map_db,
                               has_keyframe_images = has_keyframe_images,
                               keyfrms = keyfrms, landmarks=landmarks, slam_output = slam_output,
                               keyframe_folder = keyframe_folder, detections= detections, processing = processing,
                               point_cloud=point_cloud, project=project, message=message, slam_mapping_output = slam_mapping_output,
                               nerf_export=nerf_export,
                               vertices = vertices, gradient_lut=gradient_lut)  #create a different render template maybe

    def render_standard_report(self, report_id, thread=None, template="baseReport.html"):
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
                   'creation_time': self.project_manager.get_project_creation_time(report_id),
                   'ir_settings': ir_settings}
        return render_template(template, id=report_id, file_names=file_names, file_names_ir=[],
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

        ir_settings = {}
        try:
            ir_settings = data["ir_settings"]
            if ir_settings == None:
                print("ir settings are None", flush=True)
                ir_settings = {}
        except:
            print("no ir settings found", flush=True)

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
                   'creation_time': self.project_manager.get_project_creation_time(report_id),
                   'ir_settings': ir_settings}
        return render_template(template, id=report_id, project=project, file_names=file_names_upload,
                               processing=processing)

    def delete_file_in_folder(self, report_id, filename, subfolder, thumbnail=False):
        # project_path = self.project_manager.project_path(report_id)
        # file_path = os.path.join(project_path, subfolder)
        # print('project_path:', project_path, 'file_path', file_path)
        # file_path = os.path.join(file_path, filename)
        # print("trying to delete file in folder ", file_path)
        # since os.path.join does noot want to put the project_path into the path, we have to do it manually
        file_path = self.project_manager.project_path(report_id) + subfolder + filename
        if os.path.exists(file_path):
            os.remove(file_path)
            print("file deleted @" + file_path)
            if not thumbnail:
                self.project_manager.remove_from_file_names_rgb(report_id, file_path)
                self.project_manager.remove_from_file_names_ir(report_id, file_path)
                self.project_manager.remove_from_panos(report_id, file_path)
                self.project_manager.remove_from_unprocessed_images(report_id, file_path)
                self.delete_file_in_folder(report_id, filename, subfolder + "thumbnails", thumbnail=True)
            return True
        return False

    def delete_video_file_in_folder(self, report_id, filename):
        file_path = filename
        print(file_path,flush=True)
        if os.path.exists(file_path):
            os.remove(file_path)
            print("file deleted @" + file_path)
            self.project_manager.remove_from_file_name_video(report_id, file_path)
            return True
        return False

    def delete_mask_file_in_folder(self, report_id, filename):
        file_path = filename
        if os.path.exists(file_path):
            os.remove(file_path)
            print("file deleted @" + file_path)
            self.project_manager.remove_from_file_name_mask(report_id, file_path)
            return True
        return False

    def delete_insv1_file_in_folder(self, report_id, filename):
        file_path = filename
        if os.path.exists(file_path):
            os.remove(file_path)
            print("file deleted @" + file_path)
            self.project_manager.remove_from_file_name_insv1(report_id, file_path)
            return True
        return False

    def delete_insv2_file_in_folder(self, report_id, filename):
        file_path = filename
        if os.path.exists(file_path):
            os.remove(file_path)
            print("file deleted @" + file_path)
            self.project_manager.remove_from_file_name_insv2(report_id, file_path)
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

    def allowed_video_file(self, filename):
        return '.' in filename and filename.rsplit('.', 1)[1].lower() in self.ALLOWED_VIDEO_EXTENSIONS

    def allowed_insv_file(self, filename):
        return '.' in filename and filename.rsplit('.', 1)[1].lower() in self.ALLOWED_INSV_EXTENSIONS

    def allowed_file_project(self, filename):
        return '.' in filename and filename.rsplit('.', 1)[1].lower() in self.ALLOWED_EXTENSIONS_PROJECT

    def set_IAIS_settings(self):
        data = request.get_json()
        print("set_IAIS_settings with: ", data, flush=True)
        self.data_share_manager.update_iais_connection(data["url"], data["username"], data["password"])
        return data

    def test_POI(self):
        data = request.get_json()
        print("test_POI with", data, flush=True)
        response = self.data_share_manager.send_poi_to_iais(data)
        return response

    def render_poi_test(self):
        return render_template('poi_test.html')

    def get_POI_list(self):
        return self.data_share_manager.get_all_pois_from_iais()

    def delete_POI(self):
        data = request.get_json()
        print("delete_POI with", data, flush=True)
        response = self.data_share_manager.remove_poi_from_iais(data['poi_id'])
        return response
