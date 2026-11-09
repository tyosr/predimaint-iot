# PrediMaint — Releases et guide de validation

Ce document suit le découpage du backlog fourni. Il décrit le **Release 1 uniquement** ; les sections fonctionnelles des Releases 2 et 3 seront ajoutées lorsqu’elles seront planifiées. Le Release 1 pose le socle IoT : acquisition, transport MQTT, stockage, alertes, sécurité et administration du parc.

## Découpage des releases

| Release | PBI | Points | État de la documentation |
|---|---:|---:|---|
| Release 1 | 9 | 44 | Détaillé ci-dessous |
| Release 2 | 21 | 100 | À documenter ultérieurement |
| Release 3 | 20 | 93 | À documenter ultérieurement |

## Release 1 — périmètre

| Réf. | User story | Livraison de ce release |
|---|---|---|
| US-18 | Collecte des mesures des capteurs | Le firmware MicroPython acquiert DHT22 et HW-072, calcule le taux d’événements par fenêtre et publie un message JSON. Le courant reste simulé tant que le câblage ACS712 n’est pas protégé et calibré. |
| US-19 | Stockage des mesures | Le backend valide le JSON MQTT, ajoute l’horodatage serveur UTC et conserve les mesures dans PostgreSQL avec index machine/date. |
| US-20 | Détection de dépassement de seuil | Seuils avertissement/critique par machine et grandeur ; création/mise à jour d’une alerte active, puis clôture automatique au retour sous le seuil d’avertissement. |
| US-23 | Déclaration des machines et capteurs | Le Responsable peut déclarer des machines et leurs capteurs, modifier les métadonnées, désactiver/réactiver un capteur et archiver/réactiver une machine sans effacer son historique. |
| US-41 | Sécurité des échanges MQTT | Connexion par mot de passe, compte distinct pour le firmware et le backend, accès anonyme interdit, ACL limitant un équipement à ses topics et backend en lecture seule sur les topics de télémétrie/état. |
| US-42 | Sécurité de l’API | Jetons JWT expirables, hachage des mots de passe, contrôle des rôles côté serveur, validation des entrées et tests d’accès non autorisé. |
| US-47 | Dépôt Git et tableau Trello | Dépôt Git local, règles d’exclusion des secrets, procédure de branches/commits et modèle de board avec les neuf cartes Release 1 dans `docs/releases/release-1/trello-board.md`. La création du board dans un compte Trello reste une action manuelle. |
| US-48 | Installation du broker MQTT | Mosquitto est déployé par Docker Compose, persistant, authentifié, protégé par ACL et vérifié par healthcheck. Port hôte 1884, port interne Docker 1883. |
| US-49 | Firmware ESP32 de base | Connexion Wi-Fi, reconnexion, DHT22, comptage d’événements HW-072 par interruption, Last Will MQTT et publication QoS 1 toutes les cinq secondes. |

## Architecture et ports

```text
DHT22 + HW-072 + ACS712 (désactivé/simulé)
              ↓ MicroPython / JSON
ESP32 ── MQTT 1884 (hôte) → Mosquitto 1883 (Docker)
                                  ↓ MQTT interne
                             FastAPI → PostgreSQL
                                  ↓ HTTP JSON, polling 5 s
                              Interface web :8001
```

| Service | Adresse depuis le PC | Adresse interne Docker |
|---|---|---|
| Application/API | `http://localhost:8001` | `backend:8000` |
| MQTT | `PC_IP:1884` | `mosquitto:1883` |
| PostgreSQL | non exposé sur le PC | `postgres:5432` |

Le backend horodate chaque mesure à réception. Le navigateur actualise par polling HTTP toutes les cinq secondes ; MQTT transporte les mesures de l’ESP32 au backend. Le port PostgreSQL n’est pas publié sur le réseau de l’hôte.

## Préparer et démarrer

### Configuration des secrets

1. Depuis PowerShell, place-toi dans le dossier du dépôt.
2. Si `.env` n’existe pas, copie `.env.example` vers `.env`.
3. Renseigne des secrets différents et robustes pour PostgreSQL, JWT, le compte MQTT appareil, le compte MQTT backend et les comptes de démonstration. Ne colle jamais les vrais secrets dans `config.example.json` ni dans Git.
4. `MQTT_USERNAME` / `MQTT_PASSWORD` sont ceux de l’ESP32. `MQTT_BACKEND_USERNAME` / `MQTT_BACKEND_PASSWORD` sont générés pour l’abonné backend. Le nom `predimaint_backend` est utilisé par l’ACL.
5. L’URL `DATABASE_URL` doit employer les mêmes identifiants PostgreSQL que `POSTGRES_USER`, `POSTGRES_PASSWORD` et `POSTGRES_DB`. Encoder les caractères spéciaux du mot de passe dans l’URL.

Les ports hôte peuvent être changés via `MQTT_HOST_PORT` et `API_HOST_PORT`. Le firmware doit alors utiliser `mqtt_port` égal à `MQTT_HOST_PORT`.

### Lancer les services

```powershell
docker compose up --build
```

Laisse cette fenêtre ouverte. Ouvre `http://localhost:8001`. Pour lancer en arrière-plan : `docker compose up -d --build`; état : `docker compose ps`; journaux : `docker compose logs -f backend mosquitto postgres`; arrêt : `docker compose down`. N’utilise pas `docker compose down -v` sauf si tu veux supprimer aussi les mesures conservées dans le volume PostgreSQL.

### Charger le firmware

1. Dans Thonny, sélectionne MicroPython ESP32 et le port USB de la carte.
2. Copie `firmware/config.example.json` vers l’ESP32 en `/config.json`, puis renseigne le SSID/mot de passe Wi-Fi, `mqtt_host` (IPv4 du PC), `mqtt_port` (1884 par défaut), identifiants de l’appareil et `machine_id` (`demo-machine`).
3. Enregistre `firmware/main.py` sur l’ESP32 en `/main.py` et lance-le avec F5. `umqtt.simple` doit être présent.
4. La console doit afficher `Wi-Fi connecté`, puis `Publié: {...}`.

**Sécurité électrique :** le firmware conserve `current_mode` à `simulated`. Ne raccorde pas la sortie ACS712 directement à GPIO34 lorsque le module est alimenté en 5 V. L’activation matérielle attend le pont diviseur vérifié et un calibrage. Ne branche pas le secteur sur la breadboard.

## Comptes de démonstration et rôles

Les trois utilisateurs initiaux sont créés au premier démarrage, selon les mots de passe définis dans `.env` :

| Adresse | Rôle | Permissions Release 1 |
|---|---|---|
| `tech@predimaint.local` | Technicien | Consultation, acquittement/clôture d’alertes et enregistrement d’intervention via API |
| `manager@predimaint.local` | Responsable | Permissions technicien, gestion machines/capteurs/seuils et ingestion HTTP de test |
| `director@predimaint.local` | Direction | Consultation en lecture seule |

L’application ne permet pas encore de créer des comptes supplémentaires dans cette version. Changer les valeurs de mot de passe du `.env` après la création initiale des utilisateurs ne modifie pas leurs mots de passe déjà hachés en base.

## Guide de test Release 1

### T1 — US-48 Broker démarré et authentifié

```powershell
docker compose ps
docker compose logs --tail 50 mosquitto
```

Attendu : `mosquitto` est `running` et `healthy`, le broker écoute sur 1883 dans Docker, l’accès hôte est publié sur 1884, et le journal indique le démarrage sans erreur d’ACL ou de fichier de mot de passe. Il ne doit pas accepter de client anonyme.

### T2 — US-42 Authentification et rôles API

Ouvre `http://localhost:8001/docs`.

1. `GET /api/health` doit répondre `200`.
2. `GET /api/machines` sans jeton doit répondre `401`.
3. `POST /api/auth/login` avec un mot de passe erroné doit répondre `401`.
4. Connecte-toi via `POST /api/auth/login` avec un compte technicien ; copie `access_token`, clique sur **Authorize** et saisis le jeton. `GET /api/machines` doit répondre `200`.
5. Avec le jeton Direction, `POST /api/alerts/{id}/acknowledge` doit répondre `403`.
6. Une requête d’ingestion `POST /api/telemetry/{machine_id}` sans jeton doit répondre `401`; le rôle Responsable est requis.

### T3 — US-18/49 ESP32 et acquisition réelle

1. Lance `/main.py` dans Thonny avec un DHT22 et HW-072 raccordés sur GPIO27 et GPIO16.
2. Attendu : Wi-Fi connecté, compteur `seq` croissant et message JSON publié toutes les cinq secondes.
3. Température/humidité doivent évoluer selon la pièce. Tapote doucement le banc et vérifie que les événements HW-072 changent après réglage de son potentiomètre.
4. Vérifie que `current_source` vaut `simulated` et `current_rms` vaut `0.0` tant que l’ACS712 n’est pas validé.

Le HW-072 est une sortie numérique ; son taux dépend du réglage et n’est pas une mesure d’accélération étalonnée.

### T4 — US-19 Message stocké dans PostgreSQL

Après avoir vu plusieurs messages `Publié` dans Thonny, exécute :

```powershell
docker compose exec postgres psql -U predimaint -d predimaint -c "SELECT machine_id, seq, temperature, humidity, vibration_rate, current_rms, current_source, recorded_at FROM measurements ORDER BY recorded_at DESC LIMIT 10;"
```

Adapte `-U`/`-d` si tu as choisi d’autres valeurs dans `.env`. Attendu : nouvelles lignes, machine `demo-machine`, séquences provenant du firmware et dates serveur récentes.

### T5 — US-20 Alerte et retour sous seuil

La méthode la plus sûre est de simuler des lectures par l’API, sans chauffer la machine :

1. Dans l’interface, connecte-toi comme Responsable. Dans **Seuils d’alerte**, choisis Température et règle avertissement `60`, critique `75` (valeurs de démonstration par défaut).
2. Ouvre `http://localhost:8001/docs`, autorise-toi avec le jeton du Responsable, puis utilise `POST /api/telemetry/{machine_id}` pour `demo-machine` avec ce JSON :

   ```json
   {"seq": 9001, "temperature": 66, "humidity": 55, "vibration_rate": 0, "vibration_edges": 0, "current_rms": 0, "current_source": "simulated"}
   ```

   La réponse attendue est `202`; une alerte **warning** apparaît dans le tableau de bord.
3. Recommence avec `seq: 9002` et `temperature: 80`. L’alerte active existante doit passer à **critical**, sans créer une nouvelle alerte par mesure.
4. Recommence avec `seq: 9003` et `temperature: 50`. L’alerte doit se clôturer automatiquement; elle reste visible dans l’historique des alertes.
5. Si tu as modifié les seuils pour ce test, remets les valeurs adaptées à ton banc avant de connecter une machine réelle.

### T6 — US-23 Déclarer une machine et ses capteurs

Connecte-toi comme Responsable et va à **Machines et capteurs**.

1. Crée la machine `pompe-test` avec nom et description ; elle doit apparaître dans le parc et démarrer hors ligne.
2. Déclare un capteur Température / type `DHT22` / GPIO `27` / unité `°C`; il doit apparaître dans la liste.
3. Désactive puis réactive le capteur.
4. Archive puis réactive la machine. L’historique n’est pas supprimé.
5. Connecte-toi comme Technicien : la zone d’administration n’est pas visible et la création d’une machine via l’API doit répondre `403`.

### T7 — US-41 ACL MQTT appareil/backend

1. Avec l’ESP32 et le compte appareil, publie sur `predimaint/demo-machine/telemetry`; le backend doit enregistrer la mesure.
2. Vérifie le journal broker : l’abonné backend est connecté avec le compte `predimaint_backend`; le firmware utilise le compte appareil.
3. Lance `powershell -ExecutionPolicy Bypass -File scripts/verify-mqtt-acl.ps1`. La publication par `demo-machine` doit réussir et la publication croisée par `autre-machine` doit être refusée.
4. Un client sans identifiant/mot de passe doit être refusé. Le compte appareil ne dispose que des droits de publication configurés par ACL ; le backend a un identifiant distinct.

Les échanges MQTT de ce profil local sont authentifiés et filtrés par ACL mais ne sont pas chiffrés par TLS. Reste sur un réseau local de confiance ; ne publie pas le broker sur Internet.

### T8 — US-47 Git et préparation Trello

Dans le dépôt local :

```powershell
git status --short
git check-ignore .env .env.trash firmware/config.json mosquitto/passwd
```

Attendu : les fichiers de configuration locale et le fichier de mots de passe Mosquitto sont ignorés. Les changements code/docs sont suivis. Le dépôt local est initialisé; avant le premier commit, vérifie `git status`, puis fais `git add .` et `git commit -m "Release 1 PrediMaint"`. Avant un dépôt distant, configure le remote de l’équipe et n’ajoute jamais `.env`, `mosquitto/passwd`, clés, mots de passe ou captures contenant des secrets.

Le board à créer dans Trello est préparé dans [`docs/releases/release-1/trello-board.md`](docs/releases/release-1/trello-board.md) avec les 9 cartes, leurs critères d’acceptation et les listes proposées. Crée un board `PrediMaint — Release 1`, puis reporte les cartes dans Trello et relie le dépôt Git. Aucun board externe n’est créé automatiquement par le code local.

### T9 — Tests automatisés de régression

Avec Docker démarré :

```powershell
docker compose run --build --rm backend pytest -q
```

Attendu : tests verts sur règles de seuil, authentification, permissions, persistance, machines/capteurs et transitions d’alerte. Les tests remplacent PostgreSQL et MQTT par une base SQLite en mémoire et ne publient pas de données sur le broker réel.

## Contrat MQTT

Topic mesure : `predimaint/{machine_id}/telemetry`; état retained : `predimaint/{machine_id}/status` (`online`/`offline`). Exemple :

```json
{
  "seq": 25,
  "temperature": 24.1,
  "humidity": 58.2,
  "vibration_rate": 0.0,
  "vibration_edges": 0,
  "current_rms": 0.0,
  "current_source": "simulated"
}
```

Le firmware publie QoS 1. Le backend valide les plages, refuse une machine non déclarée ou archivée, écrit la mesure et évalue les seuils activés.

## Limites connues à la fin du Release 1

- Le courant est simulé jusqu’à validation électrique, calibration de l’ACS712 et test avec une charge basse tension protégée.
- Le HW-072 ne donne pas de vitesse/accélération calibrée ; la mesure est un nombre d’événements numériques avec filtrage anti-rebond.
- Les règles sont des seuils simples, sans analyse prédictive statistique/ML ni hystérésis configurable.
- MQTT local utilise un mot de passe et des ACL mais pas TLS ; une configuration TLS adaptée au nom/IP du réseau est requise avant tout réseau non fiable.
- Gestion des comptes (création, désactivation, réinitialisation mot de passe) et board Trello distant non automatisés dans ce release.
- Schéma PostgreSQL créé au démarrage ; une migration additive est appliquée à la table machines pour la base persistante existante.

