import argparse
import asyncio
import logging
import time
import queue
import speech_recognition as sr
import numpy as np
import sounddevice as sd
from multiprocessing import Queue, Process
import sys
from signalling import WebsocketSignaling

from aiortc import RTCIceCandidate, RTCPeerConnection, RTCSessionDescription
from aiortc.contrib.signaling import BYE, add_signaling_arguments, create_signaling

audio_queue = queue.Queue()
reciever_audio_queue= Queue()
sampling_rate= 8000
def channel_log(channel, t, message):
    print("channel(%s) %s %s" % (channel.label, t, message))


def channel_send(channel, message):
    #channel_log(channel, ">", message)
    channel.send(message)


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


time_start = None


def current_stamp():
    global time_start

    if time_start is None:
        time_start = time.time()
        return 0
    else:
        return int((time.time() - time_start) * 1000000)

async def run_answer(pc, signaling):
    await signaling.connect()

    async def sendMessage(channel):
        while True:
            if(not audio_queue.empty()):
                channel.send(b''.join(audio_queue.queue))
                audio_queue.queue.clear()
            await asyncio.sleep(.5)

    @pc.on("datachannel")
    def on_datachannel(channel):
        channel_log(channel, "-", "created by remote party")

        #asyncio.ensure_future(sendMessage(channel))
        
        @channel.on("message")
        def on_message(message):
            #channel_log(channel, "<", message)
            audio_np = np.frombuffer(message, dtype=np.int16).astype(np.float32) / 32768.0
            sd.play(audio_np,sampling_rate)
            try:
                reciever_audio_queue.put_nowait(audio_np)
            except  queue.Full:
                print("Queue is full")
            print(f"Recieved message is of type:{type(message)}")
            print(f"Type of each index:{type(message[0])}")
            print(f"Each sample is of size: {sys.getsizeof(message[0])}")
    
    await signaling.send("start")
    await consume_signaling(pc, signaling)


async def run_offer(pc, signaling):
    await signaling.connect()

    channel = pc.createDataChannel("chat")
    channel_log(channel, "-", "created by local party")

    async def sendAudio(channel):
        while True:
            if(not audio_queue.empty()):
                audio_data=b''.join(audio_queue.queue)
                channel.send(audio_data)
                audio_queue.queue.clear()
                print(f"Sending audio data of lenght: {sys.getsizeof(audio_data)}")
            await asyncio.sleep(.5)

    @channel.on("open")
    def on_open():
        asyncio.ensure_future(sendAudio(channel))

    # @channel.on("message")
    # def on_message(message):
    #     #channel_log(channel, "<", message)
    #     print(f"Recieved message is of type:{type(message)}, echoing it back")
    #     channel_send(channel,message)

    # send offer
    await consume_signaling(pc, signaling)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Data channels ping/pong")
    parser.add_argument("role", choices=["offer", "answer"])
    parser.add_argument("--verbose", "-v", action="count")
    add_signaling_arguments(parser)

    args = parser.parse_args()

    if args.verbose:
        logging.basicConfig(level=logging.DEBUG)

    def audio_callback(_, audio:sr.AudioData):
        data = audio.get_raw_data()
        audio_queue.put(data)

    signaling = WebsocketSignaling("raspberrypi.local","8765")
    pc = RTCPeerConnection()
    p = None
    if args.role == "offer":
        recorder = sr.Recognizer()
        recorder.energy_threshold = 1000
        recorder.dynamic_energy_threshold = False

        source = sr.Microphone(sample_rate=sampling_rate)

        with source:
            recorder.adjust_for_ambient_noise(source)

        recorder.listen_in_background(source, audio_callback, phrase_time_limit=1.2)
        print("Microphone initialized")
        coro = run_offer(pc, signaling)
    else:
        import whisper
        import torch
        dummy_queue= Queue()
            #  while True:
            #      audio_data = None
            #      try:
            #          audio_data=queue.get()
            #          result = model.transcribe(audio_data, fp16=torch.cuda.is_available())
            #          text = result['text'].strip()
            #          print(text)
            #      except queue.empty:
            #          time.sleep(.05)
        
        print("Cuda device is {}".format("available" if torch.cuda.is_available() else "not available"))
        audio_model = whisper.load_model("medium.en",device="cuda")
        print("Model loaded.")
        # p = Process(target=process_audio,args=())
        # p.start()
       # print("Process started")
        coro = run_answer(pc, signaling)

    # run event loop
    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(coro)
    except KeyboardInterrupt:
        print("Recieved keyboard interrupt")
        pass
    finally:
        reciever_audio_queue.close()
             
        
        audio_queue.join()
        loop.run_until_complete(pc.close())
        loop.run_until_complete(signaling.close())