# encoding=utf-8

import unittest
import sys
from os import path
from socket import create_server, timeout
from threading import Thread, Event

sys.path.append('src')
sys.path.append(path.join('..', 'src'))
import socket_asyncio_threaded.client as sockco

MOCK_SERVER_ADDR = 'localhost'
MOCK_SERVER_PORT = 55580

class ServerThread(Thread):
    def __init__(self) -> None:
        super().__init__()
        self._stop_event = Event()
        self._stop_event.clear()

    def run(self):
        serversocket = create_server((MOCK_SERVER_ADDR, MOCK_SERVER_PORT))
        serversocket.listen()
        conn, addr = serversocket.accept()
        with conn:
            conn.settimeout(1)
            while not self._stop_event.is_set():
                try:
                    data = conn.recv(1024)
                except timeout:
                    continue
                if not data:
                    break
                for each_data in data.split(b'\n'):
                    if each_data == b'':
                        continue
                    print("{} wrote:".format(addr), end = ' ')
                    print(each_data)
                    conn.sendall(b"pong: %b\n" % each_data)
        serversocket.close()

    def stop(self):
        self._stop_event.set()

class MainTestCase(unittest.TestCase):
    def __init__(self, methodName: str = ...) -> None:
        super().__init__(methodName=methodName)
        self._server_thread = None

    def setUp(self) -> None:
        super().setUp()
        self._server_thread = ServerThread()
        self._server_thread.start()

    def tearDown(self) -> None:
        if self._server_thread is not None:
            self._server_thread.stop()
            self._server_thread.join()
        super().tearDown()

    def test_ping_pong(self):
        client = sockco.SocketClient()
        client.start_async(MOCK_SERVER_ADDR, MOCK_SERVER_PORT, sockco.RH_Splitter())
        for i in range(10):
            client.write_async(bytes(f'index {i}\n', encoding='utf-8'))
        for i in range(10):
            msg = client.read_async()
            self.assertTrue(str(msg, encoding='utf-8') == f'pong: index {i}\n')

if __name__ == '__main__':
    unittest.main()