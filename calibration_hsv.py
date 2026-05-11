from picamera2 import Picamera2
import cv2
import time

# =========================
# CAMERA
# =========================

picam2 = Picamera2()

config = picam2.create_preview_configuration(
    main={"format": "RGB888", "size": (640, 480)}
)

picam2.configure(config)

picam2.start()

time.sleep(2)

# =========================
# REGLAGES STABLES
# =========================

picam2.set_controls({

    "AeEnable": False,
    "ExposureTime": 16000,
    "AnalogueGain": 1.0,

    "AwbEnable": False,
    "ColourGains": (1.4, 1.45)
})

time.sleep(1)

# =========================
# CALLBACK SOURIS
# =========================

def mouse_callback(event, x, y, flags, param):

    if event == cv2.EVENT_LBUTTONDOWN:

        hsv = param

        pixel = hsv[y, x]

        print(f"\nPosition : ({x}, {y})")
        print(f"HSV : {pixel}")

# =========================
# BOUCLE
# =========================

while True:

    frame = picam2.capture_array()

    # IMPORTANT :
    # ne PAS convertir RGB -> BGR ici

    hsv = cv2.cvtColor(frame, cv2.COLOR_RGB2HSV)

    display = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)

    cv2.imshow("Calibration HSV", display)

    cv2.setMouseCallback(
        "Calibration HSV",
        mouse_callback,
        hsv
    )

    key = cv2.waitKey(1)

    if key == 27:
        break

cv2.destroyAllWindows()
