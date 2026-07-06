import sys
import os
import subprocess
import time
import math
import threading
import urllib.request
import queue

# All paths relative to this file, so the folder is portable
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = os.path.join(BASE_DIR, "tuber_runtime.log")

class Logger:
    def __init__(self, filepath):
        self.terminal = sys.stdout
        self.log = open(filepath, "a", encoding="utf-8")

    def write(self, message):
        self.terminal.write(message)
        self.log.write(message)
        self.log.flush()

    def flush(self):
        self.terminal.flush()
        self.log.flush()

sys.stdout = Logger(LOG_FILE)
sys.stderr = sys.stdout

print(f"\n--- Application started at {time.strftime('%Y-%m-%d %H:%M:%S')} ---")

# Auto-install dependencies if missing
try:
    import cv2
    import mediapipe as mp
    import numpy as np
    from PIL import Image, ImageTk
except ImportError:
    print("Installing computer vision libraries (opencv, mediapipe, numpy, pillow)...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "opencv-python", "mediapipe", "numpy", "pillow"])
    import cv2
    import mediapipe as mp
    import numpy as np
    from PIL import Image, ImageTk

from mediapipe.tasks import python
from mediapipe.tasks.python import vision

import tkinter as tk

# Paths and Config
ASSETS_DIR = os.path.join(BASE_DIR, "assets")
MODEL_PATH = os.path.join(BASE_DIR, "face_landmarker.task")
MODEL_URL = "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task"

IMAGES = {
    "idle": os.path.join(ASSETS_DIR, "1_green_idle.png"),
    "talk": os.path.join(ASSETS_DIR, "2_green_talk.png"),
    "blink": os.path.join(ASSETS_DIR, "3_green_blink.png"),
    "talk_blink": os.path.join(ASSETS_DIR, "4_green_talk_blink.png")
}

CANVAS_W, CANVAS_H = 480, 480
SPRITE_SIZE = 400  # avatar rendered at this size, canvas is larger to leave room for movement

# Motion tuning
MOUTH_LO, MOUTH_HI = 0.05, 0.25   # jawOpen mapped to 0..1 across this range
BLINK_LO, BLINK_HI = 0.25, 0.50   # eyeBlink mapped to 0..1 across this range
SMOOTH_MOUTH = 0.45               # EMA factors (higher = snappier)
SMOOTH_BLINK = 0.60
SMOOTH_POS = 0.18
MOVE_X_RANGE = 50                 # px of horizontal sway
MOVE_Y_RANGE = 35                 # px of vertical sway
BREATH_AMPLITUDE = 3.5            # idle bob in px
BREATH_SPEED = 2.0                # rad/s

# Download model if not exists
if not os.path.exists(MODEL_PATH):
    print("Downloading face landmarker model...")
    urllib.request.urlretrieve(MODEL_URL, MODEL_PATH)
    print("Model downloaded successfully!")

# Raw tracking targets (written by processing loop, smoothed by renderer)
TRACK = {"mouth": 0.0, "blink": 0.0, "dx": 0.0, "dy": 0.0, "face": False}
RUNNING = True

def clamp01(v):
    return max(0.0, min(1.0, v))

# Vectorized Chroma Keying using NumPy
def load_sprite(img_path):
    if not os.path.exists(img_path):
        print(f"Error: {img_path} not found.")
        return np.zeros((SPRITE_SIZE, SPRITE_SIZE, 4), dtype=np.float32)

    img = Image.open(img_path).convert("RGBA")
    arr = np.array(img)

    r, g, b = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2]
    green_mask = (g > 140) & (r < 110) & (b < 110)
    arr[green_mask] = [0, 0, 0, 0]

    out_img = Image.fromarray(arr).resize((SPRITE_SIZE, SPRITE_SIZE), Image.Resampling.LANCZOS)
    return np.array(out_img, dtype=np.float32)

# Background camera reader thread
def camera_capture_thread(cap, frame_queue):
    global RUNNING
    print("Camera capture thread started...")
    while RUNNING:
        try:
            ret, frame = cap.read()
            if ret:
                if not frame_queue.empty():
                    try:
                        frame_queue.get_nowait()
                    except queue.Empty:
                        pass
                frame_queue.put(frame)
            else:
                time.sleep(0.01)
        except Exception as e:
            print(f"Error capturing camera frame: {e}")
            time.sleep(0.1)

    cap.release()
    print("Camera capture thread stopped and camera released.")

# Tkinter GUI App
class WebcamPNGTuberApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Webcam Face-Tracking PNGTuber")
        self.root.geometry(f"{CANVAS_W}x{CANVAS_H + 50}")
        self.root.configure(bg="#1a1a1a")

        print("Processing images and removing green screen...")
        t0 = time.time()
        self.spr_idle = load_sprite(IMAGES["idle"])
        self.spr_talk = load_sprite(IMAGES["talk"])
        self.spr_blink = load_sprite(IMAGES["blink"])
        self.spr_talk_blink = load_sprite(IMAGES["talk_blink"])
        print(f"Images processed in {time.time() - t0:.3f} seconds.")

        # Smoothed motion state
        self.mouth = 0.0
        self.blink = 0.0
        self.dx = 0.0
        self.dy = 0.0
        self.t0 = time.time()

        self.avatar_canvas = tk.Canvas(root, width=CANVAS_W, height=CANVAS_H, bg="#222222", highlightthickness=0)
        self.avatar_canvas.pack()

        self.tk_frame = None  # per-frame PhotoImage reference
        self.image_on_canvas = self.avatar_canvas.create_image(CANVAS_W // 2, CANVAS_H // 2)

        self.status_label = tk.Label(root, text="Status: Tracking...", fg="cyan", bg="#1a1a1a")
        self.status_label.pack(pady=10)

    def draw_avatar(self):
        # Smooth raw targets toward current state (EMA)
        self.mouth += (TRACK["mouth"] - self.mouth) * SMOOTH_MOUTH
        self.blink += (TRACK["blink"] - self.blink) * SMOOTH_BLINK
        self.dx += (TRACK["dx"] - self.dx) * SMOOTH_POS
        self.dy += (TRACK["dy"] - self.dy) * SMOOTH_POS

        m, b = clamp01(self.mouth), clamp01(self.blink)

        # Bilinear crossfade across the 4 sprites (continuous mouth x blink)
        blended = ((1 - m) * (1 - b) * self.spr_idle
                   + m * (1 - b) * self.spr_talk
                   + (1 - m) * b * self.spr_blink
                   + m * b * self.spr_talk_blink)
        frame_img = Image.fromarray(blended.astype(np.uint8))

        # Idle breathing bob
        breath = math.sin((time.time() - self.t0) * BREATH_SPEED) * BREATH_AMPLITUDE

        self.tk_frame = ImageTk.PhotoImage(frame_img)
        self.avatar_canvas.itemconfig(self.image_on_canvas, image=self.tk_frame)
        self.avatar_canvas.coords(self.image_on_canvas,
                                  CANVAS_W // 2 + self.dx,
                                  CANVAS_H // 2 + self.dy + breath)

        if TRACK["face"]:
            self.status_label.config(
                text=f"Mouth: {m:.2f} | Blink: {b:.2f}",
                fg="lightgreen" if m > 0.3 else "cyan")
        else:
            self.status_label.config(text="No face detected", fg="orange")

# Main thread loop: processes frames and updates GUI
def main_processing_loop(app, frame_queue, detector):
    global RUNNING

    if not RUNNING:
        return

    try:
        frame = None
        try:
            frame = frame_queue.get_nowait()
        except queue.Empty:
            pass

        if frame is not None:
            frame = cv2.flip(frame, 1)
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)
            result = detector.detect(mp_image)

            if result.face_blendshapes and result.face_landmarks:
                TRACK["face"] = True
                blendshapes = result.face_blendshapes[0]
                landmarks = result.face_landmarks[0]

                blink_l = blink_r = jaw_open = 0.0
                for cat in blendshapes:
                    if cat.category_name == "eyeBlinkLeft":
                        blink_l = cat.score
                    elif cat.category_name == "eyeBlinkRight":
                        blink_r = cat.score
                    elif cat.category_name == "jawOpen":
                        jaw_open = cat.score

                # Continuous 0..1 targets instead of on/off thresholds
                TRACK["mouth"] = clamp01((jaw_open - MOUTH_LO) / (MOUTH_HI - MOUTH_LO))
                TRACK["blink"] = clamp01((max(blink_l, blink_r) - BLINK_LO) / (BLINK_HI - BLINK_LO))

                # Head position from nose tip (landmark 1), normalized 0..1
                nose = landmarks[1]
                TRACK["dx"] = max(-1.0, min(1.0, (nose.x - 0.5) * 3.0)) * MOVE_X_RANGE
                TRACK["dy"] = max(-1.0, min(1.0, (nose.y - 0.45) * 3.0)) * MOVE_Y_RANGE
            else:
                TRACK["face"] = False
                TRACK["mouth"] = 0.0
                TRACK["blink"] = 0.0
    except Exception as e:
        print(f"Error in tracking loop iteration: {e}")

    app.draw_avatar()

    # Schedule next run on the main thread (approx 30 FPS / 33ms)
    app.root.after(33, lambda: main_processing_loop(app, frame_queue, detector))

if __name__ == "__main__":
    print("Opening webcam on main thread...")
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("Error: Could not open webcam on main thread.")
        sys.exit(1)

    try:
        print("Initializing Face Landmarker on main thread...")
        base_options = python.BaseOptions(model_asset_path=MODEL_PATH)
        options = vision.FaceLandmarkerOptions(
            base_options=base_options,
            output_face_blendshapes=True,
            num_faces=1
        )
        detector = vision.FaceLandmarker.create_from_options(options)
    except Exception as e:
        print(f"Failed to initialize Face Landmarker: {e}")
        cap.release()
        sys.exit(1)

    frame_queue = queue.Queue(maxsize=1)

    capture_thread = threading.Thread(target=camera_capture_thread, args=(cap, frame_queue), daemon=True)
    capture_thread.start()

    print("Launching Tkinter Window...")
    root = tk.Tk()
    app = WebcamPNGTuberApp(root)

    print("Starting main thread processing loop...")
    root.after(100, lambda: main_processing_loop(app, frame_queue, detector))

    def on_closing():
        global RUNNING
        RUNNING = False
        print("Closing application...")
        detector.close()
        root.destroy()
        sys.exit(0)

    root.protocol("WM_DELETE_WINDOW", on_closing)
    root.mainloop()
