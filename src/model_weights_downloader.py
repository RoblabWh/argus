#import pysciebo
#from webbot import Browser
#import requests
import os
import owncloud
import zipfile
import time

# check if src/detection/model_weights/ exists or if it is empty

class ModelWeightsDownloader:
    def __init__(self, weights_path="./detection/model_weights/"):
        self.weight_path = weights_path
        print("weights_path set to:", weights_path)


    def check_model_weights(self):
        if not self._has_model_weights():
            print("no files were found under: ", os.path.abspath(self.weight_path))
            self._download_model_weights()
            self._unzip_model_weights()
        else:
            print("found existing model weights at: ", os.listdir(self.weight_path))

    def _has_model_weights(self):
        if not os.path.exists(self.weight_path):
            os.makedirs(self.weight_path)
            return False
        if not os.listdir(self.weight_path):
            return False
        return True

    def _download_model_weights(self):
        # download model weights from sciebo-link "https://w-hs.sciebo.de/s/dF2wQbFNW2zuCpK" with password "fire"
        # and save them to src/detection/model_weights/

        destination = self.weight_path
        public_link = 'https://w-hs.sciebo.de/s/dF2wQbFNW2zuCpK'
        folder_password = 'fire'

        oc = owncloud.Client.from_public_link(public_link, folder_password=folder_password)
        print("downloading model weights from sciebo-link: ", public_link)
        print("This may take a couple of minutes (file size approximately 1.6GB). The weights only need to be loaded once.")

        print("started download at", time.strftime('%H:%M:%S - %d/%m/%Y'))
        oc.get_file('/model_weights.zip', destination+'model_weights.zip')
        print("finished download at", time.strftime('%H:%M:%S - %d/%m/%Y'))

    def _unzip_model_weights(self, delete_zip=True):
        # unzip model weights from src/detection/model_weights/model_weights.zip
        # and save them to src/detection/model_weights/
        print("unzipping model weights from ", self.weight_path+'model_weights.zip')
        with zipfile.ZipFile(self.weight_path+'model_weights.zip', 'r') as zip_ref:
            zip_ref.extractall(self.weight_path)
        if delete_zip:
            os.remove(self.weight_path+'model_weights.zip')

        #if there is a folder model_weighs within the zip file, move all files and fodlers from this folder to the parent folder
        if os.path.exists(self.weight_path+'model_weights'):
            print("moving all files and folders from model_weights folder to parent folder")
            for file in os.listdir(self.weight_path+'model_weights'):
                os.rename(self.weight_path+'model_weights/'+file, self.weight_path+file)
            os.rmdir(self.weight_path+'model_weights')

        print("finished unzipping model weights")


