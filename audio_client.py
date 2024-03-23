#!/usr/bin/env python

import pyaudio
import socket
import sys

# import asyncio
import time
from multiprocessing import JoinableQueue,Queue, Process
# import sounddevice as sd
import speech_recognition as sr
import numpy as np
import sys

FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 44100
CHUNK = 4096

reciever_audio_queue= JoinableQueue()
text_queue= JoinableQueue()
sampling_rate= 44100
recorder= sr.Recognizer()
recorder.energy_threshold = 1000
# Definitely do this, dynamic energy compensation lowers the energy threshold dramatically to a point where the SpeechRecognizer never stops recording.
recorder.dynamic_energy_threshold = False

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
            # sd.play(audio_data,sampling_rate)
            result = audio_model.transcribe(audio_data, fp16=torch.cuda.is_available())
            text = result['text'].strip()
            print("Got text")
            print(text)
            text_q.put_nowait(text)
            # audio_queue.task_done()
            
        except Queue.empty:
            time.sleep(.2)

s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.connect((sys.argv[1], int(sys.argv[2])))
audio = pyaudio.PyAudio()
stream = audio.open(format=FORMAT, channels=CHANNELS, rate=RATE, output=True, frames_per_buffer=CHUNK)

try:
    while True:
        data = s.recv(CHUNK)  # audio data stream
        stream.write(data)










except KeyboardInterrupt:
    pass

print('Shutting down')
s.close()
stream.close()
audio.terminate()