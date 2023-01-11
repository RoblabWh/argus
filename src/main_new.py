

import os
import sys
import datetime
import argparse
from multiprocessing import Process

from image_mapper_for_falsk import ImageMapper
from project_manager import ProjectManager
from mapper_thread import MapperThread
from PanoramaViewer import Panorma_viewer

from flask import Flask, flash, request, redirect, url_for, render_template
#import urllib.request
import os
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
app.config['MAX_CONTENT_LENGTH'] = 500 * 8024 * 8024

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
# image_mapper = ImageMapper(path_to_images)
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def render_standard_report(report_id, thread = None):
    #check if process is running and if it is only preprocessing or calculating map
    data = project_manager.get_project(report_id)['data']
    flight_data = data["flight_data"]
    camera_specs = data["camera_specs"]
    weather = data["weather"]
    file_names = data["file_names"]
    file_names_ir = data["file_names_ir"]
    has_ir = False
    if file_names_ir != []:
        has_ir = True
    map = data["map"]
    message = None
    processing = False
    for thread in threads:
        if thread.report_id == report_id:
            processing = True
            message = thread.message
            break


    project = {"id": report_id, "name": project_manager.get_project_name(report_id),
               "description": project_manager.get_project_description(report_id),
               'creation_time': project_manager.get_project_creation_time(report_id)}
    return render_template('concept.html', id=report_id, file_names=file_names, file_names_ir=file_names_ir,
                           has_ir=has_ir, flight_data=flight_data, camera_specs=camera_specs, weather=weather, map=map,
                           project=project, message=message, processing=processing)


@app.route('/')
def projects_overview():
    projects_dict_list = project_manager.get_projects()
    return render_template('projectsOverview.html', projects = projects_dict_list )

@app.route('/create', methods=['POST'])
def create_report():
    name = request.form.get("name")
    description = request.form.get("description")
    project_manager.create_project(name, description)
    # project_manager.create_project("testname", "testdescription")
    projects_dict_list = project_manager.get_projects()
    return render_template('projectsOverview.html', projects=projects_dict_list)

@app.route('/<int:report_id>')
def upload_form(report_id):
    #check if directory static/uploads/report_id exists
    #if yes, load json file
    #if not create it
    print("upload_form" + str(report_id))
    if(project_manager.has_project(report_id)):
        print("Directory exists")
        return render_standard_report(report_id)
    else:
        projects_dict_list = project_manager.get_projects()
        return render_template('projectsOverview.html', projects=projects_dict_list, message="Report does not exist")

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
    file_names = project_manager.update_file_names(report_id, file_names)
    print(file_names)
    project = {"id": report_id, "name": project_manager.get_project_name(report_id), "description": project_manager.get_project_description(report_id)}
    return render_standard_report(report_id)
    # return render_template('concept.html', id=report_id, file_names=file_names, flight_data=flight_data, camera_specs=camera_specs,
    #                        weather=weather, map=map, project=project)

@app.route('/<int:report_id>/process', methods=['POST', 'GET'])
def process(report_id):
    if request.method == 'POST':
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

        image_mapper = project_manager.get_image_mapper(report_id)

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

        print("with_ODM: ", with_ODM)
        print("ai_detection: ", ai_detection)
        print("map_resolution: ", map_resolution)

        image_mapper.set_processing_parameters(map_width_px=max_width,
                                               map_height_px=max_height, with_ODM=with_ODM)#, ai_detection=ai_detection)
        thread = MapperThread(image_mapper, report_id, file_names)
        threads.append(thread)
        thread.start()
        print("process started")
        return render_standard_report(report_id, thread)


@app.route('/<int:report_id>/process_status', methods=['GET', 'POST'])
def check_preprocess_status(report_id):
    print('asking for status of report ' + str(report_id))
    progress_preprocessing = -1
    progress_mapping = -1
    redirect = False
    map_url = url_for('static', filename="default/MapRGBMissing.jpeg")
    map_ir_url = url_for('static', filename="default/MapIRMissing.jpeg")

    for thread in threads:
        if thread.report_id == report_id:
            print("check_preprocess_status" + str(report_id))
            progress_preprocessing = thread.get_progress_preprocess()
            progress_mapping = thread.get_progress_mapping()
            print(progress_preprocessing, progress_mapping)
            if progress_preprocessing == 100 and not thread.metadata_delivered:
                flight_data, camera_specs, weather, map, file_names_rgb, file_names_ir = thread.get_results()
                project_manager.update_flight_data(report_id, flight_data)
                project_manager.update_camera_specs(report_id, camera_specs)
                project_manager.update_weather(report_id, weather)
                project_manager.update_map(report_id, map)
                project_manager.overwrite_file_names_sorted(report_id, file_names_rgb= file_names_rgb, file_names_ir=file_names_ir)
                redirect = True
                thread.metadata_delivered = True
            elif progress_mapping == 100:
                project_manager.update_map(report_id, thread.get_map())
                map_url = url_for('static', filename=project_manager.get_map(report_id)['rgbMapFile'])
                map_ir_url = url_for('static', filename=project_manager.get_map(report_id)['irMapFile'])
                # map_ir_url = url_for('static', filename=project_manager.get_map(report_id)['rgbMapFile'])
                print(map_url)
                threads.remove(thread)
            break
    return str(progress_preprocessing) + "," + str(progress_mapping) + "," + str(redirect) + "," + str(map_url) + "," + str(map_ir_url)



# @app.route('/<int:report_id>/buildMap', methods=['POST'])
# def buildMap(report_id):
#     if request.method == 'POST':
#         map = image_mapper.map_images(report_id)
#         file_names = project_manager.get_file_names(report_id)
#         flight_data = project_manager.get_flight_data(report_id)
#         camera_specs = project_manager.get_camera_specs(report_id)
#         weather = project_manager.get_weather(report_id)
#         project = {"id": report_id, "name": project_manager.get_project_name(report_id),
#                    "description": project_manager.get_project_description(report_id)}
#         if map == None:
#             return render_template('concept.html', id=report_id, file_names=file_names, flight_data=flight_data, camera_specs=camera_specs,
#                                weather=weather, map=map, message="Error", project=project)
#         project_manager.update_map(report_id, map)
#
#
#         return render_template('concept.html', file_names=file_names, flight_data=flight_data,
#                                camera_specs=camera_specs,
#                                weather=weather, map=map, project=project)
#     #return render_template('concept.html')

@app.route('/display/<filename>')
def display_image(filename):
    # print('display_image filename: ' + filename)
    return redirect(url_for('static', filename='uploads/' + filename), code=301)

# @app.route('/display/<path>/<filename>')
# def display_image_with_path(path, filename):
#     print('display_image filename: ' + filename + path)
#     return redirect(url_for('static', filename='uploads/' + path + '/' + filename), code=301)

@app.route('/idgenerator/<filename>')
def generate_id_for_image(filename):
    #print('display_image filename: ' + filename)
    return redirect(url_for('static', filename='uploads/' + filename), code=301)

if __name__ == '__main__':
    print("Sudo permission is required to add GPS based evaluations to the report")
    os.system(": $(sudo chmod +x ./get-gps-info.sh)")

    start = datetime.datetime.now().replace(microsecond=0)
    project_manager.initiate_project_list()

    app.run(debug=True)


    #TODO List Report
    #   IR Map serstellen
    # NEXT IR Bilder in eigenen Ordner verschieben und im Projekt speichern (file_names entsprechend anpassen)
    # NEXT Switch/ Tab für IR Bilder (/mit Overlay) (von wegen Checkbox für show all, only IR oder only RGB)
    # Header Stylen
    #   Footer erstellen (Urheber etc)
    #   Buttons zum berechnen umsortieren
    #   Feedback für den User (Berechnung läuft, fertig, Fehler)
    # GPS Polygone für Flug einbauen
    # Bilder oder punkte anklickbar machen (für Link zur Slideshow)
    #   DONE map im ordner speichern und korrekt laden
    #   Maus in Gallerie bem Hovern zur Hand machen und scroll to einabuen
    # Bisschen besseres Feedback für den User (beim Mapping Balken)
    # Beschreibung bearbeitbar machen
    # Fade Slider in Map einbauen
    # beim fenster resize neu magnify aufrufen

    #   TODO render project nur noch aus einer methode mit parametern machen

    # TODO List Project Overview
    #   Overview Seite Stylen
    #   Eingabemaske bei neuen Projekten erzeugen & entsprechend Daten übergeben
    #   Bestehende Projekte Löschen
    #   nach ID sortiert darstellen
    #   neues Projekt Anlegen stylen
    #   (alert) Abfrage bei Delete

    #   TODO größe der Maps ändern
    #   TODO Map Bild ersetzen, Seite nicht neu laden

    #TODO allgemein
    # Report mit nur IR Bildern auch als solche verarbeiten/ ermöglichen
    # Wetter Daten aus der Vergangenheit abrufen können


    # NEXT!!!!!!!!!!!!!!!!!!!!
    # TODO IR Bilder in eigenen Ordner verschieben
    # TODO Tab für IR Darstellungseinstellung (Checkbox für Temp messen, und Schieberegler für Transparenz)
    # TODO Temp messen einbauen


#Kill Process on port:
#find pid
#   sudo lsof -i :5000
# kill 1234