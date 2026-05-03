import sounddevice as sd
import numpy as np
import pyqtgraph as pg
import queue
from pynput.keyboard import Key, Controller
import time 
from collections import deque

# Set up audio stream
# reduce chunk size and sampling rate for lower latency
CHUNK_SIZE = 1024 # Number of audio frames per buffer
RATE = 44100 # Audio sampling rate (HZ)
CHANNELS = 1 # Mono audio

# store the detected frequencies 
audio_q = queue.Queue()
keyboard = Controller()

# store the last few frequencies 
freq_history = deque(maxlen=6)
last_store_time = 0.0
latest_freq = None

# cooldown to avoid double detected single chirps
last_trigger_time = 0.0
trigger_cooldown = 1.0

# print info about audio devices
print("Available input devices:\n")
devices = sd.query_devices()

input_devices = []
for i, dev in enumerate(devices):
    if dev['max_input_channels'] > 0:
        print(f"{i}: {dev['name']}")
        input_devices.append(i)

# let user select audio device
input_device = int(input("\nSelect input device: "))

# function to get the major frequency with fft
def get_major_freq(data, rate):
    N = len(data)
    win = np.hamming(N)

    x = data * win
    spectrum = np.abs(np.fft.rfft(x))
    frequencies = np.fft.rfftfreq(N, 1/rate)
    idx = np.argmax(spectrum)

    return frequencies[idx]

# function to check if a few values are monotonic increasing
def is_monotonic_increasing(values):
    return all(values[i] < values[i + 1] for i in range(len(values) - 1))

# function to check if a few values are monotonic decreasing
def is_monotonic_decreasing(values):
    return all(values[i] > values[i + 1] for i in range(len(values) - 1))
    
def update():
    global last_store_time, latest_freq, last_trigger_time

    try:
        # get the latest frequency from the queue
        latest_freq = audio_q.get_nowait()
    except queue.Empty:
        latest_freq = None
        return

    if latest_freq is None: 
        return
    
    now = time.monotonic()

    # store frequnecies every 0.1 seconds
    if now - last_store_time >= 0.1:
        freq_history.append((now, latest_freq))
        last_store_time = now

    # cooldown
    if now - last_trigger_time < trigger_cooldown:
        return

    # after storing 4 values, check if these are chirps
    if len(freq_history) >= 4:
        values = [freq for _, freq in freq_history]

        if is_monotonic_increasing(values): 
            keyboard.press(Key.up)
            print("Upward chirp, up-key is pressed")
            keyboard.release(Key.up)
            # delete the history
            freq_history.clear()
            last_trigger_time = now
            return
        
        if is_monotonic_decreasing(values):
            keyboard.press(Key.down)
            print("Downward chirp, down-key is pressed")
            keyboard.release(Key.down)
            # delete the history
            freq_history.clear()
            last_trigger_time = now
            return

# audio callback to safe data
def audio_callback(indata, frames, time, status):

    data = indata[:, 0]  # mono
    major_freq = get_major_freq(data, RATE)
    try: 
        audio_q.put_nowait(major_freq)
    except queue.Full:
        pass
    update()


# open audio input stream
stream = sd.InputStream(
    device=input_device,
    channels=CHANNELS,
    samplerate=RATE,
    blocksize=CHUNK_SIZE,
    callback=audio_callback,
    latency='low'
)

# continously capture and plot audio signal
with stream:
    pg.exec()
