# Coinche Tracker (Flask)

Petit projet Flask pour enregistrer des parties de coinche.

## Lancer en local

1. Créer un environnement virtuel (optionnel mais recommandé)
2. Installer les dépendances
3. Initialiser la base SQLite
4. Configurer l'environnement via `.env` (optionnel)
5. Démarrer l'app

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

export FLASK_APP=app.py
flask --app app.py init-db

# Optionnel: variables via .env (voir .env.example)
# cp .env.example .env && editez les valeurs

flask --app app.py run --debug

## Gestion des utilisateurs

Pas de page d'inscription pour l'instant. Créez des utilisateurs via la CLI:

```bash
flask --app app.py create-user --username monlogin
# un prompt demandera le mot de passe (confirmé). Longueur minimale: 8
```

La connexion utilise désormais la base: les mots de passe sont stockés hachés (PBKDF2-SHA256). Le login est insensible à la casse. Le cookie de session est durci (HttpOnly, SameSite=Lax, Secure en prod) et la session est vidée au login/logout.
```

Puis ouvrir http://127.0.0.1:5000

## Structure

- `app.py` — application Flask, routes, DB SQLite
- `templates/` — templates Jinja2 avec Bootstrap
- `static/` — fichiers statiques (CSS)

