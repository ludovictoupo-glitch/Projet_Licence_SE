# Système Industriel de Tri Automatisé - Dobot Magician & IoT

Ce projet présente la conception et la réalisation d'une cellule de tri de pièces industrielles automatisée et sécurisée. Le système intègre un bras robotisé **Dobot Magician**, un convoyeur motorisé piloté par un microcontrôleur **Arduino**, une communication sans fil **XBee**, ainsi qu'une interface homme-machine (IHM) développée sous **Flask** avec persistance des données sous **SQLite**.

L'ensemble de l'architecture a été optimisé pour répondre aux exigences de la Smart Factory (Industrie 4.0), avec une capacité nominale de traitement de **haute cadence (jusqu'à 5000 tris par heure)**.

# Architecture Matérielle (Hardware)

Le système est composé de trois blocs principaux qui communiquent en temps réel :

1. **Unité de Convoyage & Détection (Arduino Uno / Nano) :**
   * **Capteur infrarouge (IR) de position :** Détecte l'arrivée d'une pièce à l'entrée du tapis roulant.
   * **Moteur pas-à-pas / CC :** Entraîne le convoyeur industriel.
   * **Module XBee (Émetteur) :** Envoie instantanément un signal sans fil dès qu'une pièce est positionnée et immobilisée, déclenchant le protocole de tri.

2. **Unité de Tri Robotisée (Raspberry Pi 4 & Dobot Magician) :**
   * **Module XBee (Récepteur) :** Reçoit le signal de validation de l'Arduino.
   * **Raspberry Pi :** Cerveau local de l'application, héberge le script maître (`dobotmainihm.py`), l'algorithme de traitement d'images (reconnaissance de couleur) et le serveur web.
   * **Dobot Magician :** Exécute les trajectoires de pick-and-place vers les zones de stockage dédiées.

3. **Supervision & IHM (Serveur Flask) :**
   * Centralise le tableau de bord, l'état du système, le contrôle des flux et la gestion de la sécurité.

# Architecture Logicielle & Sécurité Industrielle

# Authentification Intégrée & Cookies Volatils
Pour interdire l'accès aux commandes critiques de l'usine (START, STOP, configuration), l'IHM intègre un protocole de sécurité strict via l'extension **Flask-Login** :
* **Compte Admin Unique :** Authentification restreinte au profil `dobot_admin`.
* **Hachage Cryptographique :** Les mots de passe ne sont pas stockés en clair. Ils sont sécurisés sous forme d'empreinte numérique irréversible (*hash*) via le module `werkzeug.security`.
* **Session Éphémère & Volatile :** Configuration stricte de la session pour expirer automatiquement dès la fermeture du navigateur de l'opérateur (`SESSION_PERMANENT = False`).
* **Signature Numérique :** Signature des cookies via une clé secrète (`SECRET_KEY`) masquée dans les variables d'environnement (`Systemd`) du Raspberry Pi pour parer aux attaques par falsification.

# Base de Données SQLite
Toutes les données de production sont stockées de façon permanente dans une base de données `project_Dobot.db` :
* Incrémentation en temps réel des pièces par couleur (Rouge, Bleu, Vert, Jaune).
* Calcul automatisé et centralisé du **Tri Total** directement en requêtes SQL (`SUM` / `COUNT`) pour éviter toute perte de données en cas de coupure de courant sur la ligne.
