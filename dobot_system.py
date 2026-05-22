import time
import threading
import logging
from queue import Queue, Empty, Full
import math
import serial
import serial.tools.list_ports
from pydobot import Dobot
from pydobot.message import Message
from gpiozero import LED
import logging

log = logging.getLogger(__name__)

led1 = LED(16)
led2 = LED(26)

def allumer_eclairage():
    led1.on()
    led2.on()
    log.info("Éclairage ON")

def eteindre_eclairage():
    led1.off()
    led2.off()
    log.info("Éclairage OFF")

def fermer_eclairage():
    eteindre_eclairage()
    led1.close()
    led.close()

logging.basicConfig(level=logging.INFO)
log = logging.getLogger()

couleur_queue = Queue(maxsize=5)
stop_event = threading.Event()

Positions = {
    "prise": (219.3181, 3.8507, 0.5939, 1.0059),
    "R": (52.522, -150.0039, -50.4858, -70.7029),
    "V": (137.7465, -171.9357, -50.4809, -51.3),
    "B": (92.1892, -225.5057, -49.5892, -67.7647),
    "J": (92.1892, -225.5057, -49.5892, -67.7647),
    "home": (200, 0, 50, 0),}

Z_SAFE = 50
MAX_REACH = 300


def detect_ports():
    dobot = None
    xbee = None
    for p in serial.tools.list_ports.comports():
        log.info(f"Port détecté: {p.device}, VID={p.vid}, PID={p.pid}, desc={p.description}")
        if p.vid == 0x1A86:
            dobot = p.device
        elif p.vid in [0x10C4, 0x0403]:
            xbee = p.device
    return dobot, xbee


def robot_ready(device):
    try:
        device.pose()
        return True
    except Exception as e:
        log.error(f"Dobot ne répond pas: {e}")
        return False


def in_reach(x, y):
    return math.sqrt(x**2 + y**2) <= MAX_REACH

def check_position_reached(device, x, y, z, r, tolerance_xyz=15, tolerance_r=15):
    cx, cy, cz, cr, j1, j2, j3, j4 = device.pose()
    erreur_xyz = math.sqrt((cx - x)**2 + (cy - y)**2 + (cz - z)**2)
    erreur_r = abs(cr - r)
    log.info(f"Position demandée : x={x:.1f}, y={y:.1f}, z={z:.1f}, r={r:.1f}")
    log.info(f"Position atteinte  : x={cx:.1f}, y={cy:.1f}, z={cz:.1f}, r={cr:.1f}")
    log.info(f"Erreur XYZ={erreur_xyz:.1f} mm | Erreur R={erreur_r:.1f}°")
    if erreur_xyz > tolerance_xyz:
        return False
    if erreur_r > tolerance_r:
        return False
    return True

def wait_until_reached(device, x, y, z, r, timeout=10, tolerance_xyz=15, tolerance_r=15):
    start = time.time()
    while time.time() - start < timeout:
        if check_position_reached(device, x, y, z, r, tolerance_xyz, tolerance_r):
            return True
        time.sleep(0.3)
    return False

def safe_move(device, x, y, z, r=0):
    if not robot_ready(device):
        raise RuntimeError("Robot non prêt")
    if not in_reach(x, y):
        raise RuntimeError(f"Position hors enveloppe: x={x:.1f}, y={y:.1f}")
    pose = device.pose()
    cx, cy, cz, cr = pose[0], pose[1], pose[2], pose[3]
    risky = abs(y) > 120 or z < 40
    if risky:
        log.info("Zone risquée → passage intermédiaire")
        if cz < Z_SAFE:
            device.move_to(cx, cy, Z_SAFE, cr, wait=True)
            time.sleep(0.5)
        device.move_to(cx, 0, Z_SAFE, 0, wait=True)
        time.sleep(0.5)
        pose = device.pose()
        cx, cy, cz, cr = pose[0], pose[1], pose[2], pose[3]
    if cz < Z_SAFE:
        device.move_to(cx, cy, Z_SAFE, cr, wait=True)
        time.sleep(0.5)
    device.move_to(x, y, Z_SAFE, r, wait=True)
    time.sleep(0.5)
    device.move_to(x, y, z, r, wait=True)
    if not wait_until_reached(device, x, y, z, r):
        raise RuntimeError("Position finale non atteinte")

def clear_alarms(device):
    try:
        log.warning("Effacement des alarmes Dobot")
        # 1. Stopper / vider les anciennes commandes
        device._set_queued_cmd_stop_exec()
        time.sleep(0.2)
        device._set_queued_cmd_clear()
        time.sleep(0.2)
        # 2. Envoyer ClearAlarmsState
        msg = Message()
        msg.id = 20
        msg.ctrl = 0x01
        msg.params = bytearray([])
        device._send_command(msg)
        time.sleep(1)
        # 3. Redémarrer l'exécution des commandes
        device._set_queued_cmd_start_exec()
        time.sleep(0.5)
        log.info("Commande clear alarm envoyée")
        return True
    except Exception as e:
        log.error(f"Impossible d'effacer les alarmes: {e}")
        return False

def set_suction(device, enable: bool):
    try:
        device._set_end_effector_suction_cup(enable)
        log.info(f"Ventouse {'ON' if enable else 'OFF'}")
    except Exception as e:
        log.error(f"Erreur commande ventouse: {e}")

def listen_xbee(port, detecter_couleur_callback):
    ser = None
    try:
        while not stop_event.is_set():
            try:
                ser = serial.Serial(port, 9600, timeout=1)
                log.info(f"XBee connecté: {port}")
                while not stop_event.is_set():
                    if ser.in_waiting:
                        raw = ser.readline()
                        msg = raw.decode(errors="ignore").strip()
                        log.info(f"Reçu XBee: '{msg}'")
                        if msg == "OBJET":
                            log.info("OBJET reçu allumage LED + capture caméra")
                            couleur = "inconnue"
                            try:
                                allumer_eclairage()
                                time.sleep(0.5)  # stabilisation lumière/caméra
                                couleur = detecter_couleur_callback()
                                log.info(f"Couleur capturée: {couleur}")
                            except Exception as e:
                                log.error(f"Erreur capture caméra avec éclairage: {e}")
                            finally:
                                eteindre_eclairage()
                            if couleur != "inconnue":
                                try:
                                    couleur_queue.put_nowait(couleur)
                                    log.info(f"Couleur ajoutée à la file: {couleur}")
                                except Full:
                                    log.warning("File d'attente pleine → objet ignoré")
                            else:
                                log.warning("Couleur inconnue → objet ignoré")
                    time.sleep(0.05)
            except Exception as e:
                log.warning(f"XBee erreur: {e}")
                time.sleep(2)
            finally:
                if ser and ser.is_open:
                    ser.close()
    except Exception as e:
        log.error(f"Thread XBee arrêté: {e}")

def do_homing(device):
    log.info("HOMING LOGICIEL")
    clear_alarms(device)
    x, y, z, r = device.pose()[:4]
    log.info(f"Position avant test: x={x:.1f}, y={y:.1f}, z={z:.1f}, r={r:.1f}")
    device.move_to(x, y, z + 10, r, wait=True)
    time.sleep(1)
    x2, y2, z2, r2 = device.pose()[:4]
    log.info(f"Position après test: x={x2:.1f}, y={y2:.1f}, z={z2:.1f}, r={r2:.1f}")
    if abs(z2 - z) < 5:
        raise RuntimeError("Le Dobot ne bouge toujours pas après clear alarm")
    log.info("Homing logiciel terminé")


def couleur_to_position(couleur):
    mapping = {
        "rouge": "R",
        "vert": "V",
        "bleu": "B",
        "jaune": "J",}
    return mapping.get(couleur)


def cycle(device, couleur):
    log.info("CYCLE DOBOT")
    log.info(f"Couleur reçue depuis la file: {couleur}")
    try:
        if not robot_ready(device):
            raise RuntimeError("Robot non prêt")
        destination = couleur_to_position(couleur)
        if destination is None:
            raise RuntimeError(f"Couleur inconnue: {couleur}")
        if destination not in Positions:
            raise RuntimeError(f"Position absente: {destination}")
        safe_move(device, *Positions["prise"])
        set_suction(device, True)
        time.sleep(0.3)
        safe_move(device, *Positions[destination])
    except Exception as e:
        log.error(f"Erreur cycle: {e}")
    finally:
        try:
            set_suction(device, False)
        except Exception:
            pass
        try:
            safe_move(device, *Positions["home"])
        except Exception as e:
            log.warning(f"Retour home impossible: {e}")
        log.info("FIN CYCLE")

def init_robot_system(detecter_couleur_callback):
    log.info("INIT ROBOT SYSTEM")
    dobot_port, xbee_port = detect_ports()
    if not dobot_port:
        raise RuntimeError("Dobot introuvable")
    if not xbee_port:
        raise RuntimeError("XBee introuvable")
    log.info(f"Dobot: {dobot_port}")
    log.info(f"XBee: {xbee_port}")
    device = Dobot(port=dobot_port)
    time.sleep(1)
    clear_alarms(device)
    try:
        device._set_queued_cmd_clear()
        time.sleep(0.2)
        device._set_queued_cmd_start_exec()
        time.sleep(0.2)
        device._set_ptp_joint_params(50, 50, 50, 50, 50, 50, 50, 50)
    except Exception as e:
        log.warning(f"Impossible de régler les paramètres PTP: {e}")
    set_suction(device, False)
    device.speed(90, 90)
    do_homing(device)
    threading.Thread(target=listen_xbee,args=(xbee_port, detecter_couleur_callback),daemon=True ).start()
    log.info("ROBOT SYSTEM READY")
    return device


def close_robot_system(device):
    stop_event.set()
    try:
        safe_move(device, *Positions["home"])
        set_suction(device, False)
    except Exception as e:
        log.warning(f"Erreur retour final home: {e}")
    try:
        device.close()
    except Exception as e:
        log.warning(f"Erreur fermeture Dobot: {e}")