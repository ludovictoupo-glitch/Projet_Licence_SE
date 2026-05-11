from picamera2 import Picamera2
import cv2
import time
import numpy as np

NOM_COULEUR = "jaune"  # change ici : rouge, vert, bleu, jaune

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

hsv = cv2.cvtColor(frame, cv2.COLOR_RGB2HSV)

# zone centrale de mesure
x1, y1 = 270, 190
x2, y2 = 370, 290

zone = hsv[y1:y2, x1:x2]
moyenne = np.mean(zone.reshape(-1, 3), axis=0).astype(int)

# dessin du rectangle sur l'image
image_affichage = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
cv2.rectangle(image_affichage, (x1, y1), (x2, y2), (0, 255, 0), 2)

nom_image = f"hsv_{NOM_COULEUR}.jpg"
cv2.imwrite(nom_image, image_affichage)

print(f"Couleur testée : {NOM_COULEUR}")
print(f"HSV moyen centre = {moyenne}")
print(f"Image sauvegardée : {nom_image}")