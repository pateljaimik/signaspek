import asyncio
import time
from multiprocessing import JoinableQueue,Queue, Process
import sounddevice as sd
import numpy as np
import sys
from signalling import WebsocketSignaling,BYE

from aiortc import RTCIceCandidate, RTCPeerConnection, RTCSessionDescription

reciever_audio_queue= JoinableQueue()
text_queue= JoinableQueue()
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


async def processing_client(pc, signaling):
    await signaling.connect()

    async def sendText(channel):
            while True:
                try:
                    text= text_queue.get(block=False)
                    channel.send(text)
                    print(f"Sending text data ")
                    text_queue.task_done()
                except:
                    pass
                await asyncio.sleep(1)

    

    @pc.on("datachannel")
    def on_datachannel(channel):
        channel_log(channel, "-", "created by remote party")
        
        @channel.on("message")
        def on_message(message):
            audio_np = np.frombuffer(message, dtype=np.int16).astype(np.float32) / 32768.0
            print("Recieved audio data")

            try:
                reciever_audio_queue.put_nowait(audio_np)
            except  Queue.Full:
                print("Queue is full")
        
        asyncio.create_task(sendText(channel))
    
    await signaling.send("start")
    await consume_signaling(pc, signaling)



def process_audio(audio_queue,text_q):
    import whisper
    import torch

    print("Cuda device is {}".format("available" if torch.cuda.is_available() else "not available"))
    audio_model = whisper.load_model("medium.en",device="cuda")
    print("Model loaded.")

    while True:
        audio_data = None
        try:
            audio_data=audio_queue.get()
            sd.play(audio_data,sampling_rate)
            result = audio_model.transcribe(audio_data, fp16=torch.cuda.is_available())
            text = result['text'].strip()
            print("Got text")
            print(text)
            text_q.put_nowait(text)
            audio_queue.task_done()
            
        except Queue.empty:
            time.sleep(.2)

if __name__ == "__main__":

    p = Process(target=process_audio, args=(reciever_audio_queue,text_queue))
    p.start()
    print("Process started")

    signaling = WebsocketSignaling("raspberrypi.local","8765")
    
    pc = RTCPeerConnection()
    coro = processing_client(pc, signaling)

    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(coro)
    except KeyboardInterrupt:
        print("Recieved keyboard interrupt")
    finally:
        reciever_audio_queue.close()
        text_queue.close()
        loop.run_until_complete(pc.close())
        loop.run_until_complete(signaling.close())
    p.join()

