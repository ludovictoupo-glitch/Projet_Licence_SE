from flask import Flask, render_template, jsonify, request
import os
import socket 
import subprocess  # Pour lancer le robot
import sys         # Pour trouver le bon Python
import atexit      # Pour fermer le robot proprement à la fin
import logging     # Configuration des logs
import sqlite3

# Configuration du logging
logging.basicConfig(level=logging.INFO)

robot_moving = False  # Variable globale pour suivre l'état du robot
system_active = False # Variable pour l'état du système

app = Flask(__name__)

DB_FILE = 'project_Dobot.db'

# --- INITIALISATION DE LA BASE DE DONNÉES ---
def init_db():
    """Crée la base de données et la table si elles n'existent pas"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS stats (
            color TEXT PRIMARY KEY,
            count INTEGER DEFAULT 0
        )
    ''')
    # Initialisation des compteurs à 0 pour nos 4 couleurs
    couleurs = ['jaune', 'bleu', 'rouge', 'vert']
    for couleur in couleurs:
        cursor.execute("INSERT OR IGNORE INTO stats (color, count) VALUES (?, 0)", (couleur,))
    conn.commit()
    conn.close()

# On initialise la base SQLite au démarrage de l'application
init_db()

# --- 1. LANCEMENT AUTOMATIQUE DU ROBOT ---
# On lance le robot comme un processus séparé
robot_process = subprocess.Popen([sys.executable, "dobotmainihm.py"])
print("Démarrage automatique du script Robot...")

# Sécurité : On tue le processus robot quand on quitte Flask
def cleanup():
    print("Arrêt du système robotique...")
    try:
        robot_process.terminate()
    except Exception:
        pass

atexit.register(cleanup)

# --- 2. FONCTION DE COMMUNICATION ---
def envoyer_signal_socket(message):
    """Envoie un message synchrone au serveur de commande du Dobot"""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(2) # Évite de bloquer l'IHM si le robot est figé
            s.connect(('127.0.0.1', 5001))
            s.sendall(message.encode('utf-8'))
            logging.info(f" Signal {message} transmis au robot avec succès.")
            return True
    except Exception as e:
        logging.error(f"⚠️ Robot non prêt (Socket Error sur {message}): {e}")
        return False

# --- 3. GESTION DES STATISTIQUES (SQLITE) ---
def load_stats():
    """Lit les statistiques depuis SQLite et les formate en dictionnaire pour l'IHM"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT color, count FROM stats")
    rows = cursor.fetchall()
    conn.close()
    
    # Structure attendue par l'IHM
    stats = {"total": 0, "rouge": 0, "vert": 0, "bleu": 0   , "jaune": 0}
    total = 0
    for color, count in rows:
        if color in stats:
            stats[color] = count
            total += count
            
    stats["total"] = total
    return stats

# --- 4. ROUTES FLASK ---
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/get_stats')
def get_stats():
    return jsonify(load_stats())

@app.route('/get_status')
def get_status():
    global system_active
    return jsonify({"moving": system_active})

@app.route('/update_tri', methods=['POST'])
def update_tri():
    """Appelée par dobotmainihm.py après chaque cube déposé"""
    color = request.json.get('color', '').lower()
    valides = ["rouge", "bleu", "vert", "jaune"]
    
    if color in valides:
        try:
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            cursor.execute("UPDATE stats SET count = count + 1 WHERE color = ?", (color,))
            conn.commit()
            conn.close()
            
            print(f" SQLite mis à jour : +1 {color}")
            return jsonify(load_stats())
        except Exception as e:
            return jsonify({"error": f"Erreur BDD : {str(e)}"}), 500
            
    return jsonify({"error": "Couleur inconnue"}), 400

@app.route('/start_robot', methods=['POST'])
def start_robot():
    global system_active
    system_active = True
    logging.info("Bouton START pressé sur l'interface.")
    
    # Envoi du signal via la fonction socket unifiée
    succes = envoyer_signal_socket("START")
    
    if succes:
        return jsonify({"status": "success", "message": "Robot démarré"})
    else:
        return jsonify({"status": "Erreur", "message": "Le script robot ne répond pas sur le port 5001"}), 500

@app.route('/stop_robot', methods=['POST'])
def stop_robot():
    global system_active
    system_active = False
    logging.warning("Bouton STOP pressé sur l'interface.")
    
    succes = envoyer_signal_socket("STOP")
    
    if succes:
        return jsonify({"status": "success", "message": "Signal STOP envoyé"})
    else:
        return jsonify({"status": "Erreur", "message": "Impossible de joindre le robot pour l'arrêt"}), 500

@app.route('/reset_stats', methods=['POST'])
def reset_stats():
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("UPDATE stats SET count = 0")
        conn.commit()
        conn.close()
        return jsonify(load_stats())
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    try:
        app.run(host='0.0.0.0', port=5000, debug=True, use_reloader=False)
    finally:
        print("Arrêt du script Robot...")
        try:
            robot_process.terminate()
        except Exception:
            pass