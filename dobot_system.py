import time
import threading
import logging
from queue import Queue, Empty, Full
import math
import serial
import serial.tools.list_ports
from pydobot import Dobot

logging.basicConfig(level=logging.INFO)
log = logging.getLogger()

couleur_queue = Queue(maxsize=5)
stop_event = threading.Event()

Positions = {
    "prise": (213.3245, 5.2245, 1.6391, 1.4029),
    "R": (19.3407, -196.8356, -49.1944, -84.3882),
    "V": (71.6597, -204.0571, -49.544, -70.65),
    "B": (47.9391, -130.6879, -47.5538, -69.8559),
    # Ajoute une vraie position jaune si nécessaire
    # "J": (...),
    "home": (200, 0, 50, 0),
}

Z_SAFE = 50
Z_MIN = -50
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


def safe_move(device, x, y, z, r=0):
    """Mouvement sécurisé inspiré du safe_move DobotDll. """
    if not robot_ready(device):
        raise RuntimeError("Robot non prêt")

    if not in_reach(x, y):
        raise RuntimeError(
            f"Position hors enveloppe: x={x:.1f}, y={y:.1f}")
    # =========================
    # POSITION ACTUELLE
    # =========================
    pose = device.pose()
    cx = pose[0]
    cy = pose[1]
    cz = pose[2]
    cr = pose[3]
    # =========================
    # DETECTION ZONE RISQUEE
    # =========================
    risky = abs(y) > 120 or z < 40
    # =========================
    # PASSAGE INTERMEDIAIRE
    # =========================
    if risky:
        log.info("Zone risquée → passage intermédiaire")
        # Remontée verticale
        if cz < Z_SAFE:
            device.move_to( cx, cy, Z_SAFE, cr, wait=True)
            time.sleep(0.1)
        # Passage centre Y=0
        device.move_to( cx, 0, Z_SAFE, 0, wait=True )
        time.sleep(0.1)
    # =========================
    # REMONTEE SI NECESSAIRE
    # =========================
    if cz < Z_SAFE:
        device.move_to( cx, cy, Z_SAFE, cr, wait=True)
        time.sleep(0.1)
    # =========================
    # DEPLACEMENT HORIZONTAL
    # =========================
    device.move_to(x, y, Z_SAFE, cr, wait=True)
    time.sleep(0.1)
    # =========================
    # DESCENTE
    # =========================
    device.move_to( x, y, z, r, wait=True)
    time.sleep(0.1)

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
                            log.info("OBJET reçu → capture caméra immédiate")
                            couleur = detecter_couleur_callback()
                            log.info(f"Couleur capturée: {couleur}")
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
    log.info("=== HOMING LOGICIEL ===")
    safe_move(device, *Positions["home"])
    log.info("Homing terminé")


def couleur_to_position(couleur):
    mapping = {
        "rouge": "R",
        "vert": "V",
        "bleu": "B",

        # Temporaire : jaune envoyé vers V
        # Remplace par "J" si tu ajoutes une position jaune.
        "jaune": "V",
    }

    return mapping.get(couleur)


def cycle(device, couleur):
    log.info("===== CYCLE DOBOT =====")
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
        log.info("===== FIN CYCLE =====")


def init_robot_system(detecter_couleur_callback):
    log.info("=== INIT ROBOT SYSTEM ===")
    dobot_port, xbee_port = detect_ports()
    if not dobot_port:
        raise RuntimeError("Dobot introuvable")
    if not xbee_port:
        raise RuntimeError("XBee introuvable")
    log.info(f"Dobot: {dobot_port}")
    log.info(f"XBee: {xbee_port}")
    device = Dobot(port=dobot_port)
    time.sleep(1)

    try:
        device._set_queued_cmd_clear()

        device._set_ptp_joint_params(
            50, 50, 50, 50,
            50, 50, 50, 50
        )
    except Exception as e:
        log.warning(f"Impossible de régler les paramètres PTP: {e}")

    set_suction(device, False)
    device.speed(60, 60)

    safe_move(device, *Positions["home"])
    do_homing(device)

    threading.Thread(
        target=listen_xbee,
        args=(xbee_port, detecter_couleur_callback),
        daemon=True
    ).start()

    log.info("=== ROBOT SYSTEM READY ===")

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