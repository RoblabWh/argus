import json
import os
from flask import Flask, flash, request, redirect, url_for, render_template, jsonify
from detection_process import DetectionProcess

class DetectionServer:
    def __init__(self, address, port, device):
        self.app = Flask(__name__)

        self.app.secret_key = "WasIstDennMitKarsten?-LosDasSiehtAberGarNichtGutAus"
        self.threads = []
        self.address = address
        self.port = port
        self.device = device

        self.setup_routes()

    def setup_routes(self):
        self.app.add_url_rule('/', view_func=self.render_status)
        self.app.add_url_rule('/process', methods=['POST'], view_func=self.process)
        self.app.add_url_rule('/get_processes', methods=['GET'], view_func=self.get_processes)
        self.app.add_url_rule('/remove_thread/<report_id>', methods=['GET'], view_func=self.remove_thread)

    def render_status(self):
        det_threads = []
        for thread in self.threads:
            t = {'report_id': thread.report_id, 'started': thread.started, 'done': thread.done}
            det_threads.append(t)
        return render_template('status.html', detection_threads=det_threads)

    def process(self):
        data = request.get_json(force=True)
        print("data: ", data, flush=True)
        report_id = data['report_id']
        models = data['models']
        max_splits = data['max_splits']
        image_folder = data['image_folder']
        ann_path = data['ann_path']


        process = DetectionProcess(report_id, models, max_splits, image_folder, ann_path, self.device)
        self.threads.append(process)

        if(len(self.threads) == 1):
            print("Starting first thread", flush=True)
            self.threads[0].start()
            return jsonify({'status': 'started'})
        else:
            print("Thread is queued", flush=True)

        return jsonify({'status': 'queued'})

    def remove_thread(self, report_id):
        removed = False
        for i, thread in enumerate(self.threads):
            if thread.report_id == report_id:
                self.threads.pop(i)
                removed = True
                break

        if self.threads:
            self.threads[0].start()

        return jsonify({'removed': removed})


    def get_processes(self):
        thread_data = [{'report_id': thread.report_id, 'started': thread.report_id, 'done': thread.done} for thread in self.threads]
        return jsonify(thread_data)

    def run(self):
        self.app.run(host=self.address, port=self.port, debug=True, use_reloader=False)
