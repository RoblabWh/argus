import threading
import os
import sys
import shutil

from .image import Image

class FilterThread(threading.Thread):

    def __init__(self, path, report_id):
        self.path = path
        self.report_id = report_id
        self.ir = False
        self.pano = False
        self.done = False
        self.results_already_sent = False
        self.image = None
        super().__init__()

    def run(self):
        self.image = Image(self.path)
        self.ir = self.image.get_exif_header().ir
        self.pano = self.image.get_exif_header().pano
        self.image.generate_thumbnail()
        self.done = True

    def get_old_and_new_path(self):
        return self.path, self.image.get_image_path()

    def get_result(self):
        return self.ir, self.pano, self.image


# moving the images happens automatically if an image is ir or panorama during its initilization

# after all images are processed, they are sorted into 3 lists, based on the pano and ir variable and the filepaths get saved in the project manager acordingly
# the first ir image gets checked for ir settings and the settings get saved in the project manager
# if no settings can be extracted a messege is send to the website, that asks the user to enter the settings manually
# when processing starts, images get sorted by creation time and couples are created, also the flight trajectory gets calculated



# clicking on images after upload need to direct to moved image position and deleting must be fixed as well (maybe when checking progress send new paths)
# now wehen processing starts, fist check, if every image has an image opject. if not create objects for remaining images, but make sure to not move them into subfolders if already in correct folder
# then process the rest, order of images, couples, trajectory, content for data tables in report, and then start generating the maps










# nach upload habe ich eine Liste an Bildern im Projectmanager, in all images, mit dem Pfad ins projetverzeichnis
# sobald ein Bild verschoben wird, wird sollte der pfad unter all images auch aktualisiert werden
# jetzt im Image Processor einfach die images durchgehen und die Pfade alle aus den zu verarbeitenden bildern raus kegeln









