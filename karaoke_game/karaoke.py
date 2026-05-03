import sounddevice as sd
import numpy as np
from mido import MidiFile
import math
import pyglet
from pyglet import shapes
import queue
from pyglet.gl import glClearColor

CHUNK_SIZE = 1024 # Number of audio frames per buffer
RATE = 44100 # Audio sampling rate (HZ)
CHANNELS = 1 # Mono audio

# notes from song that are currently on the display
active_notes = []

spawn_index = 0
song_time = 0.0
score = 0
latest_detected_midi = None

# one does not have to sing excactly the right note
pitch_tolerance = 1
hit_zone_px = 12

win = pyglet.window.Window(1000, 600)
# set background color
glClearColor(0.05, 0.08, 0.2, 1.0)
batch = pyglet.graphics.Batch()  
hit_x = 120

# store the sung frequencies 
audio_q = queue.Queue()
# rectangle for the player to see what note is currently sung
detected_rect = shapes.Rectangle(hit_x, 0, 20, 12, color=(255,145,167), batch=batch)

line = shapes.Line(hit_x, 0, hit_x, 600)
score_label = pyglet.text.Label(
    "Score: 0",
    x = 10, y = win.height - 30,
    font_name='Calibri',
    font_size = 18,
    color = (255, 255, 255, 255)
)

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

def read_midi(midi_file: str):
    melody = []
    t = 0.0
    for msg in MidiFile(midi_file).play():
        t += msg.time
        melody.append((msg.note, t))
    return melody

# set the melody
melody = read_midi("../read_midi/freude.mid")

# function to convert frequency to midi note
def freq_to_midi(freq):
    if not freq or freq <= 0:
        return None
    return int(round(69 + 12*math.log2(freq/440.0))) # formula for frequency to midi note

# function to convert midi note to height in the window
def midi_to_y(midi, height, min_note=48, max_note=84, margin=20):
    midi = max(min_note, min(max_note, midi))
    frac = (midi - min_note) / (max_note - min_note)
    return margin + frac * (height - 2*margin)

# function to get major frequency with fft
def get_major_freq(data, rate):
    N = len(data)
    win = np.hamming(N)

    x = data * win
    spectrum = np.abs(np.fft.rfft(x))
    frequencies = np.fft.rfftfreq(N, 1/rate)
    idx = np.argmax(spectrum)

    return frequencies[idx]

# function to spawn a note from the melody
def spawn_note(midi):
    rect = shapes.Rectangle(win.width, midi_to_y(midi, win.height), 20, 12, color=(173,216,230), batch=batch)
    rect.midi = midi
    rect.hit = False
    active_notes.append(rect)

def update(dt):
    global spawn_index, song_time, latest_detected_midi, score

    latest_freq = None
    try:
        # get the latest frequency from the queue
        latest_freq = audio_q.get_nowait()
    except queue.Empty:
        pass

    # if frequnecy is detected, set the respective height for the rectangle 
    if latest_freq is not None and latest_freq > 0:
        detected = freq_to_midi(latest_freq)
        if detected is not None:
                latest_detected_midi = detected
                detected_rect.y = midi_to_y(detected, win.height)
        else:
                latest_detected_midi = None
    else:
            latest_detected_midi = None

    song_time += dt

    # spawn the notes of the melody
    if spawn_index < len(melody) and song_time >= melody[spawn_index][1]:
        spawn_note(melody[spawn_index][0])
        spawn_index += 1

    for rect in active_notes[:]:
        # let the rectangles ("notes") move to the left
        rect.x -= 200 * dt

        # if note is not hit yet
        if not getattr(rect, "hit", False):
            # get left and right edge of rectangle
            rect_left = rect.x
            rect_right = rect.x + rect.width
            in_hit_zone = (rect_left <= hit_x + hit_zone_px) and (rect_right >= hit_x - hit_zone_px)

            # if rectangle is in the hit zone and a sung note is detected
            if in_hit_zone and latest_detected_midi is not None:
                # check if sung note and true note are almost the same 
                if abs(latest_detected_midi - rect.midi) <= pitch_tolerance:
                    score += 1
                    rect.hit = True
                    rect.color = (0, 255, 0)   
                    score_label.text = f"Score: {score}"
                    latest_detected_midi = None

        if rect.x < -20:
            rect.delete()
            active_notes.remove(rect)


# audio callback to safe data
def audio_callback(indata, frames, time, status):
    if status:
        print(status)

    data = indata[:, 0]  # mono
    major_freq = get_major_freq(data, RATE)
    try: 
        audio_q.put_nowait(major_freq)
    except queue.Full:
        pass
    
# open audio input stream
stream = sd.InputStream(
    device=input_device,
    channels=CHANNELS,
    samplerate=RATE,
    blocksize=CHUNK_SIZE,
    callback=audio_callback,
    latency='low'
)

        
@win.event
def on_draw():
    win.clear()
    batch.draw()
    line.draw()
    score_label.draw()


stream.start()
pyglet.clock.schedule_interval(update, 1/60.0)
pyglet.app.run()