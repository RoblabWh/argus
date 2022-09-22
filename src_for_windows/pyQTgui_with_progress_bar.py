import sys
import datetime
import time

from PyQt5.QtCore import QSize, Qt, QObject, QThread, pyqtSignal
from PyQt5.QtWidgets import QApplication, QMainWindow, QPushButton, QProgressBar, QFileDialog, QLineEdit, QLabel
from PyQt5.QtGui import QMovie, QIcon
from image_mapper import ImageMapper

class ImageMapperThread(QThread):
    finished = pyqtSignal()
    started = pyqtSignal()
    progression = pyqtSignal(str)

    def __init__(self, path, parent=None):
        QThread.__init__(self, parent)
        if path[-1] != "/":
            path += "/"
        self.path = path
        self.map_width_px= 2500
        self.map_height_px= 2500 
        self.blending = 0.7   
        self.optimize = False

    def run(self):
        self.started.emit()
        image_mapper = ImageMapper(self.path, self.map_width_px, self.map_height_px, self.blending, self.optimize, self.statusupdate)
        image_mapper.create_flight_report()
        image_mapper.show_flight_report()
        #maybe create own image mapper python class w/ callback so you can display the progress
        self.finished.emit()
    def statusupdate(self, str):
        self.progression.emit(str)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.selectedFolder = ""
        #create ui elements
        self.setWindowTitle("ImageMapper")
        self.setWindowIcon(QIcon('pythonpowered.png'))

        self.folderDisplay = QLabel('',self)
        self.folderDisplay.setStyleSheet("background-color: white; border: 1px solid black;")
        self.folderDisplay.setGeometry(125,50,300,30)

        self.folderSelecter = QPushButton('select folder',self)
        self.folderSelecter.setGeometry(25,50,75,30)
        self.folderSelecter.clicked.connect(self.folderSelection)

        self.runImageMapper = QPushButton('start mapping', self)
        self.runImageMapper.setGeometry(25,150,75,30)
        self.runImageMapper.clicked.connect(self.startImageMapperThread)
        self.runImageMapper.setEnabled(False)

        self.loadingGif = QLabel(self)
        self.loadingGif.move(325,110)
        self.gif = QMovie('loading.gif')
        self.gif.setScaledSize(QSize(100,100))
        self.loadingGif.resize(100,100)
        self.loadingGif.setMovie(self.gif)
        self.loadingGif.hide()
        self.status = QLabel('',self)
        self.status.setGeometry(125,190,300,30)
        self.status.setAlignment(Qt.AlignCenter)
        self.progressBar = QProgressBar(self)
        self.progressBar.setGeometry(125,150,200, 25)
        self.progressBar.setMaximum(100)
        self.progressBar.hide()

        self.setFixedSize(QSize(450,250))

    def folderSelection(self):
        response = QFileDialog.getExistingDirectory(
            self,
            caption='Select a folder'
        )
        self.selectedFolder = response
        self.folderDisplay.setText(response)
        if response:
            self.runImageMapper.setEnabled(True)
        else:
            self.runImageMapper.setEnabled(False)
        return response

    def startImageMapperThread(self):
        if self.selectedFolder:
            self.folderSelecter.setEnabled(False)
            self.runImageMapper.setEnabled(False)
            print(self.selectedFolder)
            self.mapping = ImageMapperThread(self.selectedFolder)
            self.mapping.finished.connect(self.finished)
            self.mapping.started.connect(self.started)
            self.mapping.progression.connect(self.logProgress)
            self.mapping.start()
            self.loadingGif.show()
            self.progressBar.show()
            self.gif.start()
            self.status.setText('starting ImageMapper')
        else:
            print('please select a folder')
    def finished(self):
        print('image mapper finished')
        self.folderSelecter.setEnabled(True)
        self.runImageMapper.setEnabled(True)
        self.loadingGif.hide()
        self.gif.stop()
        self.progressBar.hide()
        self.status.setText("image mapper finished")
    def started(self):
        print('image mapper started')
    def logProgress(self, str):
        self.status.setText(str)

        if str.replace("Step ","")[0] == "1":
            prog = 0
            while prog < 5:
                prog += 0.0001
                self.progressBar.setValue(prog)
        elif str.replace("Step ","")[0] == "2":
            range = 45
            percentage = int(str.replace("Step 2/4: loading images: ","").split('/')[0])/int(str.replace("Step 2/4: loading images: ","").split('/')[1])
            self.progressBar.setValue(5 + (range * percentage))
        elif str.replace("Step ","")[0] == "3":
            range = 45
            percentage = int(str.replace("Step 3/4: building map: ","").split('/')[0])/int(str.replace("Step 3/4: building map: ","").split('/')[1])
            self.progressBar.setValue(50 + (range * percentage))
        elif str.replace("Step ","")[0] == "4":
            prog = 0
            while prog < 5:
                prog += 0.001
                self.progressBar.setValue(95+prog)

def main():
    app = QApplication(sys.argv)

    window = MainWindow()
    window.show()

    app.exec()

if __name__ == "__main__":
    main()