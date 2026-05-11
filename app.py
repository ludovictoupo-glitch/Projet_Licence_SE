from flask import Flask, render_template, jsonify, request
import json
import os
import socket 
import subprocess  # Pour lancer le robot
import sys         # Pour trouver le bon Python
import atexit      # Pour fermer le robot proprement à la fin

app = Flask(__name__)

STATS_FILE = 'stats.json'

# --- 1. LANCEMENT AUTOMATIQUE DU ROBOT ---
# On lance le robot comme un processus séparé
# stdout=None et stderr=None permettent de voir les prints du robot dans cette console
robot_process = subprocess.Popen([sys.executable, "dobotmainihm.py"])

# Sécurité : On tue le processus robot quand on quitte Flask
def cleanup():
    print("Arrêt du système robotique...")
    robot_process.terminate()

atexit.register(cleanup)

# --- 2. FONCTIONS DE COMMUNICATION ---
def envoyer_signal_socket(message):
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(2)
            # UTILISE TOUJOURS 127.0.0.1 pour la communication interne
            s.connect(('127.0.0.1', 5001)) 
            s.sendall(message.encode('utf-8'))
            print(">>> Signal transmis au robot avec succès")
    except Exception as e:
        # SI TU VOIS CETTE ERREUR DANS LA CONSOLE : 
        # C'est que dobotmainihm.py n'a pas démarré son serveur socket.
        print(f"⚠️ Erreur de transmission : {e}")

# --- 3. GESTION DES STATISTIQUES (JSON) ---
def load_stats():
    if os.path.exists(STATS_FILE):
        try:
            with open(STATS_FILE, 'r') as f:
                return json.load(f)
        except json.JSONDecodeError:
            pass # Si le fichier est corrompu
    return {"total": 0, "rouge": 0, "bleu": 0, "vert": 0}

def save_stats(stats):
    with open(STATS_FILE, 'w') as f:
        json.dump(stats, f, indent=4) # indent=4 rend le JSON lisible

# --- 4. ROUTES FLASK ---
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/get_stats')
def get_stats():
    return jsonify(load_stats())

@app.route('/start_robot', methods=['POST'])
def start_robot():
    # Envoie le signal au serveur socket qui tourne dans dobotmainihm.py
    envoyer_signal_socket("START")
    return jsonify({"status": "success", "message": "Signal START envoyé"})

@app.route('/update_tri', methods=['POST'])
def update_tri():
    """Cette route est appelée par le robot (dobotmainihm.py) après chaque tri"""
    color = request.json.get('color', '').lower()
    stats = load_stats()
    
    if color in stats:
        stats[color] += 1
        stats['total'] += 1
        save_stats(stats)
        print(f"📊 Stats mises à jour : +1 {color}")
        return jsonify(stats)
    return jsonify({"error": "Couleur inconnue"}), 400

if __name__ == '__main__':
    # On désactive le 'reloader' car sinon il lancerait le robot deux fois !
    app.run(host='0.0.0.0', port=5000, debug=True, use_reloader=False)