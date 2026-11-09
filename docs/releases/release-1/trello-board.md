# Board Trello PrediMaint Release 1

## Configuration du board

- Nom proposé : **PrediMaint — Release 1**
- Listes : `Backlog`, `À faire`, `En cours`, `À tester`, `Terminé`, `Bloqué`
- Labels : `ESP32`, `Backend`, `MQTT`, `PostgreSQL`, `API/Sécurité`, `Projet`
- Chaque carte porte la référence US, les critères d’acceptation ci-dessous et un lien vers le commit ou la pull request.

## Cartes à créer

### US-18 — Collecte des mesures des capteurs

**Acteur :** système ESP32. **Points :** 8. **Priorité :** très haute.

- Acquisition DHT22 et état numérique HW-072 depuis les GPIO configurés.
- Message JSON contient séquence, température, humidité, taux/compte vibration et source courant.
- Le courant simulé est explicitement indiqué tant que la mesure matérielle n’est pas validée.
- Test : console Thonny montre des lectures plausibles et séquence croissante.

### US-19 — Stockage des mesures

**Acteur :** système backend. **Points :** 5. **Priorité :** haute.

- Le backend valide le JSON MQTT et pose un timestamp UTC serveur.
- PostgreSQL conserve les mesures et indexe l’historique par machine/date.
- Un JSON malformé est rejeté sans arrêter l’abonné.
- Test : confirmer la ligne récente avec `SELECT` et vérifier le timestamp.

### US-20 — Détection de dépassement de seuil

**Acteur :** système backend. **Points :** 8. **Priorité :** très haute.

- Seuils avertissement et critique enregistrés par machine/grandeur.
- Dépassement ouvre ou met à jour une alerte ; retour à la normale clôture l’alerte.
- Une alerte active n’est pas dupliquée à chaque mesure.
- Test : publier une valeur en avertissement, une valeur critique puis une valeur normale.

### US-23 — Déclaration des machines et capteurs

**Acteur :** administrateur du système / Responsable. **Points :** 5. **Priorité :** haute.

- Le Responsable crée et met à jour les machines, les archive et les réactive sans perdre l’historique.
- Il déclare les capteurs avec grandeur, type, GPIO et unité, puis peut les désactiver/réactiver.
- Les rôles de lecture n’ont pas accès à l’administration.
- Test : créer machine/capteur, basculer leur état et vérifier l’accès Technicien.

### US-41 — Sécurité des échanges MQTT

**Acteur :** administrateur du système. **Points :** 5. **Priorité :** haute.

- Anonyme refusé ; appareil et backend ont des comptes distincts.
- ACL : appareil publie seulement sur son topic de mesure/état ; backend lit les topics nécessaires.
- Secrets hors Git.
- Test : publication légitime acceptée, topic d’une autre machine et abonnement appareil refusés.

### US-42 — Sécurité de l’API

**Acteur :** administrateur du système. **Points :** 5. **Priorité :** haute.

- JWT à expiration, mots de passe hachés, autorisations vérifiées côté serveur.
- Requête sans jeton `401`, rôle insuffisant `403`, corps invalide `422`.
- L’ingestion HTTP manuelle est restreinte au Responsable.
- Test : exécuter les tests d’API et vérifier les rôles via `/docs`.

### US-47 — Dépôt Git et tableau Trello

**Acteur :** membre de l’équipe. **Points :** 2. **Priorité :** haute.

- `.env` et `firmware/config.json` exclus du dépôt.
- Commits cohérents et board de suivi contenant les neuf cartes de Release 1.
- Test : `git check-ignore .env firmware/config.json`; vérifier les listes et critères dans le board.

### US-48 — Installation du broker MQTT

**Acteur :** membre de l’équipe. **Points :** 3. **Priorité :** haute.

- Mosquitto démarre avec Compose, persistance, authentification, ACL et healthcheck.
- Port hôte documenté et accessible à l’ESP32 sur le réseau local.
- Test : `docker compose ps`, journal Mosquitto et publication firmware.

### US-49 — Firmware ESP32 de base

**Acteur :** membre de l’équipe. **Points :** 3. **Priorité :** haute.

- Connexion Wi-Fi, reconnexion, Last Will, acquisition périodique et publication MQTT QoS 1.
- Configuration externe à `main.py`; pins conformes au câblage réalisé.
- Test : cycle de 30 minutes, coupure/restauration Wi-Fi et retour des publications.
