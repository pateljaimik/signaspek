from signalling import WebsocketSignaling,BYE
import asyncio
import speech_recognition as sr
import queue
from aiortc import RTCIceCandidate, RTCPeerConnection, RTCSessionDescription
import sys

audio_queue = queue.Queue()
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

    async def sendAudio():
        while True:
            if(not audio_queue.empty()):
                audio_data=b''.join(audio_queue.queue)
                channel.send(audio_data)
                audio_queue.queue.clear()
                audio_queue.task_done()
                print(f"Sending audio data of lenght: {sys.getsizeof(audio_data)} to channel {channel.label}")
                
            await asyncio.sleep(1)

    @channel.on("open")
    def on_open():
        asyncio.create_task(sendAudio())

    @channel.on("message")
    def on_message(message):
        print(message)
    
    await consume_signaling(pc, signaling)


    
if __name__ == "__main__":
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

        signaling = WebsocketSignaling("raspberrypi.local","8765")
        pc = RTCPeerConnection()
        coro = server(pc, signaling)

        loop = asyncio.get_event_loop()
        try:
            loop.run_until_complete(coro)
        except KeyboardInterrupt:
            print("Recieved keyboard interrupt")
        finally: 
            loop.run_until_complete(pc.close())
            loop.run_until_complete(signaling.close())
