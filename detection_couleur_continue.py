from picamera2 import Picamera2
import cv2
import time
import numpy as np

COLOR_RANGES = {
    "rouge": [
        ((0, 140, 100), (10, 255, 255)),
        ((170, 140, 100), (180, 255, 255))
    ],
    "jaune": [
        ((15, 120, 80), (35, 255, 255))
    ],
    "vert": [
        ((35, 100, 60), (65, 255, 255))
    ],
    "bleu": [
        ((105, 80, 30), (135, 255, 180))
    ],
}

picam2 = Picamera2()

config = picam2.create_preview_configuration(
    main={"format": "RGB888", "size": (640, 480)}
)

picam2.configure(config)
picam2.start()
time.sleep(2)

picam2.set_controls({
    "AeEnable": False,
    "ExposureTime": 16000,
    "AnalogueGain": 1.0,
    "AwbEnable": False,
    "ColourGains": (1.4, 1.45)
})

time.sleep(1)

print("Détection continue lancée. CTRL+C pour arrêter.")

try:
    while True:
        frame = picam2.capture_array()
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

        roi_mask = np.zeros(hsv.shape[:2], dtype=np.uint8)
        roi_mask[100:440, 140:580] = 255

        resultats = {}

        for couleur, ranges in COLOR_RANGES.items():
            mask_total = None

            for lower, upper in ranges:
                lower = np.array(lower, dtype=np.uint8)
                upper = np.array(upper, dtype=np.uint8)

                mask = cv2.inRange(hsv, lower, upper)
                mask = cv2.bitwise_and(mask, roi_mask)

                if mask_total is None:
                    mask_total = mask
                else:
                    mask_total = cv2.bitwise_or(mask_total, mask)

            kernel = np.ones((5, 5), np.uint8)
            mask_total = cv2.morphologyEx(mask_total, cv2.MORPH_OPEN, kernel)
            mask_total = cv2.morphologyEx(mask_total, cv2.MORPH_CLOSE, kernel)

            pixels_detectes = cv2.countNonZero(mask_total)
            resultats[couleur] = pixels_detectes

        couleur_detectee = max(resultats, key=resultats.get)
        score = resultats[couleur_detectee]

        if score > 15000:
            couleur_actuelle = couleur_detectee
        else:
            couleur_actuelle = "inconnue"

        print(f"Couleur détectée : {couleur_actuelle} | score={score}")

        time.sleep(0.5)

except KeyboardInterrupt:
    print("\nArrêt détection.")

finally:
    picam2.stop()