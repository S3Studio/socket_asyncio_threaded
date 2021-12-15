# encoding=utf-8

import asyncio
from threading import Thread, Event
import struct
from contextlib import closing

class ReceiveHandler(object):
    async def read_one_msg(self, reader: asyncio.StreamReader):
        raise NotImplementedError()

class RH_Splitter(ReceiveHandler):
    def __init__(self, separator: bytes = b'\n') -> None:
        super().__init__()
        self._separator = separator

    async def read_one_msg(self, reader: asyncio.StreamReader):
        return await reader.readuntil(self._separator)

class RH_HeaderSize(ReceiveHandler):
    def __init__(self, header_format: str = '=I') -> None:
        super().__init__()
        self._header_format = header_format
        self._header_len = struct.calcsize(self._header_format)

    async def read_one_msg(self, reader: asyncio.StreamReader):
        header = await reader.readexactly(self._header_len)
        msg_size = struct.unpack(header)
        return await reader.readexactly(msg_size)

class SocketClient(object):
    class StartTwiceException(Exception):
        def __str__(self) -> str:
            return 'SocketClient cannot be started twice, try creating another instance.'

    class NotReadyException(Exception):
        def __str__(self) -> str:
            return 'SocketClient is not ready, try calling "start_async" first.'

    class FinishedException(Exception):
        def __str__(self) -> str:
            return 'SocketClient is finished, caused by reader which is disconnected or at eof.'

    def __init__(self) -> None:
        super().__init__()
        self._event_loop = None
        self._prepare_event = Event()
        self._prepare_event.clear()
        self._finish_event = Event()
        self._finish_event.clear()
        self._host = ''
        self._port = 0
        self._receive_handler = None
        self._thread = None

        self._async_reader = None
        self._async_writer = None
        self._write_lock = None
        self._msg_queue = None

    def is_preparing(self) -> bool:
        """Check if client is preparing for working

        Return True if:
            Working thread is alive, and preparation is not finished so that
            real working loop (read from socket) is not started.
        """
        return self._event_loop is not None and \
               not self._prepare_event.is_set() and \
               self._thread is not None and self._thread.is_alive()

    def is_running(self) -> bool:
        """Check if client is running

        Return True if:
            Working thread is alive, and preparation is finished and real working
            loop (read from socket) is still running and not finished.
        """
        return self._event_loop is not None and \
               self._prepare_event.is_set() and \
               self._thread is not None and self._thread.is_alive()

    def start_async(self, host: str, port: int, handler: ReceiveHandler) -> None:
        """Start thread for working (read from socket)

        Include environment preparation (open socket connection, etc.). Must be
        called first, before "write_async", "read_async", etc.
        """
        if self._event_loop is not None:
            raise SocketClient.StartTwiceException()

        self._host = host
        self._port = port
        self._receive_handler = handler

        self._event_loop = asyncio.new_event_loop()
        self._thread = Thread(target=self._start_loop, args=())
        self._thread.start()

    def write_async(self, data):
        """Write data to socket
        """
        return self._call_async(self._write(data))

    def read_async(self):
        """Read data from socket

        There is a working loop which is doing the real reading, so previous
        received data may be returned.
        """
        return self._call_async(self._get_msg())

    def _start_loop(self) -> None:
        if self._event_loop is None:
            return

        asyncio.set_event_loop(self._event_loop)

        self._event_loop.run_until_complete(self._prepare())
        self._prepare_event.set()
        self._event_loop.run_until_complete(self._read_loop())

        # Wait for all tasks and do cleanups
        g = asyncio.gather(*asyncio.all_tasks(self._event_loop), return_exceptions = True)
        self._event_loop.run_until_complete(g)
        self._event_loop.run_until_complete(self._event_loop.shutdown_asyncgens())
        self._event_loop.close()

    def _call_async(self, coro):
        with closing(coro):
            if self._event_loop is None:
                raise SocketClient.NotReadyException()
            if self._finish_event.is_set():
                raise SocketClient.FinishedException()

            self._prepare_event.wait()

            return asyncio.run_coroutine_threadsafe(coro, self._event_loop).result()

    async def _prepare(self):
        self._async_reader, self._async_writer = await asyncio.open_connection(self._host, self._port)
        self._write_lock = asyncio.Lock()
        self._msg_queue = asyncio.Queue()

    async def _write(self, data: bytes) -> None:
        async with self._write_lock:
            self._async_writer.write(data)

    async def _get_msg(self):
        while True:
            try:
                return await asyncio.wait_for(self._msg_queue.get(), 1.0)
            except asyncio.TimeoutError as e:
                if self._finish_event.is_set():
                    raise SocketClient.FinishedException()

    async def _read_loop(self):
        while True:
            try:
                item = await self._receive_handler.read_one_msg(self._async_reader)
                await self._msg_queue.put(item)
            except ConnectionError as e:
                break
            except Exception as e:
                if self._async_reader.at_eof():
                    break
        self._finish_event.set()
