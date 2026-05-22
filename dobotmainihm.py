import logging
import socket
import threading
import time
import json
import requests
from queue import Empty
import os

#CONFIGURATION
HOST = '127.0.0.1'
PORT = 5001
robot_actif = False  

# Configuration des logs
logging.basicConfig(level=logging.INFO)
log = logging.getLogger()

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
                print("SIGNAL WEB REÇU : ACTIVATION DU ROBOT")
                log.info("Signal START reçu du web, activation du robot")
                robot_actif = True 
            elif data == "STOP":
                print("SIGNAL WEB REÇU : ARRÊT DU ROBOT")
                log.info("Signal STOP reçu du web, arrêt du robot")
                robot_actif = False
            conn.close() # Pense toujours à refermer la connexion entrante

def envoyer_stats_au_web(couleur_detectee):
    try:
        requests.post('http://127.0.0.1:5000/update_tri', 
                      json={'color': couleur_detectee.lower()}, timeout=1)
        print(f"Stats mises à jour envoyées à Flask : {couleur_detectee}")
    except Exception as e:
        print(f"Erreur envoi stats : {e}")

# IMPORTS ROBOTIQUE
from dobot_camera import init_camera, detecter_couleur, fermer_camera
from dobotsystem_ihm import init_robot_system, close_robot_system, couleur_queue, cycle, fermer_eclairage

device = None

try:
    log.info(" START MAIN ")
    init_camera()
    device = init_robot_system(detecter_couleur)
    
    # Lancement du serveur socket en arrière-plan
    threading.Thread(target=socket_server, daemon=True).start()

    while True:
        # SI LE ROBOT N'EST PAS ACTIVÉ, ON ATTEND SANS SATURER LE CPU
        if not robot_actif:
            while not couleur_queue.empty():
                try:
                    couleur_queue.get_nowait() # Vide la file pour éviter l'accumulation
                except Empty:
                    break # TRÈS IMPORTANT : Laisse respirer le CPU du Raspberry Pi !
            continue

        # SI LE ROBOT EST ACTIVÉ, ON TRAVAILLE
        while True:
                try:
                    couleur = couleur_queue.get(timeout=1)
                    log.info(f"Couleur récupérée depuis la file: {couleur}")
                    cycle(device, couleur)
            
                    
            # Envoi de la vraie couleur triée à SQLite/JSON via Flask
                    envoyer_stats_au_web(couleur)

                except Empty:
                    if not robot_actif:
                        log.info("Robot désactivé, retour en mode veille")
                        break  # Sort de la boucle de travail pour retourner en veille
                except Exception as e:
                    log.error(f"Erreur dans la boucle principale: {e}")
                     # Petite pause pour éviter les boucles d'erreur rapides

except KeyboardInterrupt:
    log.info("Arrêt manuel par l'utilisateur")
finally:
    fermer_camera()
    if device:
        close_robot_system(device)
    log.info("Système arrêté proprement")