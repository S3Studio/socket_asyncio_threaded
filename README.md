# socket_asyncio_threaded

**socket_asyncio_threaded**, or *sockco* as I like to call it, is a python library to send and receive data with *asyncio.StreamReader, asyncio.StreamWriter* in another **single** thread.

## Simple Usage

```
import socket_asyncio_threaded.client as sockco

if __name__ == '__main__':
    client = sockco.SocketClient()

    # Choose a ReceiveHandler from sockco like RH_Splitter, RH_HeaderSize,
    # or implement your own handler
    client.start_async(MOCK_SERVER_ADDR, MOCK_SERVER_PORT, sockco.RH_Splitter())

    # Now do something you want and write data at any time
    client.write_async(bytes(f'ping\n', encoding='utf-8'))

    # When needed, just read a pack of data, no need to be concerned about when to receive
    msg = client.read_async()
```

## Background and Notes

This code is used in my project which needs to read and write data with socket occasionally. If only *asyncio* is used, the event loop needs to run in the main thread; and reading/writing data from different threads needs a little bit more resource than coroutine. So I decided to put them together, which is this library.

Some notes I like to mention:

* Only client-side is available, and the implementation of server-side is under schedule.

* The lifecycle of *SocketClient* is the same as *StreamReader*, so it is not allowed to write data after the receiving direction is closed, even if the sending direction is still open.

## About

Version: 0.0.1

Auther: S3Studio

Url: https://github.com/S3Studio/socket_asyncio_threaded

New issues are welcomed
