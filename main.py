import asyncio
import sys
from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QPushButton, QListWidget, QMessageBox
from PyQt5.QtCore import QThread, pyqtSignal
from bleak import BleakScanner, BleakClient

class ConnectionThread(QThread):
    connectionResult = pyqtSignal(str, bool)
    c=3+4j
    print(c)
    def __init__(self, address):
        QThread.__init__(self)
        self.address = address

    def run(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(self.connect())

    async def connect(self):
        async with BleakClient(self.address) as client:
            connected = await client.is_connected()
            self.connectionResult.emit(self.address, connected)

class ScannerThread(QThread):
    devicesUpdated = pyqtSignal(list)

    def run(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(self.scan())

    async def scan(self):
        scanner = BleakScanner()
        while True:
            devices = await scanner.discover()
            valid_devices = [d for d in devices if d.name and d.name != 'N/A']
            self.devicesUpdated.emit(valid_devices)

class App(QWidget):
    def __init__(self):
        super().__init__()

        self.setWindowTitle('Bluetooth Scanner')
        self.setGeometry(300, 300, 300, 200)

        layout = QVBoxLayout()

        self.listWidget = QListWidget()
        self.listWidget.itemDoubleClicked.connect(self.connect_device)
        layout.addWidget(self.listWidget)

        self.startButton = QPushButton('Start Scanning')
        self.startButton.clicked.connect(self.start_scanning)
        layout.addWidget(self.startButton)

        self.setLayout(layout)

        self.scannerThread = ScannerThread()
        self.scannerThread.devicesUpdated.connect(self.update_devices)

    def start_scanning(self):
        if not self.scannerThread.isRunning():
            self.scannerThread.start()

    def update_devices(self, devices):
        self.listWidget.clear()
        for device in devices:
            self.listWidget.addItem(f"{device.name} ({device.address})")

    def connect_device(self):
        item = self.listWidget.currentItem()

        if item:
            address = item.text().split(" (")[1].split(")")[0]
            self.connectionThread = ConnectionThread(address)
            self.connectionThread.connectionResult.connect(self.show_connection_result)
            self.connectionThread.start()

    def show_connection_result(self, address, connected):
        QMessageBox.information(self, 'Connection Result', f"Connected to {address}: {connected}")

if __name__ == '__main__':
    app = QApplication(sys.argv)
    ex = App()
    ex.show()
    sys.exit(app.exec_())
