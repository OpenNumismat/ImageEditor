from PySide6.QtCore import QTimer, QSettings, Qt
from PySide6.QtGui import QIcon, QShortcut
from PySide6.QtWidgets import QComboBox, QDialog, QMessageBox, QVBoxLayout, QPushButton
from PySide6.QtMultimedia import QCamera, QImageCapture, QMediaCaptureSession, QMediaDevices
from PySide6.QtMultimediaWidgets import QVideoWidget

try:
    from OpenNumismat.Tools.DialogDecorators import storeDlgSizeDecorator
except ModuleNotFoundError:
    from Tools.DialogDecorators import storeDlgSizeDecorator


@storeDlgSizeDecorator
class CameraDialog(QDialog):

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setWindowIcon(QIcon(':/webcam.png'))
        self.setMinimumHeight(100)

        self.image = None
        self.captureSession = QMediaCaptureSession()
        self.camera = None

        # To check camera blocked by antivirus
        self.first_capture_timer = QTimer(self)
        self.first_capture_timer.timeout.connect(self.firstCaptureTimeout)

        self.viewfinder = QVideoWidget()

        self.cameraSelector = QComboBox()
        for cameraDevice in QMediaDevices.videoInputs():
            self.cameraSelector.addItem(cameraDevice.description(), cameraDevice.id())
        self.cameraSelector.setCurrentIndex(-1)
        self.cameraSelector.currentIndexChanged.connect(self.cameraChanged)

        self.shootBtn = QPushButton(self.tr("Shoot"))
        self.shootBtn.clicked.connect(self.shoot)
        self.shootBtn.setEnabled(False)
        self.shootShortcut = QShortcut(Qt.Key_Space, self, self.shoot)

        layout = QVBoxLayout()
        layout.addWidget(self.cameraSelector)
        layout.addWidget(self.viewfinder)
        layout.addWidget(self.shootBtn)
        self.setLayout(layout)

        settings = QSettings()
        default_camera_id = settings.value('default_camera')
        camera_index = -1
        if default_camera_id:
            camera_index = self.cameraSelector.findData(default_camera_id)
            if camera_index == -1:
                defaultDevice = QMediaDevices.defaultVideoInput()
                camera_index = self.cameraSelector.findData(defaultDevice.id())
        else:
            defaultDevice = QMediaDevices.defaultVideoInput()
            camera_index = self.cameraSelector.findData(defaultDevice.id())

        if camera_index == -1:
            QMessageBox.warning(self.parent(), self.tr("Scan barcode"),
                                self.tr("Camera not available"))
        else:
            self.cameraSelector.setCurrentIndex(camera_index)

    def cameraChanged(self, _index):
        cameraId = self.cameraSelector.currentData()
        for cameraDevice in QMediaDevices.videoInputs():
            if cameraDevice.id() == cameraId:
                self.setCamera(cameraDevice)

                settings = QSettings()
                settings.setValue('default_camera', cameraId)

                break

    def setCamera(self, cameraDevice):
        self.setWindowTitle(cameraDevice.description())

        if self.camera:
            self.camera.stop()

        self.camera = QCamera(cameraDevice)
        if self.camera.isFocusModeSupported(QCamera.FocusModeAutoNear):
            self.camera.setFocusMode(QCamera.FocusModeAutoNear)
        self.captureSession.setCamera(self.camera)

        self.camera.errorOccurred.connect(self.displayCameraError)

        self.imageCapture = QImageCapture()
        self.captureSession.setImageCapture(self.imageCapture)
        self.imageCapture.readyForCaptureChanged.connect(self.readyForCapture)
        self.imageCapture.imageCaptured.connect(self.processCapturedImage)
        self.imageCapture.errorOccurred.connect(self.displayCaptureError)

        self.captureSession.setVideoOutput(self.viewfinder)

        self.camera.start()

    def shoot(self):
        if self.imageCapture.isReadyForCapture():
            self.first_capture_timer.start(2500)
            self.first_capture_timer.setSingleShot(True)

            self.imageCapture.capture()

    def done(self, r):
        if self.camera:
            self.camera.stop()

        super().done(r)

    def readyForCapture(self, ready):
        self.shootBtn.setEnabled(ready)

    def processCapturedImage(self, _requestId, img):
        self.first_capture_timer.stop()

        self.image = img
        self.accept()

    def firstCaptureTimeout(self):
        QMessageBox.warning(self, self.tr("Scan barcode"),
            self.tr("Camera not available or disabled by antivirus"))

    def displayCameraError(self):
        if self.camera.error() != QCamera.NoError:
            QMessageBox.warning(self, self.tr("Camera Error"),
                                self.camera.errorString())

    def displayCaptureError(self, _id, _error, errorString):
        QMessageBox.warning(self, "Image Capture Error", errorString)
