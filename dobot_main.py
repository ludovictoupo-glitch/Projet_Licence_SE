import logging
from queue import Empty
from dobot_camera import init_camera, detecter_couleur, fermer_camera
from dobot_system import init_robot_system, close_robot_system, couleur_queue, cycle, fermer_eclairage

logging.basicConfig(level=logging.INFO)
log = logging.getLogger()

device = None

try:
    log.info("=== START MAIN ===")
    init_camera()
    log.info("Caméra prête")
    device = init_robot_system(detecter_couleur)
    log.info("Système prêt")
    while True:
        try:
            couleur = couleur_queue.get(timeout=1)
            log.info(f"Couleur récupérée depuis la file: {couleur}")
            cycle(device, couleur)
        except Empty:
            continue
        except Exception as e:
            log.error(f"Erreur dans la boucle principale: {e}")
except KeyboardInterrupt:
    log.info("Arrêt demandé")
finally:
    fermer_camera()
    if device:
        close_robot_system(device)
    log.info("Système arrêté proprement")
