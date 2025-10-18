import os
import smtplib
from typing import Optional
from email.message import EmailMessage


def _get_bool_env(name: str, default: bool = False) -> bool:
    val = os.environ.get(name)
    if val is None:
        return bool(default)
    return val.strip().lower() in ('1', 'true', 'yes', 'on')


def _load_smtp_config():
    host = os.environ.get('SMTP_HOST')
    port_raw = os.environ.get('SMTP_PORT')
    user = os.environ.get('SMTP_USER')
    password = os.environ.get('SMTP_PASSWORD')
    use_ssl = _get_bool_env('SMTP_USE_SSL', False)
    use_tls = _get_bool_env('SMTP_USE_TLS', True)
    sender = os.environ.get('SMTP_FROM') or user
    timeout_raw = os.environ.get('SMTP_TIMEOUT', '10')

    if not host:
        raise ValueError('Configuration SMTP manquante: SMTP_HOST')
    try:
        port = int(port_raw or (465 if use_ssl else 587))
    except Exception:
        port = 465 if use_ssl else 587
    try:
        timeout = float(timeout_raw)
    except Exception:
        timeout = 10.0

    return {
        'host': host,
        'port': port,
        'user': user,
        'password': password,
        'use_ssl': use_ssl,
        'use_tls': use_tls,
        'sender': sender,
        'timeout': timeout,
    }


def _build_test_message(sender: str, to_email: str, username: Optional[str] = None) -> EmailMessage:
    subject = 'Email de test - SansCoeurCDX'
    lines = [
        'Bonjour,',
        '',
        "Ceci est un email de test envoyé depuis l'application SansCoeurCDX.",
    ]
    if username:
        lines.append(f"Utilisateur: {username}")
    lines.extend([
        '',
        'Si vous recevez ce message, la configuration SMTP est fonctionnelle.',
    ])
    msg = EmailMessage()
    msg['From'] = sender
    msg['To'] = to_email
    msg['Subject'] = subject
    msg.set_content('\n'.join(lines))
    return msg


def send_test_email(to_email: str, username: Optional[str] = None):
    if not to_email:
        raise ValueError("Adresse email du destinataire manquante")

    cfg = _load_smtp_config()
    msg = _build_test_message(cfg['sender'] or cfg['user'], to_email, username=username)

    if cfg['use_ssl']:
        with smtplib.SMTP_SSL(cfg['host'], cfg['port'], timeout=cfg['timeout']) as server:
            if cfg['user'] and cfg['password']:
                server.login(cfg['user'], cfg['password'])
            server.send_message(msg)
            return True
    else:
        with smtplib.SMTP(cfg['host'], cfg['port'], timeout=cfg['timeout']) as server:
            server.ehlo()
            if cfg['use_tls']:
                server.starttls()
                server.ehlo()
            if cfg['user'] and cfg['password']:
                server.login(cfg['user'], cfg['password'])
            server.send_message(msg)
            return True


def send_email(to_email: str, subject: str, body_text: str):
    """Send a plain-text email using SMTP config from environment."""
    if not to_email:
        raise ValueError("Adresse email du destinataire manquante")
    cfg = _load_smtp_config()
    sender = cfg['sender'] or cfg['user']
    if not sender:
        raise ValueError("Adresse d'expédition introuvable (SMTP_FROM ou SMTP_USER)")
    msg = EmailMessage()
    msg['From'] = sender
    msg['To'] = to_email
    msg['Subject'] = subject
    msg.set_content(body_text)

    if cfg['use_ssl']:
        with smtplib.SMTP_SSL(cfg['host'], cfg['port'], timeout=cfg['timeout']) as server:
            if cfg['user'] and cfg['password']:
                server.login(cfg['user'], cfg['password'])
            server.send_message(msg)
            return True
    else:
        with smtplib.SMTP(cfg['host'], cfg['port'], timeout=cfg['timeout']) as server:
            server.ehlo()
            if cfg['use_tls']:
                server.starttls()
                server.ehlo()
            if cfg['user'] and cfg['password']:
                server.login(cfg['user'], cfg['password'])
            server.send_message(msg)
            return True


def send_registration_email(to_email: str, username: Optional[str] = None):
    subject = 'Création de votre compte SansCoeurCDX'
    lines = [
        'Bonjour' + (f' {username}' if username else '') + ',',
        '',
        'Votre compte a bien été créé sur SansCoeurCDX.',
        "Il doit maintenant être validé par un administrateur avant de pouvoir vous connecter.",
        '',
        'Merci et à bientôt !',
    ]
    return send_email(to_email, subject, '\n'.join(lines))


def send_account_activated_email(to_email: str, username: Optional[str] = None):
    subject = 'Votre compte SansCoeurCDX est activé'
    lines = [
        'Bonjour' + (f' {username}' if username else '') + ',',
        '',
        'Bonne nouvelle ! Votre compte a été activé par un administrateur.',
        'Vous pouvez maintenant vous connecter à l\'application.',
        '',
        'Bon jeu !',
    ]
    return send_email(to_email, subject, '\n'.join(lines))


def send_email_update_confirmation(to_email: str, username: Optional[str] = None, old_email: Optional[str] = None):
    subject = 'Confirmation de modification de votre adresse email'
    lines = [
        'Bonjour' + (f' {username}' if username else '') + ',',
        '',
        "Nous confirmons la modification de l'adresse email associée à votre compte SansCoeurCDX.",
    ]
    if old_email:
        lines.append(f'Ancienne adresse: {old_email}')
    lines.append(f'Nouvelle adresse: {to_email}')
    lines.extend([
        '',
        'Si vous n\'êtes pas à l\'origine de ce changement, veuillez contacter un administrateur au plus vite.',
    ])
    return send_email(to_email, subject, '\n'.join(lines))


def send_password_reset_email(to_email: str, username: Optional[str], reset_url: str):
    subject = 'Réinitialisation de votre mot de passe'
    lines = [
        'Bonjour' + (f' {username}' if username else '') + ',',
        '',
        'Nous avons reçu une demande de réinitialisation de votre mot de passe.',
        'Pour définir un nouveau mot de passe, cliquez sur le lien suivant:',
        reset_url,
        '',
        'Si vous n’êtes pas à l’origine de cette demande, vous pouvez ignorer cet email.',
    ]
    return send_email(to_email, subject, '\n'.join(lines))
