from flask import Flask, render_template, jsonify, request, redirect, url_for, jsonify
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import check_password_hash
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

app.config['SECRET_KEY'] = os.environ.get('FLASK_SECRET_KEY', 'cle_de_secours_ultra_basique') # Indispensable pour sécuriser les sessions

# CONFIGURATION STRICTE : Déconnexion dès qu'on ferme le navigateur
app.config['REMEMBER_COOKIE_DURATION'] = 0
app.config['SESSION_PERMANENT'] = False

# Initialisation du gestionnaire de connexion
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login' # Redirige ici si l'accès est refusé

# Configuration de ton compte unique d'entreprise
ADMIN_SOCIETE = {
    "id": "1",
    "username": "dobot_admin",
    "password_hash": "pbkdf2:sha256:260000$7z43U1776wqHrw2J$798ce1d07102fba94a30079318aa569508e01fe3a1ba0e09f9502bbc84321282" # Hash de "motdepasse123"
}

DB_FILE = 'project_Dobot.db'


# INITIALISATION DE LA BASE DE DONNÉES SQLITE
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
    # Initialisation des compteurs à 0 pour nos 4 couleurs + la ligne 'total' (si elle n'existe pas déjà)
    couleurs = ['jaune', 'bleu', 'rouge', 'vert']
    cursor.execute("INSERT OR IGNORE INTO stats (color, count) VALUES ('total', 0)")
    for couleur in couleurs:
        cursor.execute("INSERT OR IGNORE INTO stats (color, count) VALUES (?, 0)", (couleur,))
    conn.commit()
    conn.close()

# On initialise la base SQLite au démarrage de l'application
init_db()

# LANCEMENT AUTOMATIQUE DU ROBOT COMME PROCESSUS SÉPARÉ 
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

# FONCTION DE COMMUNICATION SOCKET AVEC LE ROBOT
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

#  GESTION DES STATISTIQUES (SQLITE) 
def load_stats():
    """Lit les statistiques depuis SQLite et les formate en dictionnaire pour l'IHM"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT color, count FROM stats")
    rows = cursor.fetchall()
    conn.close()
    
    # Structure attendue par l'IHM
    stats = {"total": 0, "rouge": 0, "vert": 0, "bleu": 0   , "jaune": 0}
    
    for color, count in rows:
        if color in stats:
            stats[color] = count
            
    return stats

class User(UserMixin):
    def __init__(self, id, username):
        self.id = id
        self.username = username

@login_manager.user_loader
def load_user(user_id):
    if user_id == ADMIN_SOCIETE["id"]:
        return User(id=ADMIN_SOCIETE["id"], username=ADMIN_SOCIETE["username"])
    return None


@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index')) # Déjà connecté ? Go sur l'IHM
        
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        # Vérification des identifiants uniques de l'entreprise
        if username == ADMIN_SOCIETE["username"] and check_password_hash(ADMIN_SOCIETE["password_hash"], password):
            user = User(id=ADMIN_SOCIETE["id"], username=ADMIN_SOCIETE["username"])
            login_user(user) # Ouvre la session utilisateur
            return redirect(url_for('index'))
        else:
            return "Identifiants invalides. <a href='/login'>Réessayer</a>", 401
            
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user() # Détruit le cookie de session
    return redirect(url_for('login'))

# ROUTES FLASK PRINCIPALES
@app.route('/')
@login_required
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
    valides = ["rouge", "bleu", "vert", "jaune"] # On ne met que les vraies couleurs ici
     # La ligne 'total' est gérée automatiquement, pas d'incrément manuel
    if color in valides:
        try:
            # 1. On ouvre la connexion SQLite en PREMIER
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            
            # 2. On incrémente la couleur reçue (ex: rouge + 1)
            cursor.execute("UPDATE stats SET count = count + 1 WHERE color = ?", (color,))
            
            # 3. AUTOMATISATION : On recalcule immédiatement la somme de tout le monde
            cursor.execute("SELECT SUM(count) FROM stats WHERE color != 'total'")
            total = cursor.fetchone()[0]
            if total is None: 
                total = 0
                
            # 4. On enregistre ce nouveau total directement dans la ligne 'total'
            cursor.execute("UPDATE stats SET count = ? WHERE color = 'total'", (total,))
            
            # 5. On valide et on ferme proprement
            conn.commit()
            conn.close()
            
            print(f" SQLite mis à jour : +1 {color} | Nouveau total = {total}")
            
            # On renvoie les stats à jour à l'IHM
            return jsonify(load_stats())
            
        except Exception as e:
            # En cas d'erreur, on s'assure de ne pas laisser la BDD verrouillée
            try: conn.close()
            except: pass
            return jsonify({"error": f"Erreur BDD : {str(e)}"}), 500
            
    return jsonify({"error": f"Couleur '{color}' inconnue ou invalide"}), 400


@app.route('/start_robot', methods=['POST'])
@login_required
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
@login_required
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
@login_required
def reset_stats():
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        # 1. ÉTAPE INDUSTRIELLE : Création automatique de la table d'archives si absente
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS donner_archives_tri (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date_archive TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                jaune INTEGER,
                rouge INTEGER,
                vert INTEGER,
                bleu INTEGER,
                total_tri INTEGER
            )
        ''')
        
        # 2. Récupération des valeurs courantes de la table stats pour archivage
        cursor.execute("SELECT color, count FROM stats")
        rows = cursor.fetchall()
        actuel = {row[0]: row[1] for row in rows}
        
        # Sécurisation des variables pour éviter les erreurs de clés manquantes
        j = actuel.get('jaune', 0)
        r = actuel.get('rouge', 0)
        v = actuel.get('vert', 0)
        b = actuel.get('bleu', 0)
        t = actuel.get('total', 0)
        
        # 3. ARCHIVAGE : Insertion des données de production dans l'historique
        cursor.execute('''
            INSERT INTO donner_archives_tri (jaune, rouge, vert, bleu, total_tri)
            VALUES (?, ?, ?, ?, ?)
        ''', (j, r, v, b, t))
        
        # 4. REMISE À ZÉRO : Nettoyage de la table active pour la nouvelle session
        cursor.execute("UPDATE stats SET count = 0")
        
        # Validation définitive des écritures dans le fichier SQLite
        conn.commit()
        conn.close()
        
        print(" [INFO] Production archivée avec succès et compteurs réinitialisés à 0.")
        
        # Renvoie les nouvelles stats à 0 à ton interface HTML pour rafraîchir l'affichage
        return jsonify(load_stats())
        
    except Exception as e:
        try:
            conn.close()
        except:
            pass
        return jsonify({"error": f"Erreur lors de l'archivage et de la réinitialisation : {str(e)}"}), 500

if __name__ == '__main__':
    try:
        app.run(host='0.0.0.0', port=5000, debug=True, use_reloader=False)
    finally:
        print("Arrêt du script Robot...")
        try:
            robot_process.terminate()
        except Exception:
            pass