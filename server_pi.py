from signalling import WebsocketSignaling,BYE
import asyncio
import speech_recognition as sr
import queue
from aiortc import RTCIceCandidate, RTCPeerConnection, RTCSessionDescription
from multiprocessing import Process
from ctypes import *
import sys
import os

audio_queue = queue.Queue()
text_queue = asyncio.Queue()
OLED_started= asyncio.Event()
OLED_Process= None
sampling_rate= 16000

def channel_log(channel, t, message):
    print("channel(%s) %s %s" % (channel.label, t, message))

async def consume_signaling(pc, signaling):
    while True:
        obj = await signaling.receive()

        if isinstance(obj, str) and obj == "start":
            await pc.setLocalDescription(await pc.createOffer())
            await signaling.send(pc.localDescription)
        if isinstance(obj, RTCSessionDescription):
            await pc.setRemoteDescription(obj)

            if obj.type == "offer":
                # send answer
                await pc.setLocalDescription(await pc.createAnswer())
                await signaling.send(pc.localDescription)
        elif isinstance(obj, RTCIceCandidate):
            await pc.addIceCandidate(obj)
        elif obj is BYE:
            print("Exiting")
            break

async def server(pc, signaling):
    await signaling.connect()

    channel = pc.createDataChannel("audio")
    channel_log(channel, "-", "created by local party\n")

    async def sendAudio(chan):
        while True:
            if(not audio_queue.empty()):
                audio_data=b''.join(audio_queue.queue)
                chan.send(audio_data)
                audio_queue.queue.clear()
                audio_queue.task_done()
                print(f"Sending audio data of lenght: {sys.getsizeof(audio_data)} to channel {channel.label}")
            await asyncio.sleep(1)

    @channel.on("open")
    def on_open():
        asyncio.create_task(sendAudio(channel))

    @channel.on("message")
    def on_message(message):
        print(f"Recieved message:{message}")
        if(OLED_started.is_set() is False):
            OLED_started.set()
            OLED_Process.start()

        try:
            text_queue.put_nowait(message)
        except:
            print("Text queue is full")


    await consume_signaling(pc, signaling)

# Creating Unix socket to send text data to OLED display application


async def unix_socket_callback(reader, writer):

    while True:
        text= await text_queue.get()
        print("Writing to socket")
        writer.write((text+" ").encode())
        await writer.drain()

async def unix_soc_server():
    socket_path="/tmp/SignaSpek"
    try:
        os.unlink(socket_path)
    except OSError as error:
        if os.path.exists(socket_path):
            raise error
    soc_server= await asyncio.start_unix_server(client_connected_cb=unix_socket_callback,path=socket_path)
    print("Unix socket intialized")
    async with soc_server:
        await soc_server.serve_forever()
    print("Socket server closed")

async def mainAsync(pc,signaling):
    a=asyncio.create_task(unix_soc_server())
    b= asyncio.create_task(server(pc,signaling))
    await asyncio.gather(a,b)

# Code to get rid of JACK errors on startup
ERROR_HANDLER_FUNC = CFUNCTYPE(None, c_char_p, c_int, c_char_p, c_int, c_char_p)

def py_error_handler(filename, line, function, err, fmt):
    pass

def OLED_startup():
    os.system(' cd /home/pi/OLED_Module_Code/RaspberryPi/c && sudo ./main 1.51 > /tmp/rc.local.OLED.log 2>&1')
    print("Started OLED Driver\n")

c_error_handler = ERROR_HANDLER_FUNC(py_error_handler)

asound = cdll.LoadLibrary("libasound.so.2")



if __name__ == "__main__":
        asound.snd_lib_error_set_handler(c_error_handler)
        recorder = sr.Recognizer()
        recorder.energy_threshold = 1000
        recorder.dynamic_energy_threshold = False

        source = sr.Microphone(sample_rate=sampling_rate)

        with source:
            recorder.adjust_for_ambient_noise(source)

        def audio_callback(_, audio:sr.AudioData):
            data = audio.get_raw_data()
            audio_queue.put(data)

        recorder.listen_in_background(source, audio_callback, phrase_time_limit=2)
        print("Microphone initialized")

        OLED_Process= Process(target=OLED_startup)
        loop = asyncio.get_event_loop()
        signaling = WebsocketSignaling("0.0.0.0","8765")
        pc = RTCPeerConnection()
        coro = mainAsync(pc,signaling)


        try:
            loop.run_until_complete(coro)
        except KeyboardInterrupt:
            print("Recieved keyboard interrupt")
        finally:
            OLED_Process.terminate()
            loop.run_until_complete(pc.close())
            loop.run_until_complete(signaling.close())

        asound.snd_lib_error_set_handler(None)