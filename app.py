import os
import sys
import time
from pathlib import Path

import albumentations as A
import cv2
import numpy as np
import onnx
import onnxruntime
import win32api
from PIL import ImageGrab
from PyQt6.QtCore import QSize, Qt, QTimer, QUrl
from PyQt6.QtGui import QIcon, QImage, QPixmap
from PyQt6.QtMultimedia import QAudioOutput, QMediaPlayer
from PyQt6.QtWidgets import (
    QApplication,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)


class SetMonitorWindow(QWidget):
    def __init__(self, alarm_button):
        super().__init__()

        self.alarm_button = alarm_button

        self.setWindowTitle("화면세팅")
        self.setObjectName("setMonitorWindow")

        layout = QVBoxLayout()

        self.img_label = QLabel()
        img = cv2.imread("./icon/no_image.png")
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        img = cv2.resize(img, (320, 320))

        img = QImage(img.data, 320, 320, 320 * 3, QImage.Format.Format_RGB888)
        self.pixmap = QPixmap.fromImage(img)
        self.img_label.setPixmap(self.pixmap)
        self.img_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.img_label)

        self.monitors = win32api.EnumDisplayMonitors()
        self.monitor_button_list = [
            QPushButton(f"모니터 {i+1}번") for i in range(len(self.monitors))
        ]

        for i, button in enumerate(self.monitor_button_list):
            button.setStyleSheet("background-color: #999999;")
            button.clicked.connect(
                lambda _, idx=i: self.select_monitor_button_clicked(_, idx)
            )
            layout.addWidget(button)

        self.submit_button = QPushButton("선택완료")
        self.submit_button.clicked.connect(self.submit_button_click)
        self.submit_button.setDisabled(True)
        layout.addWidget(self.submit_button)

        self.setLayout(layout)
        self.setFixedSize(QSize(360, 360 + 100 * (len(self.monitors) + 1)))

    def select_monitor_button_clicked(self, _, moniter_number):
        for i, button in enumerate(self.monitor_button_list):
            if i == moniter_number:
                button.setStyleSheet("background-color: #006ee6;")
            else:
                button.setStyleSheet("background-color: #999999;")

        self.monitor_number = moniter_number
        self.monitor = self.monitors[moniter_number][0]
        margin_w, margin_h, w, h = win32api.GetMonitorInfo(self.monitor)["Monitor"]

        self.left = ((w - margin_w - 360) // 2) + margin_w
        self.top = ((h - margin_h - 360) // 2) + margin_h
        self.right = self.left + 360
        self.bottom = self.top + 360

        self.timer = QTimer()
        self.timer.start(20)
        self.timer.timeout.connect(self.capture_display)

        self.submit_button.setEnabled(True)

    def capture_display(self):
        img = ImageGrab.grab(
            bbox=(self.left, self.top, self.right, self.bottom), all_screens=True
        )
        img = np.array(img, dtype=np.float32)
        img = cv2.resize(img, (320, 320))
        img = np.array(img, dtype=np.uint8)

        img = QImage(img.data, 320, 320, 320 * 3, QImage.Format.Format_RGB888)
        self.pixmap = QPixmap.fromImage(img)
        self.img_label.setPixmap(self.pixmap)

    def submit_button_click(self):
        self.timer.stop()
        self.alarm_button.setEnabled(True)
        self.hide()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.label = {0: "투망", 1: "찌낚시", 2: "Normal"}

        self.setWindowTitle("LostARK Fishing Alarm")
        self.setWindowIcon(QIcon("./icon/icon.png"))
        self.setFixedSize(QSize(600, 300))

        h_layout = QHBoxLayout()
        button_layout = QVBoxLayout()
        audio_layout = QVBoxLayout()

        # button layout
        self.help_button = QPushButton("사용방법")

        self.set_monitor_button = QPushButton("모니터선택")
        self.set_monitor_button.clicked.connect(self.set_monitor_button_clicked)

        self.alarm_button = QPushButton("알람켜기")
        self.alarm_button.clicked.connect(self.alarm_button_clicked)
        self.alarm_button.setDisabled(True)

        button_layout.addWidget(self.help_button)
        button_layout.addWidget(self.set_monitor_button)
        button_layout.addWidget(self.alarm_button)

        h_layout.addLayout(button_layout)

        # audio layout
        file_names = os.listdir("audio")
        mp3_files = ["알람을 선택해 주세요."] + [
            file for file in file_names if file.lower().endswith(".mp3")
        ]
        self.fishing_interval = 0.0
        self.castingnet_interval = 0.0

        self.label1 = QLabel("찌낚시 감지 알람")
        combo_hbox1 = QHBoxLayout()
        self.combobox1 = QComboBox()
        self.combobox1.addItems(mp3_files)
        self.combobox1.activated.connect(self.combobox1_update)
        self.play_button1 = QPushButton()
        self.play_button1.setObjectName("play")
        self.play_button1.clicked.connect(self.play_sound_fishing)
        self.sound_file1 = "알람을 선택해 주세요."
        combo_hbox1.addWidget(self.combobox1)
        combo_hbox1.addWidget(self.play_button1)

        self.slider1 = QSlider(Qt.Orientation.Horizontal)
        self.slider1.setRange(0, 100)
        self.slider1.setSingleStep(1)
        self.slider1.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.slider1.setTickInterval(10)
        self.slider1.valueChanged.connect(self.volume1_slider_update)
        self.player1 = QMediaPlayer()
        self.audio_output1 = QAudioOutput()
        self.audio_output1.setVolume(0)

        self.label2 = QLabel("투망 감지 알람")
        combo_hbox2 = QHBoxLayout()
        self.combobox2 = QComboBox()
        self.combobox2.addItems(mp3_files)
        self.combobox2.activated.connect(self.combobox2_update)
        self.play_button2 = QPushButton()
        self.play_button2.setObjectName("play")
        self.play_button2.clicked.connect(self.play_sound_castingnet)
        self.sound_file2 = "알람을 선택해 주세요."
        combo_hbox2.addWidget(self.combobox2)
        combo_hbox2.addWidget(self.play_button2)

        self.slider2 = QSlider(Qt.Orientation.Horizontal)
        self.slider2.setRange(0, 100)
        self.slider2.setSingleStep(1)
        self.slider2.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.slider2.setTickInterval(10)
        self.slider2.valueChanged.connect(self.volume2_slider_update)
        self.player2 = QMediaPlayer()
        self.audio_output2 = QAudioOutput()
        self.audio_output2.setVolume(0)

        audio_layout.addWidget(self.label1)
        audio_layout.addLayout(combo_hbox1)
        audio_layout.addWidget(self.slider1)
        audio_layout.addWidget(self.label2)
        audio_layout.addLayout(combo_hbox2)
        audio_layout.addWidget(self.slider2)

        h_layout.addLayout(audio_layout)

        widget = QWidget()
        widget.setLayout(h_layout)
        self.setCentralWidget(widget)

        self.set_monitor_window = SetMonitorWindow(self.alarm_button)

    def set_monitor_button_clicked(self):
        self.set_monitor_window.show()

    def alarm_button_clicked(self):
        self.left = self.set_monitor_window.left
        self.top = self.set_monitor_window.top
        self.right = self.set_monitor_window.right
        self.bottom = self.set_monitor_window.bottom

        if self.alarm_button.text() == "알람켜기":
            self.alarm_button.setText("알람끄기")
            self.alarm_button.setStyleSheet("background-color: #ff5000;")

            self.onnx_model = onnx.load("./model/output.onnx")
            onnx.checker.check_model(self.onnx_model)
            self.ort_session = onnxruntime.InferenceSession("./model/output.onnx")

            self.timer = QTimer()
            self.timer.start(15)
            self.timer.timeout.connect(self.on_alarm)

        else:
            self.alarm_button.setText("알람켜기")
            self.alarm_button.setStyleSheet("background-color: #006ee6;")
            self.timer.stop()

    def on_alarm(self):
        img = ImageGrab.grab(
            bbox=(self.left, self.top, self.right, self.bottom), all_screens=True
        )
        img = A.normalize(
            np.array(img, dtype=np.float32),
            mean=(0.485, 0.456, 0.406),
            std=(0.229, 0.224, 0.225),
        )
        img = np.transpose(img, (2, 0, 1))[np.newaxis, ...]
        img = {self.ort_session.get_inputs()[0].name: img}

        onnx_output = self.ort_session.run(None, img)
        y = np.squeeze(self.soft_max(onnx_output))
        print(y)
        if y[1] >= 0.95 and (time.time() - self.fishing_interval) > 5.0:
            self.fishing_interval = time.time()
            self.player1.play()
        elif y[0] >= 0.50 and (time.time() - self.castingnet_interval) > 5.0:
            self.castingnet_interval = time.time()
            self.player2.play()

    def soft_max(self, x):
        e_x = np.exp(x - np.max(x))
        return e_x / e_x.sum()

    def volume1_slider_update(self, value):
        self.audio_output1.setVolume(value / 100)

    def volume2_slider_update(self, value):
        self.audio_output2.setVolume(value / 100)

    def combobox1_update(self):
        self.sound_file1 = self.combobox1.currentText()
        self.player1.setSource(QUrl.fromLocalFile("./audio/" + self.sound_file1))

    def combobox2_update(self):
        self.sound_file2 = self.combobox2.currentText()
        self.player2.setSource(QUrl.fromLocalFile("./audio/" + self.sound_file2))

    def play_sound_fishing(self):
        if self.sound_file1 == "알람을 선택해 주세요.":
            pass
        else:
            self.player1.setAudioOutput(self.audio_output1)
            self.player1.play()

    def play_sound_castingnet(self):
        if self.sound_file2 == "알람을 선택해 주세요.":
            pass
        else:
            self.player2.setAudioOutput(self.audio_output2)
            self.player2.play()


app = QApplication(sys.argv)
app.setStyleSheet(Path("./qss/main.qss").read_text())

window = MainWindow()
window.show()

app.exec()
