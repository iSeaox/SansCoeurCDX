# SansCoeurCDX - Application de gestion de parties de Coinche

Application Flask pour enregistrer et suivre des parties de coinche (dérivé de la belote).

## Fonctionnalités

- **Authentification** : connexion sécurisée avec comptes utilisateurs
- **Gestion des parties** : création, suivi et historique des parties
- **Enregistrement des manches** : détail complet de chaque manche (contrat, atout, scores, belotes, etc.)
- **Administration** : gestion des utilisateurs par les administrateurs
- **Graphiques** : visualisation de la progression des scores avec Chart.js
- **Interface responsive** : utilise Bootstrap pour l'affichage

## Installation

### Prérequis
- Python 3.8+
- pip

### Configuration

1. **Cloner et configurer l'environnement :**
```bash
git clone <votre-repo>
cd SansCoeurCDX
python3 -m venv .venv
source .venv/bin/activate  # Linux/Mac
# ou .venv\Scripts\activate sur Windows
pip install -r requirements.txt
```

2. **Configuration des variables d'environnement :**
```bash
cp .env.example .env
```

Puis éditer le fichier `.env` :
```env
SECRET_KEY=votre-cle-secrete-longue-et-aleatoire
DATABASE=data/coinche.db
HOST=0.0.0.0
PORT=5000
DEBUG=true
# Paramètres Classement des Duos (optionnels)
# DUO_RANKING_ALPHA=1.3
# DUO_RANKING_LAMBDA=-0.2
# DUO_RANKING_K=0.3
# DUO_RANKING_A=100
# DUO_RANKING_B=100
# DUO_RANKING_MIN_GAMES=1
# DUO_RANKING_LIMIT=50
# DUO_RANKING_SHOW_RAW=true
```

3. **Initialiser la base de données :**
```bash
flask --app app.py init-db
```

## Gestion des utilisateurs

### Création du premier administrateur

Après l'installation, créez votre premier utilisateur administrateur :

```bash
flask --app app.py create-user --admin
```

Le système vous demandera :
- Nom d'utilisateur
- Mot de passe (minimum 8 caractères, confirmé)

### Création d'utilisateurs normaux

```bash
flask --app app.py create-user
```

### Administration via l'interface web

Une fois connecté en tant qu'administrateur :

1. **Accès au panel d'administration :**
   - Le lien "Administration" apparaît dans la barre de navigation
   - Accès direct via `/admin`

2. **Gestion des utilisateurs :**
   - Liste de tous les utilisateurs avec leur statut (actif/inactif)
   - Boutons pour activer/désactiver les comptes
   - Un administrateur ne peut pas modifier son propre statut

3. **Validation des nouveaux comptes :**
   - Les nouveaux utilisateurs sont créés actifs par défaut via CLI
   - Les administrateurs peuvent désactiver des comptes si nécessaire

## Démarrage de l'application

```bash
flask --app app.py run
```

Ou directement :
```bash
python app.py
```

L'application sera accessible sur `http://localhost:5000` (ou selon votre configuration dans `.env`).

## Utilisation

### Première connexion

1. Créez un utilisateur administrateur avec la CLI
2. Créez au moins 4 utilisateurs pour pouvoir créer une partie
3. Connectez-vous sur l'interface web
4. Créez votre première partie dans "Parties" > "Nouvelle partie"

### Gestion des parties

- **Création** : sélectionnez 4 joueurs distincts et définissez l'objectif de points
- **Ajout de manches** : seuls les participants peuvent ajouter des manches
- **Suivi** : graphique de progression des scores, détail de chaque manche
- **Edition** : modification/suppression des manches par les participants

### Règles de validation

- **Belotes** :
  - Sans atout : aucune belote autorisée
  - Tout atout : maximum 4 belotes au total (équipes A+B)
  - Atout couleur : maximum 1 belote au total
- **Contrats** : 80 à 180 (par pas de 10) ou "Générale"
- **Scores** : complément automatique à 162 points
- **Capot** : détecté automatiquement (162-0)

## Architecture technique

### Structure du projet
```
SansCoeurCDX/
├── app.py              # Application Flask principale
├── db/                 # Couche d'accès aux données
│   ├── core.py         # Connexion base de données
│   ├── schema.py       # Schéma et migrations
│   ├── users.py        # Repository utilisateurs
│   ├── games.py        # Repository parties
│   └── hands.py        # Repository manches
├── services/           # Logique métier
│   ├── scores.py       # Calcul des scores de manche
│   ├── statistics.py   # Statistiques agrégées
│   └── duo_ranking.py  # Classement des duos (paramétrable via env)
├── templates/          # Templates Jinja2
├── static/            # Ressources statiques
│   ├── css/
│   └── js/
└── requirements.txt
```

### Paramétrage du Classement des Duos

Le classement des duos utilise une formule pondérée configurable via variables d'environnement:

- DUO_RANKING_ALPHA (défaut 1.3): valorise les bonnes notes (>1 accentue les victoires)
- DUO_RANKING_LAMBDA (défaut -0.2): décroissance temporelle (négatif = parties anciennes pèsent moins)
- DUO_RANKING_K (défaut 0.3): facteur de confiance selon le nombre de parties du duo
- DUO_RANKING_A, DUO_RANKING_B (défaut 100, 100): transforme le score brut en note lisible via ln(score)
- DUO_RANKING_MIN_GAMES (défaut 1): nombre minimum de parties pour afficher un duo
- DUO_RANKING_LIMIT (défaut 50): nombre maximum de duos affichés
 - DUO_RANKING_LIMIT (défaut 50): nombre maximum de duos affichés
 - DUO_RANKING_SHOW_RAW (défaut true): afficher ou masquer le score brut à droite de la note

Ces paramètres sont lus dans `app.py` et passés à `services.duo_ranking.get_duo_rankings`.

### Base de données

- **SQLite** avec schéma normalisé
- **Tables principales** : users, games, game_players, hands
- **Migrations automatiques** lors de l'initialisation
- **Contraintes** : clés étrangères, validation des données

### Sécurité

- **Sessions** : cookies sécurisés (HttpOnly, SameSite, durée limitée)
- **Mots de passe** : hachage PBKDF2-SHA256
- **Autorisation** : contrôle d'accès par rôles (admin/utilisateur)
- **Validation** : vérification des permissions pour chaque action

## Commandes CLI disponibles

```bash
# Initialiser/réinitialiser la base de données
flask --app app.py init-db

# Créer un utilisateur normal
flask --app app.py create-user

# Créer un administrateur
flask --app app.py create-user --admin

# Lancer l'application en mode développement
flask --app app.py run --debug

