import os
import shutil

from exif_header import ExifHeader

class Panorma_viewer:
    def __init__(self, path):
        self.path = path + 'pano/'
        #check if path exists
        if os.path.exists(self.path):
            self.image_list = []
            files = os.listdir(self.path)

            for file in files:
                # make sure file is an image
                if file.endswith(('.jpg', '.JPG', '.png', '.jpeg', '.PNG', '.JPEG')):
                    img_path = self.path + file
                    self.image_list.append(img_path)

            self.has_pano = True
        else:
            self.has_pano = False

        #print(self.image_list)

    def generate_reports(self):
        pano_html_files = []
        if self.has_pano:
            for image_path in self.image_list:
                filename_without_extension = os.path.splitext(os.path.basename(image_path))[0]
                html_file_name = self.path + 'pano' + filename_without_extension + '.html'

                exifheader = ExifHeader(image_path)

                template_desciptor = open("template360.html", "r")
                seperator = "<!--883458934589839458934573894573845734858345783457348534587-->"
                text = template_desciptor.read()
                splitet_template_lst = text.split(seperator)
                file_desciptor = open(str(html_file_name), "w")
                self.write_header(file_desciptor, exifheader.creation_time_str)
                file_desciptor.write(splitet_template_lst[0])
                self.write_pano(file_desciptor, image_path, exifheader.creation_time_str)
                file_desciptor.write(splitet_template_lst[1])
                file_desciptor.close()
                pano_html_files.append((exifheader.get_gps().get_latitude(), exifheader.get_gps().get_longitude(), 'pano/pano' + filename_without_extension + '.html'))

            shutil.copy2('pannellum.css', self.path)
            shutil.copy2('pannellum.js', self.path)

        return pano_html_files

    def write_header(self, file_desciptor, date):
        file_desciptor.write('<!DOCTYPE html>\n')
        file_desciptor.write('<html>\n')
        file_desciptor.write('<head>\n')
        file_desciptor.write('  <meta charset="UTF-8">\n')
        file_desciptor.write('  <title>DRZ - Pano vom ' + date + '</title>\n')

    def write_pano(self, file_desciptor, image_file_path, date_time):
        #filename of path
        filename = os.path.basename(image_file_path)
        file_desciptor.write('<script>\n')
        file_desciptor.write("viewer = pannellum.viewer('panorama', {\n")
        file_desciptor.write("      \"title\": \""+ date_time +"\",\n")
        file_desciptor.write("      \"author\": \"Hartmut Surmann, Max Schulte & DRZ-Team\",\n")
        file_desciptor.write("      \"type\": \"equirectangular\",\n")
        file_desciptor.write("      \"panorama\": \"" + str(filename) + "\",\n")
        file_desciptor.write("      \"preview\": \"" + str(filename) + "\",\n")
        file_desciptor.write("      \"autoLoad\": true,\n")
        file_desciptor.write("    \"autoRotate\": -5,\n")
        file_desciptor.write("    \"minHfov\": 2,\n")
        file_desciptor.write("    \"maxHfov\": 140,\n")
        file_desciptor.write("    \"showControls\": false\n")
        file_desciptor.write("});\n")
