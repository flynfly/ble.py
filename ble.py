import asyncio
import qasync
import sys
import collections
from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QPushButton, QLabel
from PyQt5.QtCore import QThread, pyqtSignal
from bleak import BleakScanner, BleakClient
from pyqtgraph.Qt import QtGui, QtCore
import pyqtgraph as pg

import numpy as np
from collections import deque

from datetime import datetime

class ConnectThread(QThread):
    connectionResult = pyqtSignal(str, bool, int, str)
    dataReady = pyqtSignal(list)  # Signal to send signed_data to main GUI
    uuid=None
    wx=[]
    wy=[]
    wz=[]
    ax=[]
    ay=[]
    az=[]
    f=[]

    def __init__(self, address):
        QThread.__init__(self)
        self.address = address
        self.client = None
        self.start_time = None
        self.flag=0

    def save_data_to_file(self):
        # Combine data and save to one file
        data = {
            "wx": self.wx,
            "wy": self.wy,
            "wz": self.wz,
            "ax": self.ax,
            "ay": self.ay,
            "az": self.az,
            "f": self.f
        }
        np.savez("data.npz", **data)

    def run(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(self.connect())

    async def stop_all(self):
        self.flag=0
        self.start_time = None  # Stop timer
        try:
            if self.client.is_connected:
                await self.client.stop_notify(self.uuid)
                await self.client.disconnect()
        except Exception as e:
            print(f"Exception: {e}")
        finally:
            self.client = None
            self.uuid = None

    def swap_hex_pairs(self, packet):
        data = packet.split()
        swapped_data = [data[i:i + 2][::-1] for i in range(0, len(data), 2)]
        swapped_packet = ' '.join([' '.join(pair) for pair in swapped_data])
        return swapped_packet

    def hex_to_signed_decimal(self,hex_str):
        num = int(hex_str, 16)
        if num & (1 << 15):
            num -= 1 << 16
        return num

    def handling(self, bytes):
        l = [f'{i:02x}' for i in bytes]
        s=" ".join(l)
        # 分割数据
        packets = s.split(" 0d 0a a5 5a ")
        for packet in packets:
            # 移除多余的空格，并且分割数据
            data = packet.strip().split()
            # 检查数据是否符合要求
            if len(data) == 14:
                swaped=self.swap_hex_pairs(packet).split()
                data_no_spaces = [''.join(swaped[i:i + 2]) for i in range(0, len(swaped), 2)]
                signed_data = [self.hex_to_signed_decimal(hex_str) for hex_str in data_no_spaces]

                for i in range(3):
                    signed_data[i]=round(signed_data[i]*8.75/1000,2)
                    signed_data[i+3] = round(signed_data[i+3]*0.061/1000,2)

                    self.wx.append(signed_data[0])
                    self.wy.append(signed_data[1])
                    self.wz.append(signed_data[2])
                    self.ax.append(signed_data[3])
                    self.ay.append(signed_data[4])
                    self.az.append(signed_data[5])
                    self.f.append(signed_data[6])

                self.dataReady.emit(signed_data)
                print(signed_data, end="\n")


    def notification_handler(self,sender , data):
        self.handling(data)

    async def connect(self):
        attempts = 0
        connected = False
        while not connected:
            attempts += 1
            try:
                self.client = BleakClient(self.address)
                connected = await self.client.connect()
                if connected:
                    self.start_time = datetime.now()
                    self.uuid = self.client.services.services[9].characteristics[0].uuid
                    await self.client.start_notify(self.uuid, self.notification_handler)
                    self.flag=1
                    while connected and self.flag==1:
                        if self.start_time:
                            elapsed_time = str(int((datetime.now() - self.start_time).total_seconds()))
                        self.connectionResult.emit(self.address, connected, attempts, elapsed_time)
                        await asyncio.sleep(1)  # This will keep your program running
            except Exception as e:
                pass
            finally:
                if not connected:
                    await asyncio.sleep(1)
                    self.client = None  # important to avoid issues if connection fails

class ScanThread(QThread):
    deviceFound = pyqtSignal(str)

    def run(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(self.scan())

    async def scan(self):
        # target_device_name = "D36_787F67"
        target_device_name = "Myhand2"
        scanner = BleakScanner()
        while True:
            devices = await scanner.discover()
            for device in devices:
                if device.name == target_device_name:
                    self.deviceFound.emit(device.address)
                    return



class App(QWidget):
    def __init__(self):
        super().__init__()
        self.address=None

        self.setWindowTitle('Bluetooth Scanner')
        self.setGeometry(300, 300, 300, 200)

        layout = QVBoxLayout()

        self.startButton = QPushButton('Start Scanning')
        self.startButton.clicked.connect(self.start_scanning)
        layout.addWidget(self.startButton)
        self.startButton = QPushButton('Start')
        self.startButton.clicked.connect(self.start_actions)
        layout.addWidget(self.startButton)
        self.stopButton = QPushButton('Stop')
        self.stopButton.clicked.connect(lambda: asyncio.ensure_future(self.stop_actions()))
        layout.addWidget(self.stopButton)

        self.stopButton.setEnabled(0)
        self.startButton.setEnabled(0)

        self.label = QLabel('Ready to scan')
        layout.addWidget(self.label)

        # Initialize deque with a max length of 1000 for each data series
        self.data1 = collections.deque(maxlen=500)
        self.data2 = collections.deque(maxlen=500)
        self.data3 = collections.deque(maxlen=500)
        self.data4 = collections.deque(maxlen=500)
        self.data5 = collections.deque(maxlen=500)
        self.data6 = collections.deque(maxlen=500)
        self.data7 = collections.deque(maxlen=500)

        # Initialize plot widget
        # pg.setConfigOption('background', 'w')  # 全局设定背景颜色为白色
        self.plotWidget = pg.GraphicsLayoutWidget()

        # Create 3 PlotItems (axes)
        self.plot1 = self.plotWidget.addPlot()
        self.plot1.setYRange(-500, 500)
        self.plotWidget.nextRow()
        self.plot2 = self.plotWidget.addPlot()
        self.plot2.setYRange(-10, 10)
        self.plotWidget.nextRow()
        self.plot3 = self.plotWidget.addPlot()
        self.plot3.setYRange(-1000, 1000)

        self.curve1 = self.plot1.plot(pen='r')
        self.curve2 = self.plot1.plot(pen='g')
        self.curve3 = self.plot1.plot(pen='b')
        self.curve4 = self.plot2.plot(pen='r')
        self.curve5 = self.plot2.plot(pen='g')
        self.curve6 = self.plot2.plot(pen='b')
        self.curve7 = self.plot3.plot(pen='r')


        # Add plot widget to layout
        layout.addWidget(self.plotWidget)

        self.scanThread = ScanThread()
        self.scanThread.deviceFound.connect(self.connect_device)

        self.setLayout(layout)

    def update_plot(self, data):
        # Append data to the respective deques
        self.data1.append(data[0])
        self.data2.append(data[1])
        self.data3.append(data[2])
        self.data4.append(data[3])
        self.data5.append(data[4])
        self.data6.append(data[5])
        self.data7.append(data[6])

        self.curve1.setData(self.data1)
        self.curve2.setData(self.data2)
        self.curve3.setData(self.data3)
        self.curve4.setData(self.data4)
        self.curve5.setData(self.data5)
        self.curve6.setData(self.data6)
        self.curve7.setData(self.data7)


    def start_scanning(self):
        if not self.scanThread.isRunning():
            self.scanThread.start()
            self.label.setText('Scanning...')

    def connect_device(self, address):
        self.address = address
        self.connectThread = None
        self.connectThread = ConnectThread(self.address)
        self.label.setText('Standby')
        self.startButton.setEnabled(1)


    def show_connection_result(self, address, connected, attempts, elapsed_time):
        if connected:
            self.label.setText(f"Connected to {address} for {elapsed_time} secends")
        else:
            self.label.setText(f"Failed to connect to {address}, attempts: {attempts}")
            self.connectThread.start()

    def start_actions(self):
        self.connectThread = ConnectThread(self.address)  # create new ConnectThread instance here
        self.connectThread.connectionResult.connect(self.show_connection_result)
        self.connectThread.dataReady.connect(self.update_plot)
        self.connectThread.start()
        self.label.setText('Connecting...')
        self.startButton.setEnabled(0)
        self.stopButton.setEnabled(1)

    async def stop_actions(self):
        if self.connectThread is not None:
            self.connectThread.save_data_to_file()
            await self.connectThread.stop_all()
            self.label.setText('Stopped.')
            self.startButton.setEnabled(1)
            self.stopButton.setEnabled(0)



if __name__ == '__main__':
    app = QApplication(sys.argv)

    loop = qasync.QEventLoop(app)
    asyncio.set_event_loop(loop)

    ex = App()
    ex.show()

    with loop:
        sys.exit(loop.run_forever())