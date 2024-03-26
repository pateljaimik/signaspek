import argparse
import io
import os
import speech_recognition as sr
import whisper

from datetime import datetime, timedelta
from queue import Queue
from tempfile import NamedTemporaryFile
from time import sleep

import numpy as np
import scipy.io.wavfile as wavfile
import scipy.signal as signal




def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="base", help="Model to use",
                        choices=["tiny", "base", "small", "medium", "large"])
    parser.add_argument("--non_english", action='store_true',
                        help="Don't use the english model.")
    parser.add_argument("--energy_threshold", default=1000,
                        help="Energy level for mic to detect.", type=int)
    parser.add_argument("--record_timeout", default=2,
                        help="How real time the recording is in seconds.", type=float)
    parser.add_argument("--phrase_timeout", default=1,## Default was 3
                        help="How much empty space between recordings before we "
                             "consider it a new line in the transcription.", type=float)
    args = parser.parse_args()

    model = args.model
    if args.model != "large" and not args.non_english:
        model = model + ".en"################################################## toggle between english only and all languages, Leave on EN as multilanguage support not yet ready
    audio_model = whisper.load_model(model)

    record_timeout = args.record_timeout
    phrase_timeout = args.phrase_timeout

    temp_file = NamedTemporaryFile().name
    transcription = ['']

    # The last time a recording was retreived from the queue.
    phrase_time = None
    # Current raw audio bytes.
    last_sample = bytes()
    # Thread safe Queue for passing data from the threaded recording callback.
    data_queue = Queue()

    # We use SpeechRecognizer to record our audio because it has a nice feauture where it can detect when speech ends.
    recorder = sr.Recognizer()
    recorder.energy_threshold = args.energy_threshold
    # Definitely do this, dynamic energy compensation lowers the energy threshold dramtically to a point where the SpeechRecognizer never stops recording.
    recorder.dynamic_energy_threshold =False####True##############################

    source = sr.Microphone(sample_rate=16000)

    

    with source:
        recorder.adjust_for_ambient_noise(source)
    
    
############################################## Filter Code ######################################################################## 


   ###########Filter Parameters
    cutoff_freq = 800  #All audio below this frequency will be removed 
    nyquist_freq = source.SAMPLE_RATE / 2
    order = 2  #higher values for sharper cutoff
    ripple_db = 0.5  # Adjust as needed (lower values for less distortion)

    
    b, a = signal.cheby1(order, ripple_db, cutoff_freq / nyquist_freq, btype='high')#This filter should eliminate background noise (Low frequency noise) while preserving the voice

    def apply_filter(data):
     
        samples = np.frombuffer(data, dtype=np.int16)# Converts byte string to array of samples
        
        # Apply the filter to the samples
        filtered_samples = signal.filtfilt(b, a, samples)#Applies the  high pass filter defined above
        
        
        filtered_data = filtered_samples.astype(np.int16).tobytes()#Convert filtered samples back to byte string to be interpreted by the model
        
        return filtered_data

        


    def apply_filter_and_export(data, filename): #Filters and saves recording for verification
        # Convert byte string to array of samples
        samples = np.frombuffer(data, dtype=np.int16)# Converts byte string to array of samples
        
        # Apply the filter to the samples
        filtered_samples = signal.filtfilt(b, a, samples)#Applies the high pass filter defined above
        
        
        filtered_samples = filtered_samples.astype(np.int16)
        filtered_samples_tobytes = filtered_samples.astype(np.int16).tobytes()#Convert filtered samples back to byte string to be interpreted by the model
        
        
        
        wavfile.write(filename, source.SAMPLE_RATE, filtered_samples)# Saves the filtered version of the last recording as a WAV file for verification

        return filtered_samples_tobytes


############################################## Filter Code End ######################################################################## 

    def record_callback(_, audio:sr.AudioData) -> None:
        """
        Threaded callback function to recieve audio data when recordings finish.
        audio: An AudioData containing the recorded bytes.
        """
        # Grab the raw bytes and push it into the thread safe queue.
        #data = audio.get_raw_data()#This is the unfiltered audio data 
        #data_queue.put(data) #Data being put in to the queue for transcripton

        #data = apply_filter(audio.get_raw_data())  #USE THIS when testing is complete, filter then put in data queue
        #data_queue.put(data)

        
        input_samples = np.frombuffer(audio.get_raw_data(), dtype=np.int16) 
        wavfile.write("input_samples.wav", source.SAMPLE_RATE, input_samples)# Saves the unfiltered version of the last recording as a WAV file for verification

        filtered_samples = apply_filter_and_export(audio.get_raw_data(), "filtered_output.wav") #This is the data being filtered, AND saved as WAV file, use only during testing
        data_queue.put(filtered_samples)
            



    # Create a background thread that will pass us raw audio bytes.
    # We could do this manually but SpeechRecognizer provides a nice helper.
    recorder.listen_in_background(source, record_callback, phrase_time_limit=record_timeout)

    # Cue the user that we're ready to go.
    print(model,"Model loaded.\n")####################################################################################################

    while True:
        try:
            now = datetime.utcnow()
            # Pull raw recorded audio from the queue.
            if not data_queue.empty():
                phrase_complete = False
                # If enough time has passed between recordings, consider the phrase complete.
                # Clear the current working audio buffer to start over with the new data.
                if phrase_time and now - phrase_time > timedelta(seconds=phrase_timeout):
                    last_sample = bytes()
                    phrase_complete = True
                # This is the last time we received new audio data from the queue.
                phrase_time = now

                # Concatenate our current audio data with the latest audio data.
                while not data_queue.empty():
                    data = data_queue.get()
                    last_sample += data

                # Use AudioData to convert the raw data to wav data.
                audio_data = sr.AudioData(last_sample, source.SAMPLE_RATE, source.SAMPLE_WIDTH)
                wav_data = io.BytesIO(audio_data.get_wav_data())

                # Write wav data to the temporary file as bytes.
                with open(temp_file, 'w+b') as f:
                    f.write(wav_data.read())

                # Read the transcription.
                result = audio_model.transcribe(temp_file)
                text = result['text'].strip()

                # If we detected a pause between recordings, add a new item to our transcripion.
                # Otherwise edit the existing one.
                if phrase_complete:
                    transcription.append(text)
                else:
                    transcription[-1] = text

                # Clear the console to reprint the updated transcription.
                os.system('cls' if os.name=='nt' else 'clear')
                for line in transcription:
                    print(line)
                    if(line==''):
                        print("empty") #If nothing is recorded, this is run to prevent pushing the text if we have nothing to send, "empty" will be removed later##################################################
                        
                    
                    else:
                        print("Line Output Test");#This runs when something has been transcribed, this is where you should put the communication to the display code sending 'line'##################################################
                

                    
                    
                # Flush stdout.
                print('', end='', flush=True)

                # Infinite loops are bad for processors, must sleep.
                sleep(0.25)
        except KeyboardInterrupt:
            break

    print("\n\nTranscription:")
    
    for line in transcription:
        print(line)
        


if __name__ == "__main__":
    print("Loading Model.... ")
    main()