

import os
import sys
import datetime
import argparse
from multiprocessing import Process

from image_mapper_for_falsk import ImageMapper
from project_manager import ProjectManager
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

file_names = []
flight_data = []
camera_specs = []
weather = []
map = {}

path_to_images = "./static/uploads/"
projects_dict_list = []

project_manager = ProjectManager()
image_mapper = ImageMapper(path_to_images)
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


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
    if(os.path.isdir(path_to_images + str(report_id))):
        print("Directory exists")
        data = project_manager.load_data(report_id)
        file_names = data["file_names"]
        flight_data = data["flight_data"]
        camera_specs = data["camera_specs"]
        weather = data["weather"]
        map = data["map"]
        return render_template('concept.html', id=report_id, file_names=file_names, flight_data=flight_data, camera_specs=camera_specs, weather=weather, map=map)
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
    return render_template('concept.html', id=report_id, file_names=file_names, flight_data=flight_data, camera_specs=camera_specs,
                           weather=weather, map=map)

@app.route('/<int:report_id>/process', methods=['POST'])
def process(report_id):
    if request.method == 'POST':
        file_names = project_manager.get_file_names(report_id)
        # start a process to preprocess the images
        flight_data, camera_specs, weather, map = image_mapper.calculate_metadata(report_id, file_names)
        if (flight_data == None):
            return render_template('concept.html', id=report_id, file_names=file_names, flight_data=flight_data,
                                   camera_specs=camera_specs,
                                   weather=weather, map=map, message="Error")

        project_manager.update_flight_data(report_id, flight_data)
        project_manager.update_camera_specs(report_id, camera_specs)
        project_manager.update_weather(report_id, weather)
        project_manager.update_map(report_id, map)

        return render_template('concept.html', id=report_id, file_names=file_names, flight_data=flight_data,
                               camera_specs=camera_specs,
                               weather=weather, map=map)
#         process = Process(target=preprocess_asynchronous, args=(report_id, file_names))
#         process.start()
#
# def preprocess_asynchronous(report_id, file_names):
#     flight_data, camera_specs, weather, map = image_mapper.calculate_metadata(report_id, file_names)
#     if (flight_data == None):
#         return render_template('concept.html', id=report_id, file_names=file_names, flight_data=flight_data,
#                                camera_specs=camera_specs,
#                                weather=weather, map=map, message="Error")
#
#     project_manager.update_flight_data(report_id, flight_data)
#     project_manager.update_camera_specs(report_id, camera_specs)
#     project_manager.update_weather(report_id, weather)
#     project_manager.update_map(report_id, map)
#
#     return render_template('concept.html', id=report_id, file_names=file_names, flight_data=flight_data,
#                            camera_specs=camera_specs,
#                            weather=weather, map=map)

@app.route('/<int:report_id>/buildMap', methods=['POST'])
def buildMap(report_id):
    if request.method == 'POST':
        map = image_mapper.map_images(report_id)
        file_names = project_manager.get_file_names(report_id)
        flight_data = project_manager.get_flight_data(report_id)
        camera_specs = project_manager.get_camera_specs(report_id)
        weather = project_manager.get_weather(report_id)
        if map == None:
            return render_template('concept.html', id=report_id, file_names=file_names, flight_data=flight_data, camera_specs=camera_specs,
                               weather=weather, map=map, message="Error")
        project_manager.update_map(report_id, map)


        return render_template('concept.html', file_names=file_names, flight_data=flight_data,
                               camera_specs=camera_specs,
                               weather=weather, map=map)
    #return render_template('concept.html')

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

    app.run(debug=True)


    #TODO List Report
    # IR Bilder in eigenen Ordner verschieben und im Projekt speichern (file_names entsprechend anpassen)
    # Switch/ Tab für IR Bilder (/mit Overlay) (von wegen Checkbox für show all, only IR oder only RGB)
    # Header Stylen
    # Footer erstellen (Urheber etc)
    # Buttons zum berechnen umsortieren
    # Feedback für den User (Berechnung läuft, fertig, Fehler)
    # GPS Polygone für FLug einbauen
    # Bilder oder punkte anklickbar machen (für Link zur Slideshow)
    # DONE map im ordner speichern und korrekt laden

    #TODO List Project Overview
    # Overview Seite Stylen
    # Eingabemaske bei neuen Projekten erzeugen & entsprechend Daten übergeben
    # Betsehende Projekte Löschen


