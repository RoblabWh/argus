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


# Über javaScript können auch nur spezifische Daten ohne komplettes render Template gesetz werden
# (kp was das ist, das hat copilot mit vorgeschlagen) https://stackoverflow.com/questions/20035101/return-json-response-from-flask-view
# (ich meinte diesen Post) https://stackoverflow.com/questions/60262827/how-can-i-pass-variable-from-flask-o-html-without-render-template

# Flask rückmeldungen für lange Berechnungen
# https://stackoverflow.com/questions/24251898/flask-app-update-progress-bar-while-function-runs

# Magnifier: https://stackoverflow.com/questions/60351972/how-can-i-show-my-magnifying-glass-only-when-i-hover-over-the-image-in-css



app = Flask(__name__)
UPLOAD_FOLDER = 'static/uploads/'
app.secret_key = "adwdwadwa-ednalan"
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 500 * 10000 * 10000

ALLOWED_EXTENSIONS = set(['png', 'jpg', 'jpeg', 'PNG', 'JPG', 'JPEG'])

threads = []
file_names = []
flight_data = []
camera_specs = []
weather = []
map = {}

path_to_images = "./static/uploads/"
projects_dict_list = []

project_manager = ProjectManager(path_to_images)
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def render_standard_report(report_id, thread = None, template = "concept.html"):
    data = project_manager.get_project(report_id)['data']
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

    has_rgb = False
    for slide in slide_file_paths:
        if slide[0] != "":
            has_rgb = True
            break

    message = None
    processing = False
    for thread in threads:
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


    project = {"id": report_id, "name": project_manager.get_project_name(report_id),
               "description": project_manager.get_project_description(report_id),
               'creation_time': project_manager.get_project_creation_time(report_id)}
    return render_template(template, id=report_id, file_names=file_names, file_names_ir=file_names_ir,
                           panos=panos, has_rgb=has_rgb, has_ir=has_ir, flight_data=flight_data,
                           slide_file_paths=slide_file_paths, camera_specs=camera_specs, weather=weather,
                           flight_trajectory=flight_trajectory, maps=maps, project=project, message=message,
                           processing=processing, gradient_lut=gradient_lut, ir_settings=ir_settings,
                           detections=detections, unprocessed_images=contains_unprocessed_images)


def calculate_order_based_on_flight_date(projects_dict_list):
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
    date_order = [times[i] for i in indices]
    print(date_order)
    print(indices)
    return indices



@app.route('/')
def projects_overview():
    projects_dict_list = project_manager.get_projects()
    order_by_filght_date = calculate_order_based_on_flight_date(projects_dict_list)
    return render_template('projectsOverview.html', projects=projects_dict_list, flightOrder=order_by_filght_date )

@app.route('/create', methods=['POST'])
def create_report():
    name = request.form.get("name")
    description = request.form.get("description")
    project_manager.create_project(name, description)
    projects_dict_list = project_manager.get_projects()
    order_by_filght_date = calculate_order_based_on_flight_date(projects_dict_list)
    return render_template('projectsOverview.html', projects=projects_dict_list, flightOrder=order_by_filght_date )

@app.route('/<int:report_id>')
def upload_form(report_id):
    print("upload_form" + str(report_id))
    if(project_manager.has_project(report_id)):
        print("Directory exists")
        if not project_manager.get_project(report_id)['data']['flight_data']:
            # file_names = project_manager.get_project(report_id)['data']['file_names']
            return render_standard_report(report_id, template='simpleUpload.html')
            # return render_standard_report(report_id, template='startProcessing.html')
        return render_standard_report(report_id)
    else:
        projects_dict_list = project_manager.get_projects()
        order_by_filght_date = calculate_order_based_on_flight_date(projects_dict_list)
        return render_template('projectsOverview.html', projects=projects_dict_list, message="Report does not exist", flightOrder=order_by_filght_date )

@app.route('/delete/<int:report_id>')
def delete_report(report_id):
    project_manager.delete_project(report_id)
    return projects_overview()

@app.route('/<int:report_id>/upload', methods=['POST'])
def upload_image(report_id):
    print("upload_image" + str(report_id))
    if 'files[]' not in request.files:
        flash('No file part')
        return redirect(request.url)
    files = request.files.getlist('files[]')
    file_names = []
    for file in files:
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file_names.append("uploads/" + str(report_id) +"/" + filename)
            file.save(os.path.join(app.config['UPLOAD_FOLDER']+str(report_id)+"/", filename))
        else:
            flash('Allowed image types are -> png, jpg, jpeg, gif')
            return redirect(request.url)
    project_manager.update_file_names(report_id, file_names)
    project_manager.append_unprocessed_images(report_id, file_names)
    files = []
    if not project_manager.get_project(report_id)['data']['flight_data']:
           # file_names = project_manager.get_project(report_id)['data']['file_names']
           return render_standard_report(report_id, template='simpleUpload.html')
        #  return render_standard_report(report_id, template='startProcessing.html')
    return render_standard_report(report_id)


@app.route('/<int:report_id>/edit', methods=['POST', 'GET'])
def edit_report(report_id):
    print("editing report " + str(report_id))
    if (project_manager.has_project(report_id)):
        print("Directory exists")
        return render_standard_report(report_id, template='simpleUpload.html')
    else:
        projects_dict_list = project_manager.get_projects()
        order_by_filght_date = calculate_order_based_on_flight_date(projects_dict_list)
        return render_template('projectsOverview.html', projects=projects_dict_list, message="Report does not exist",
                               flightOrder=order_by_filght_date)


@app.route('/<int:report_id>/uploadFile', methods=['POST'])
def upload_image_file(report_id):
    print("upload_image_file " + str(report_id))
    if 'image' not in request.files:
        print(request.files)
        #flash('No file part')
        return json.dumps({'success':False}), 418, {'ContentType':'application/json'}
    file = request.files['image']
    file_names = []

    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        file_names.append("uploads/" + str(report_id) +"/" + filename)
        file.save(os.path.join(app.config['UPLOAD_FOLDER']+str(report_id)+"/", filename))
    else:
        flash('Allowed image types are -> png, jpg, jpeg, gif')
        return json.dumps({'success':False}), 415, {'ContentType':'application/json'}
    project_manager.update_file_names(report_id, file_names)
    project_manager.append_unprocessed_images(report_id, file_names)
    files = []
    return json.dumps({'success':True}), 200, {'ContentType':'application/json'}


@app.route('/<int:report_id>/deleteFile', methods=['POST'])
def delete_file(report_id):
    data = request.get_json()
    filename = data.get('filename')
    if filename:

        if delete_file_in_folder(report_id, filename, "/"):
            return 'File deleted successfully.'

        if delete_file_in_folder(report_id, filename, "/rgb/"):
            return 'File deleted successfully.'

        if delete_file_in_folder(report_id, filename, "/ir/"):
            return 'File deleted successfully.'

        return 'File not found.'

    else:
        return 'Invalid request.'

def delete_file_in_folder(report_id, filename, subfolder, thumbnail=False):
    file_path = "uploads/" + str(report_id) + subfolder + filename
    print("trying to delete file in folder " + file_path)
    if os.path.exists('static/' + file_path):
        os.remove('static/' + file_path)
        project_manager.remove_from_file_names(report_id, file_path)
        project_manager.remove_from_unprocessed_images(report_id, file_path)
        if not thumbnail:
            delete_file_in_folder(report_id, filename, subfolder+"/thumbnails", thumbnail=True)
        return True
    return False


@app.route('/<int:report_id>/process', methods=['POST', 'GET'])
def process(report_id):
    if request.method == 'POST':
        with_mapping = request.form.get('with_mapping')
        if with_mapping == None:
            with_mapping = False
        else:
            with_mapping = True
        with_ODM = request.form.get('with_odm')
        if with_ODM == None:
            with_ODM = False
        else:
            with_ODM = True
        ai_detection = request.form.get('ai_detection')
        if ai_detection == None:
            ai_detection = False
        else:
            ai_detection = True

        #image_mapper = project_manager.get_image_mapper(report_id)

        map_resolution = request.form.get('map resolution')
        max_width, max_height = 2048, 2048
        if map_resolution == 'low':
            max_width, max_height = 1024, 1024
        elif map_resolution == 'medium':
            max_width, max_height = 2048, 2048
        elif map_resolution == 'high':
            max_width, max_height = 4096, 4096
        elif map_resolution == 'ultra':
            max_width, max_height = 6144, 6144

        file_names = project_manager.get_file_names(report_id)

        data = project_manager.get_project(report_id)['data']

        print("with_mapping: ", with_mapping)
        print("with_ODM: ", with_ODM)
        print("ai_detection: ", ai_detection)
        print("map_resolution: ", map_resolution)

        # image_mapper.set_processing_parameters(map_width_px=max_width,
        #                                        map_height_px=max_height, with_ODM=with_ODM)#, ai_detection=ai_detection)
        thread = MapperThread(with_mapping, with_ODM, report_id, (max_width, max_height), file_names, data)
        threads.append(thread)
        thread.start()
        print("process started")
        return render_standard_report(report_id, thread)


@app.route('/<int:report_id>/processFromUpload', methods=['POST', 'GET'])
def initial_proces(report_id):
    if request.method == 'POST':
        with_mapping = request.form.get('with_mapping')
        if with_mapping == None:
            with_mapping = False
        else:
            with_mapping = True
        with_ODM = request.form.get('with_odm')
        if with_ODM == None:
            with_ODM = False
        else:
            with_ODM = True
        ai_detection = request.form.get('ai_detection')
        if ai_detection == None:
            ai_detection = False
        else:
            ai_detection = True

        #image_mapper = project_manager.get_image_mapper(report_id)

        map_resolution = request.form.get('map resolution')
        max_width, max_height = 2048, 2048
        if map_resolution == 'low':
            max_width, max_height = 1024, 1024
        elif map_resolution == 'medium':
            max_width, max_height = 2048, 2048
        elif map_resolution == 'high':
            max_width, max_height = 4096, 4096
        elif map_resolution == 'ultra':
            max_width, max_height = 6144, 6144

        file_names = project_manager.get_file_names(report_id)

        data = project_manager.get_project(report_id)['data']

        print("with_mapping: ", with_mapping)
        print("with_ODM: ", with_ODM)
        print("ai_detection: ", ai_detection)
        print("map_resolution: ", map_resolution)

        # image_mapper.set_processing_parameters(map_width_px=max_width,
        #                                        map_height_px=max_height, with_ODM=with_ODM)#, ai_detection=ai_detection)
        thread = MapperThread(with_mapping, with_ODM, report_id, (max_width, max_height), file_names, data)
        threads.append(thread)
        thread.start()
        print("process started")
        return jsonify(thread.get_progress_preprocess())

@app.route('/gradient_lut/<int:gradient_id>', methods=['GET', 'POST'])
def send_gradient_lut(gradient_id):
    lut = json.load(open("./static/default/gradient_luts/gradient_lut_" + str(gradient_id) + ".json"))
    return lut

@app.route('/update_ir_settings/<int:report_id>/<string:settings>/', methods=['GET'])
def update_ir_settings(report_id, settings):
    settings = settings.split(",")
    settings = [int(i) for i in settings]
    project_manager.update_ir_settings_from_website(report_id, settings)
    print("update_ir_settings for id"+ str(report_id) + " with: " + str(settings))
    return "success"

@app.route("/update_description/<int:report_id>", methods=['POST'])
def update_description(report_id):
    description = request.form.get('content')
    print("update_description for id"+ str(report_id) + " with: " + str(description))
    description = process_html_strings(description)
    project_manager.update_description(report_id, description)
    return "success"

@app.route("/update_title/<int:report_id>", methods=['POST'])
def update_title(report_id):
    title = request.form.get('content')
    print("update_title for id"+ str(report_id) + " with: " + str(title))
    title = process_html_strings(title, no_newline=True)
    project_manager.update_title_name(report_id, title)
    return "success"

def process_html_strings(html_string, no_newline=False):
    html_string = html_string.replace("\n", "")
    html_string = html_string.strip()
    if no_newline:
        html_string = html_string.replace("<br>", "")
    else:
        html_string = html_string.replace("<br>", "\n")
    html_string = html_string.replace("&amp;", "&")
    return html_string

@app.route('/get_map/<int:report_id>/<int:map_index>', methods=['GET', 'POST'])
def send_next_map(report_id, map_index):
    #load json file from static/gradient_luts
    #return json file
    print("get_map for id"+ str(report_id) + " with: " + str(map_index))
    for thread in threads:
        if thread.report_id == report_id:
            maps_done = thread.get_maps_done()
            if maps_done[map_index]:
                map = thread.get_maps()[map_index]
                project_manager.update_maps(report_id, thread.get_maps())
                thread.update_maps_sent(map_index)
                #map["image_coordinates_json"] = jsonify(map["image_coordinates"])
                map["file_url"] = url_for('static', filename=map["file"])
                return jsonify(map)

    return jsonify({"file": "empty"})


@app.route('/stop_mapping_thread/<int:report_id>/', methods=['GET', 'POST'])
def stop_thread(report_id):
    #load json file from static/gradient_luts
    #return json file
    print("stop_thread for id"+ str(report_id))
    for thread in threads:
        if thread.report_id == report_id:
            threads.remove(thread)
            return "success"
    return "failure"

@app.route('/<int:report_id>/process_status', methods=['GET', 'POST'])
def check_preprocess_status(report_id):
    print('asking for status of report ' + str(report_id))
    progress_mapping = -1
    maps_done = []

    for thread in threads:
        if thread.report_id == report_id:
            # print("check_preprocess_status" + str(report_id))
            progress_mapping = thread.get_progress_mapping()
            # print(progress_preprocessing, progress_mapping)
            maps_done = thread.get_maps_done()
            maps_sent = thread.get_maps_sent()
            if progress_mapping == 100:
                project_manager.update_maps(report_id, thread.get_maps())
            break

    progress_dict = {"percentage": progress_mapping, "maps_done": maps_done, "maps_loaded": maps_sent}
    return jsonify(progress_dict)

@app.route('/<int:report_id>/preprocessProgress', methods=['GET', 'POST'])
def check_preprocess_progress(report_id):
    print('asking for preprocessing progess of report ' + str(report_id))
    progress_preprocessing = -1

    for thread in threads:
        if thread.report_id == report_id:
            # print("check_preprocess_status" + str(report_id))
            progress_preprocessing = thread.get_progress_preprocess()
            if progress_preprocessing == 100 and not thread.metadata_delivered:
                flight_data, camera_specs, weather, maps, file_names_rgb, file_names_ir, ir_settings, panos, \
                    couples_path_list, flight_trajectory = thread.get_results()
                project_manager.update_flight_data(report_id, flight_data)
                project_manager.update_camera_specs(report_id, camera_specs)
                project_manager.update_weather(report_id, weather)
                project_manager.update_maps(report_id, maps)
                project_manager.update_ir_settings(report_id, ir_settings)
                project_manager.add_panos(report_id, panos)
                project_manager.update_slide_file_paths(report_id, couples_path_list)
                project_manager.update_flight_trajectory(report_id, flight_trajectory)
                project_manager.overwrite_file_names_sorted(report_id, file_names_rgb=file_names_rgb, file_names_ir=file_names_ir)
                project_manager.update_contains_unprocessed_images(report_id, False)
                thread.metadata_delivered = True
                return render_standard_report(report_id)
            else:
                return jsonify(progress_preprocessing)
            break
    return jsonify(progress_preprocessing)


@app.route("/run_detection/<int:report_id>", methods=['GET', 'POST'])
def run_detection(report_id):
    numbr_of_models = 2
    models_setting = request.form.get('model_options')
    if models_setting == "all":
        numbr_of_models = 5
    elif models_setting == "medium":
        numbr_of_models = 3

    detect_objects(numbr_of_models, report_id)
    detections = json.load(open(project_manager.get_annotation_file_path(report_id)))

    # return render_standard_report(report_id)
    return detections

def detect_objects(numbr_of_models, report_id):
    networks_weights_folder = "./detection/model_weights"
    weights_paths_list = []

    weights_paths_list.append(networks_weights_folder + "/deformable_detr_twostage_refine_r50_16x2_50e_coco_fire_04")
    weights_paths_list.append(networks_weights_folder + "/autoassign_r50_fpn_8x2_1x_coco_fire_0")
    if numbr_of_models >= 3:
        weights_paths_list.append(networks_weights_folder + "/tood_r101_fpn_dconv_c3-c5_mstrain_2x_coco_fire_5")
        if numbr_of_models >= 4:
            weights_paths_list.append(
                networks_weights_folder + "/vfnet_x101_32x4d_fpn_mdconv_c3-c5_mstrain_2x_coco_fire_1")
            if numbr_of_models >= 5:
                weights_paths_list.append(networks_weights_folder + "/yolox_s_8x8_300e_coco_fire_300_4")

    images_path_list = project_manager.get_file_names_rgb(report_id)
    images_path_list = ["./static/" + path for path in images_path_list]
    config_path = "detection/config/custom/config.py"
    ann_path = project_manager.get_annotation_file_path(report_id)  # vom project manager geben lassen

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

@app.route('/update_detections_colors/<int:report_id>', methods=['POST'])
def update_detections_colors(report_id):
    color =[request.form.get('colorH'), request.form.get('colorS'), request.form.get('colorL')]
    category_name = request.form.get('category_name')
    print(request.form)
    print("update_detections_colors for id"+ str(report_id) + " with: " + str(color) + " and category_name: " + str(category_name))
    project_manager.update_detections_colors(report_id, color, category_name)
    return "success"

@app.route('/display/<filename>')
def display_image(filename):
    # print('display_image filename: ' + filename)
    return redirect(url_for('static', filename='uploads/' + filename), code=301)


def thumbnail_for(path):
    # insert a 'thumbnail/' after the last /
    path_thumbnail = path[:path.rindex('/') + 1] + 'thumbnails/' + path[path.rindex('/') + 1:]
    #check if file exists
    if not os.path.isfile('./static/' + path_thumbnail):
        path_thumbnail = path
    # print('display_image filename: ' + filename)
    return path_thumbnail


@app.route('/idgenerator/<filename>')
def generate_id_for_image(filename):
    #print('display_image filename: ' + filename)
    return redirect(url_for('static', filename='uploads/' + filename), code=301)

#shutdown program

@app.route('/shutdown')
def shutdown():
    print("Server shutting down...")
    stop_server()
    return 'Server shutting down...'

def stop_server():
    # global server
    # quit()
    # server.shutdown()
    # os._exit(0)
    os.kill(os.getpid(), signal.SIGINT)




if __name__ == '__main__':
    #execute the python program in file model_weights_downloader.py
    model_weights_downloader = ModelWeightsDownloader()
    model_weights_downloader.check_model_weights()

    start = datetime.datetime.now().replace(microsecond=0)
    project_manager.initiate_project_list()

    app.jinja_env.globals.update(thumbnail_for=thumbnail_for)

    app.run(host="0.0.0.0", port=5000, debug=True, use_reloader=False)
    #start_server()  # start server

    #TODO List Report
    # IR Bilder separat im Projekt speichern (file_names entsprechend anpassen)
    # Header Stylen (Logo, Name, Beschreibung)
    # Bisschen besseres Feedback für den User (beim Mapping Balken)

    #TODO allgmeien
    # IR Bilder in eigenen Ordner verschieben
    # IDs aus Datum Und Uhrzeit Basteln
    # Unterschiedliche Anzahl an IR und RGB Bildern handeln: Fehlerausgabe/einfach annehmen, auf jedem Fall Sorter fixen

    # TODO List Project Overview

    #TODO allgemein
    # Report mit nur IR Bildern auch als solche verarbeiten/ ermöglichen
    # Wetter Daten aus der Vergangenheit abrufen können
    # Überall wo multiprocessing pool genutzt wird, vorher schauen, wie viel threads verfügbar sind
    # nach aufruf von start den browser öffnen

#TODO Settings bei der Seite wo nur das preprocessing gemacht wird fixen
# Automatisch zu IR Settings wechseln, wenn nur IR Bilder Ausgewählt werden in Galerie

#Kill Process on port:
#find pid
#   sudo lsof -i :5000
# kill 1234

#kill them all:
#sudo fuser -k 5000/tcp
