import eventlet
import socketio
import threading
import requests
import base64
import map_segment_pb2
import pyarrow
import numpy
import datetime
import json
import os
import subprocess
from keyframes import Keyframes
from landmarks import Landmarks
from transmission import Transmission
from util import popen_and_call

class vslam_thread(threading.Thread):

    def decodeMessage(self, data):
        map = map_segment_pb2.map()
        map.ParseFromString(base64.b64decode(data))
        for keyframe in map.keyframes:
            keyfrm = {}
            keyfrm["id"] = keyframe.id
            keyfrm["pose"] = []  # convert pose to array
            for cell in keyframe.pose.pose:
                keyfrm["pose"].append(cell)
            lastStep = "keyframe" + str(keyframe.id) + "|" + str(keyfrm["pose"]) + ":"
            if (keyfrm["pose"] is None):
                self.keyframes.removeKeyframe(keyfrm["id"])
            else:
                self.keyframes.updateKeyframe(keyfrm["id"], keyfrm["pose"])
        for landmark in map.landmarks:
            landmarkObj = {}
            landmarkObj["id"] = landmark.id
            # if the landmark has coordinates, we create a new landmark that will either get added or update a current
            # entry in self.landmarks
            if (len(landmark.coords) != 0):
                landmarkObj["point_pos"] = []
                for coord in landmark.coords:
                    landmarkObj["point_pos"].append(coord)
                landmarkObj["rgb"] = []
                for color in landmark.color:
                    landmarkObj["rgb"].append(color)
            if (len(landmark.coords) == 0):
                self.landmarks.removeLandmark(landmarkObj["id"])
            else:
                self.landmarks.updateLandmark(landmarkObj["id"], landmarkObj["point_pos"], landmarkObj["rgb"])

    def __init__(self, report_id, keyfrm_path, landmark_path, slam_output_path):
        self.report_id = report_id
        self.sio = socketio.Server()
        self.app = socketio.WSGIApp(self.sio)
        self.keyframes = Keyframes()
        self.landmarks = Landmarks()
        self.keyfrm_path = keyfrm_path
        self.landmark_path = landmark_path
        self.slam_output_path = slam_output_path
        self.transmission = Transmission(callback=self.decodeMessage)
        self.startTime = None
        self.stopTime = None
        self.done = False

        @self.sio.event
        def connect(sid, environ):
            print('connect ', sid)

        @self.sio.on('map_publish')
        def handle_message(sid, data):
            if self.startTime == None:
                self.startTime = datetime.datetime.now()
            self.transmission.receive(data)

        @self.sio.event
        def disconnect(sid):
            print('disconnect ', sid)
            self.saveResults()
        super().__init__()

    def saveResults(self):
        self.stopTime = datetime.datetime.now()
        print("finished vslam in", self.stopTime - self.startTime, flush=True)
        calc_time = self.stopTime - self.startTime
        with open(self.keyfrm_path, "w") as json_keyfrm_file:
            json.dump(self.keyframes.getAllKeyframes(), json_keyfrm_file, ensure_ascii=False, indent=4)
        with open(self.landmark_path, "w") as json_landmark_file:
            json.dump(self.landmarks.getAllLandmarks(), json_landmark_file, ensure_ascii=False, indent=4)
        slam_output = {"calculation_time": str(calc_time)}
        with open(self.slam_output_path, "w") as json_slam_file:
            json.dump(slam_output, json_slam_file, ensure_ascii=False, indent=4)
        self.done = True

    def run(self):
        eventlet.wsgi.server(eventlet.listen(('', 3000)), self.app)
