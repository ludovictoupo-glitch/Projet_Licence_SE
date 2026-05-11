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

frame = picam2.capture_array()

# Conversion HSV correcte pour ton cas
hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

image_resultat = frame.copy()

# Zone utile : ignore les bords de l'image
roi_mask = np.zeros(hsv.shape[:2], dtype=np.uint8)
roi_mask[100:440, 140:580] = 255

for couleur, ranges in COLOR_RANGES.items():

    mask_total = None

    for lower, upper in ranges:
        lower = np.array(lower, dtype=np.uint8)
        upper = np.array(upper, dtype=np.uint8)

        mask = cv2.inRange(hsv, lower, upper)

        # Appliquer la zone utile
        mask = cv2.bitwise_and(mask, roi_mask)

        if mask_total is None:
            mask_total = mask
        else:
            mask_total = cv2.bitwise_or(mask_total, mask)

    kernel = np.ones((5, 5), np.uint8)
    mask_total = cv2.morphologyEx(mask_total, cv2.MORPH_OPEN, kernel)
    mask_total = cv2.morphologyEx(mask_total, cv2.MORPH_CLOSE, kernel)

    contours, _ = cv2.findContours(
        mask_total,
        cv2.RETR_EXTERNAL,
        cv2.CHAIN_APPROX_SIMPLE
    )

    for contour in contours:
        area = cv2.contourArea(contour)

        if area > 800:
            x, y, w, h = cv2.boundingRect(contour)

            cv2.rectangle(
                image_resultat,
                (x, y),
                (x + w, y + h),
                (0, 255, 0),
                2
            )

            cv2.putText(
                image_resultat,
                couleur,
                (x, max(y - 10, 20)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                (0, 255, 0),
                2
            )

            print(
                f"{couleur} détecté | "
                f"position=({x},{y}) | "
                f"taille=({w}x{h}) | "
                f"aire={area}"
            )

    cv2.imwrite(f"masque_{couleur}.jpg", mask_total)

cv2.rectangle(image_resultat, (80, 40), (580, 440), (255, 255, 255), 2)

cv2.imwrite("detection_resultat.jpg", image_resultat)

print("Image résultat sauvegardée : detection_resultat.jpg")
print("Masques sauvegardés : masque_rouge.jpg, masque_jaune.jpg, masque_vert.jpg, masque_bleu.jpg")