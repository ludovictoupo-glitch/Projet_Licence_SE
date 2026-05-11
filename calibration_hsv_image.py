from picamera2 import Picamera2
import cv2
import time
import numpy as np

# ==========================================
# CHOISIR LA COULEUR TESTÉE
# ==========================================

NOM_COULEUR = "vert"   # rouge, jaune, vert, bleu

# ==========================================
# CAMERA
# ==========================================

picam2 = Picamera2()

config = picam2.create_preview_configuration(
    main={"format": "RGB888", "size": (640, 480)}
)

picam2.configure(config)

picam2.start()

time.sleep(2)

# ==========================================
# REGLAGES CAMERA STABLES
# ==========================================

picam2.set_controls({

    "AeEnable": False,

    "ExposureTime": 16000,

    "AnalogueGain": 1.0,

    "AwbEnable": False,

    "ColourGains": (1.4, 1.45)
})

time.sleep(1)

# ==========================================
# CAPTURE IMAGE
# ==========================================

frame = picam2.capture_array()

# ==========================================
# CONVERSION HSV
# IMPORTANT :
# frame traité comme BGR ici
# ==========================================

hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

# ==========================================
# ZONE CENTRALE DE MESURE
# ==========================================

x1, y1 = 270, 190
x2, y2 = 370, 290

zone = hsv[y1:y2, x1:x2]

moyenne = np.mean(
    zone.reshape(-1, 3),
    axis=0
).astype(int)

# ==========================================
# IMAGE D'AFFICHAGE
# ==========================================

image_affichage = frame.copy()

# rectangle vert
cv2.rectangle(
    image_affichage,
    (x1, y1),
    (x2, y2),
    (0, 255, 0),
    2
)

# texte HSV
texte = f"HSV : {moyenne}"

cv2.putText(
    image_affichage,
    texte,
    (20, 40),
    cv2.FONT_HERSHEY_SIMPLEX,
    0.8,
    (0, 255, 0),
    2
)

# ==========================================
# SAUVEGARDE
# ==========================================

nom_image = f"hsv_{NOM_COULEUR}.jpg"

cv2.imwrite(nom_image, image_affichage)

# ==========================================
# RESULTATS
# ==========================================

print("\n==========================")
print(f"Couleur testée : {NOM_COULEUR}")
print(f"HSV moyen = {moyenne}")
print(f"Image sauvegardée : {nom_image}")
print("==========================")