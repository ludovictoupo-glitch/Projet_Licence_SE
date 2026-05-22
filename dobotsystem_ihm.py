import time
import math
import logging
import threading
from queue import Queue, Full
import serial
import serial.tools.list_ports
from gpiozero import LED
from pydobot import Dobot
from pydobot.message import Message
import sqlite3

DB_FILE = "project_Dobot.db"

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

Z_SAFE = 50
MAX_REACH = 300
POSE_TOLERANCE_XYZ = 1
POSE_TOLERANCE_R = 1
R_TRANSPORT = 0

Z_APPROCHE_PRISE = 25
Z_RETRAIT_PRISE = 35
Z_APPROCHE_DEPOT = 25
Z_RETRAIT_DEPOT = 35
MARGE_DEPOT_Z = 2

HAUTEUR_CUBE = 25
MAX_CUBES_PAR_PILE = 4
DECALAGE_PILE_X = 25
DECALAGE_PILE_Y = 0

CORRECTION_DEPOT = {
    "rouge": [(0, 0), (0, 0)],
    "vert": [(0, 0), (0, 0)],
    "bleu": [(0, 0), (0, 0)],
    "jaune": [(0, 0), (0, 0)],}

Positions = {
    "prise": (217.5083, 10.3581, 0.2026, 2.7265),
    "R": (38.7859, -171.2865, -51.2482, -77.2412),
    "V": (140.8581, -179.5291, -48.6537, -51.8824),
    "B": (89.4962, -141.4565, -50.7161, -57.6794),
    "J": (85.6157, -224.3781, -49.4713, -69.1147),
    "home": (200, 0, 50, 0),}

COULEUR_TO_POSITION = {
    "rouge": "R",
    "vert": "V",
    "bleu": "B",
    "jaune": "J",}

led1 = LED(16)
led2 = LED(26)

couleur_queue = Queue(maxsize=5) 
stop_event = threading.Event()

# Gestion de l'éclairage pour la détection couleur avec allumage avant capture et extinction après, pour économiser les LEDs et éviter les interférences lumineuses en dehors de la capture.
def allumer_eclairage():
    led1.on()
    led2.on()
    log.info("Éclairage ON")

def eteindre_eclairage():
    led1.off()
    led2.off()
    log.info("Éclairage OFF")

def fermer_eclairage():
    try:
        eteindre_eclairage()
    finally:
        led1.close()
        led2.close()
        log.info("Éclairage fermé")

# Détection automatique des ports série pour le Dobot et le XBee, avec identification basée sur les VID et PID
def detect_ports():
    dobot_port = None
    xbee_port = None
    for port in serial.tools.list_ports.comports():
        log.info(f"Port détecté: {port.device}, VID={port.vid}, PID={port.pid}, desc={port.description}")
        if port.vid == 0x1A86:
            dobot_port = port.device
        elif port.vid in {0x10C4, 0x0403}:
            xbee_port = port.device
    return dobot_port, xbee_port

def move_to(device, target):
    x, y, z, r = target
    device.move_to(x, y, z, r, wait=True)

def wait_until_reached(device, target, timeout=10):
    start = time.time()
    while time.time() - start < timeout:
        cx, cy, cz, cr = device.pose()[:4]
        x, y, z, r = target
        if math.sqrt((cx - x) ** 2 + (cy - y) ** 2 + (cz - z) ** 2) <= POSE_TOLERANCE_XYZ and abs(cr - r) <= POSE_TOLERANCE_R:
            return True
        time.sleep(0.3)
    return False
#
def set_suction(device, enable):
    try:
        device._set_end_effector_suction_cup(enable)
        log.info(f"Ventouse {'ON' if enable else 'OFF'}")
    except Exception as exc:
        log.error(f"Erreur commande ventouse: {exc}")

def sequence_prise_depot(device, point, z_approche, z_contact, z_retrait, action):
    x, y, _, r = point
    safe_move(device, x, y, z_approche, r)
    move_to(device, (x, y, z_contact, r))
    time.sleep(0.2)
    action(device)
    time.sleep(0.6)
    move_to(device, (x, y, z_retrait, r))

def prendre_cube(device):
    x, y, z, _ = Positions["prise"]
    r = R_TRANSPORT
    z_approche = max(Z_SAFE, z + Z_APPROCHE_PRISE)
    z_retrait = max(Z_SAFE, z + Z_RETRAIT_PRISE)
    sequence_prise_depot( device, (x, y, z, r), z_approche, z, z_retrait, lambda d: set_suction(d, True))

# connexion au compteur SQlite pour obtenir le nombre de cubes déjà empilés d'une couleur donnée
def get_total_sqlite(couleur): # Compteur SQlite
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT count FROM stats WHERE color = ?", (couleur,))
    row = cursor.fetchone()
    conn.close()
    if row is None:
        return 0
    return row[0]

# calcul de la position de dépôt en fonction de la couleur et du nombre de cubes déjà empilés, avec gestion de l'empilement sur 2 piles
def calculer_position_depot(couleur):
    if couleur not in COULEUR_TO_POSITION:
        raise RuntimeError(f"Couleur inconnue pour empilement: {couleur}")
    total = get_total_sqlite(couleur)
    pile_index = total % 2
    niveau = total // 2
    if niveau >= MAX_CUBES_PAR_PILE:
        raise RuntimeError(f"Les deux piles {couleur} sont pleines")
    x_base, y_base, z_base, _ = Positions[COULEUR_TO_POSITION[couleur]]
    correction_x, correction_y = CORRECTION_DEPOT[couleur][pile_index]
    x = x_base + pile_index * DECALAGE_PILE_X + correction_x
    y = y_base + pile_index * DECALAGE_PILE_Y + correction_y
    z = z_base + niveau * HAUTEUR_CUBE + MARGE_DEPOT_Z
    return pile_index, niveau, x, y, z, R_TRANSPORT

# dépôt du cube avec approche sécurisée et gestion de l'empilement
def deposer_cube_empile(device, couleur):
    pile_index, niveau, x, y, z, r = calculer_position_depot(couleur)
    z_approche = max(Z_SAFE, z + Z_APPROCHE_DEPOT)
    z_retrait = max(Z_SAFE, z + Z_RETRAIT_DEPOT)
    sequence_prise_depot(device,(x, y, z, r),z_approche,z,z_retrait,lambda d: set_suction(d, False))
    log.info(f"Compteurs piles {couleur}: {get_total_sqlite(couleur)}")

#détection de la couleur avec éclairage + capture caméra, avec gestion des erreurs et retour d'une couleur "inconnue" en cas de problème
def detecter_couleur_avec_eclairage(detecter_couleur_callback):
    try:
        allumer_eclairage()
        time.sleep(0.5)
        couleur = detecter_couleur_callback()
        log.info(f"Couleur capturée: {couleur}")
        return couleur
    except Exception as exc:
        log.error(f"Erreur capture caméra: {exc}")
        return "inconnue"
    finally:
        eteindre_eclairage()

def ajouter_couleur_file(couleur):
    if couleur == "inconnue" or couleur not in COULEUR_TO_POSITION:
        log.warning(f"Couleur invalide ou inconnue  objet ignoré: {couleur}")
        return
    try:
        couleur_queue.put_nowait(couleur)
        log.info(f"Couleur ajoutée à la file: {couleur}")
    except Full:
        log.warning("File d'attente pleine  objet ignoré")


def listen_xbee(port, detecter_couleur_callback):
    while not stop_event.is_set():
        try:
            with serial.Serial(port, 9600, timeout=1) as ser:
                log.info(f"XBee connecté: {port}")
                while not stop_event.is_set():
                    if ser.in_waiting:
                        msg = ser.readline().decode(errors="ignore").strip()
                        log.info(f"Reçu XBee: '{msg}'")
                        if msg == "OBJET":
                            log.info("OBJET reçu = allumage LED + capture caméra")
                            couleur = detecter_couleur_avec_eclairage(detecter_couleur_callback)
                            ajouter_couleur_file(couleur)
                    time.sleep(0.05)
        except Exception as exc:
            log.warning(f"Erreur XBee: {exc}")
            time.sleep(2)

def do_homing(device):
    log.info("HOMING LOGICIEL")
    clear_alarms(device)
    x, y, z, r = device.pose()[:4]
    move_to(device, (x, y, z + 10, r))
    time.sleep(1)
    _, _, z2, _ = device.pose()[:4]
    if abs(z2 - z) < 5:
        raise RuntimeError("Le Dobot ne bouge toujours pas après clear alarm")
    safe_move(device, *Positions["home"])

# mouvement sécurisé avec approche en Z safe + contournement zone risquée
def safe_move(device, x, y, z, r=0):
    try:
        device.pose()
    except Exception as exc:
        log.error(f"Dobot ne répond pas: {exc}")
        raise RuntimeError("Robot non prêt")
    if math.hypot(x, y) > MAX_REACH:
        raise RuntimeError(f"Position hors enveloppe: x={x:.1f}, y={y:.1f}")
    cx, cy, cz, cr = device.pose()[:4]
    if cz < Z_SAFE:
        move_to(device, (cx, cy, Z_SAFE, cr))
        time.sleep(0.3)
    risky_zone = abs(y) > 120 or z < 40
    if risky_zone:
        move_to(device, (cx, 0, Z_SAFE, 0))
        time.sleep(0.3)
    target = (x, y, Z_SAFE, r)
    move_to(device, target)
    time.sleep(0.3)
    target = (x, y, z, r)
    move_to(device, target)
    if not wait_until_reached(device, target):
        raise RuntimeError("Position finale non atteinte")

def init_robot_system(detecter_couleur_callback):
    log.info("INIT ROBOT SYSTEM")
    dobot_port, xbee_port = detect_ports()
    if not dobot_port:
        raise RuntimeError("Dobot introuvable")
    if not xbee_port:
        raise RuntimeError("XBee introuvable")
    device = Dobot(port=dobot_port)
    time.sleep(1)
    clear_alarms(device)
    try:
        device._set_queued_cmd_clear()
        time.sleep(0.2)
        device._set_queued_cmd_start_exec()
        time.sleep(0.2)
        device._set_ptp_joint_params(50, 50, 50, 50, 50, 50, 50, 50)
    except Exception as exc:
        log.warning(f"Impossible de régler les paramètres PTP: {exc}")
    set_suction(device, False)
    device.speed(90, 90)
    do_homing(device)
    threading.Thread(target=listen_xbee, args=(xbee_port, detecter_couleur_callback), daemon=True).start()
    log.info("ROBOT SYSTEM READY")
    return device

# Effacement des alarmes Dobot (en cas de blocage) avec envoi de commande directe
def clear_alarms(device):
    try:
        log.warning("Effacement des alarmes Dobot")
        device._set_queued_cmd_stop_exec()
        time.sleep(0.2)
        device._set_queued_cmd_clear()
        time.sleep(0.2)
        msg = Message()
        msg.id = 20
        msg.ctrl = 0x01
        msg.params = bytearray([])
        device._send_command(msg)
        time.sleep(1)
        device._set_queued_cmd_start_exec()
        time.sleep(0.5)
        return True
    except Exception as exc:
        log.error(f"Impossible d'effacer les alarmes: {exc}")
        return False

def cycle(device, couleur):
    log.info("CYCLE DOBOT")
    log.info(f"Couleur reçue depuis la file: {couleur}")
    cube_depose = False
    try:
        if couleur not in COULEUR_TO_POSITION:
            raise RuntimeError(f"Couleur inconnue: {couleur}")
        prendre_cube(device)
        deposer_cube_empile(device, couleur)
        cube_depose = True
        return True
    except Exception as exc:
        log.error(f"Erreur cycle: {exc}")
        clear_alarms(device)
        return False
    finally:
        if not cube_depose:
            set_suction(device, False)
        try:
            safe_move(device, *Positions["home"])
        except Exception as exc:
            log.warning(f"Retour home impossible: {exc}")
        log.info("FIN CYCLE")

# Fermeture du système robot avec arrêt du thread XBee
def close_robot_system(device):
    stop_event.set()
    try:
        safe_move(device, *Positions["home"])
        set_suction(device, False)
    except Exception as exc:
        log.warning(f"Erreur retour final home: {exc}")
    try:
        fermer_eclairage()
    except Exception as exc:
        log.warning(f"Erreur fermeture éclairage: {exc}")
    try:
        device.close()
    except Exception as exc:
        log.warning(f"Erreur fermeture Dobot: {exc}")
    log.info("Système robot fermé proprement")