import logging
import socket
import threading
import requests
from queue import Empty
import os

# --- CONFIGURATION ---
HOST = '127.0.0.1'
PORT = 5001
robot_actif = False  # Le robot attend le signal Web pour devenir True

def socket_server():
    global robot_actif
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind((HOST, PORT))
        s.listen()
        print(f"Serveur Socket prêt sur le port {PORT}...")
        
        while True:
            conn, addr = s.accept()
            data = conn.recv(1024).decode('utf-8')
            if data == "START":
                print(">>> SIGNAL WEB REÇU : ACTIVATION DU ROBOT")
                robot_actif = True 
            elif data == "STOP":
                print(">>> SIGNAL WEB REÇU : ARRÊT DU ROBOT")
                robot_actif = False

def envoyer_stats_au_web(couleur_detecter):
    """Met à jour le JSON via Flask"""
    try:
        requests.post('http://127.0.0.1:5000/update_tri', 
                      json={'color': couleur_detecter.lower()}, timeout=1)
        print(f"📊 Stats mises à jour : {couleur_detecter}")
    except Exception as e:
        print(f"Erreur envoi stats : {e}")

# --- IMPORTS ROBOTIQUE ---
from dobotcamera_detection import init_camera, detecter_couleur, fermer_camera
from dobot_system import init_robot_system, close_robot_system, couleur_queue, cycle

logging.basicConfig(level=logging.INFO)
log = logging.getLogger()

device = None

try:
    log.info("=== START MAIN ===")
    init_camera()
    device = init_robot_system(detecter_couleur)
    
    # Lancement du serveur socket en arrière-plan
    threading.Thread(target=socket_server, daemon=True).start()

    while True:
        # SI LE ROBOT N'EST PAS ACTIVÉ, ON ATTEND
        if not robot_actif:
            # On vide la file de la caméra pour ne pas accumuler de vieux objets
            try:
                couleur_queue.get_nowait()
            except Empty:
                pass
            continue 

        # SI LE ROBOT EST ACTIVÉ, ON TRAVAILLE
        try:
            couleur = couleur_queue.get(timeout=1)
            log.info(f"Couleur détectée : {couleur}")

            # 1. Exécuter le mouvement
            cycle(device, couleur)

            # 2. Envoyer la mise à jour à l'IHM Flask
            envoyer_stats_au_web(couleur)

        except Empty:
            continue

except KeyboardInterrupt:
    log.info("Arrêt demandé")
finally:
    fermer_camera()
    if device:
        close_robot_system(device)
    log.info("Système arrêté proprement")