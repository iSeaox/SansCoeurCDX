"""Calculation and ranking of duos (pairs of players) according to a weighted formula.

Formulas (based on the provided document):

- note_alpha = (pt_fait / pt_total) ** alpha
- weight_i = exp(lambda * i) with i=0 for the duo's most recent match
- confidence_factor_k(n) = 1 - exp(-k * n)
- duo_score = (sum(note_alpha(i) * weight_i) / sum(weight_i)) * confidence_factor
- displayed_score = A + B * ln(duo_score)

Convention used here:
- A "match" = a row in the games table with state = 'terminee'.
- For a given duo (two players who played together on the same team), we compute
    one score per match: note = duo_team_points / (points_team_a + points_team_b)
- We order the duo's matches by updated_at descending (most recent first).

Returns a ranking sorted from best to worst according to duo_score.
"""
from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass
from math import exp, log
from typing import Dict, List, Tuple


@dataclass
class DuoEntry:
    user1_id: int
    user1_name: str
    user2_id: int
    user2_name: str
    # Liste des tuples (updated_at_iso, note_brute)
    notes: List[Tuple[str, float]]


def _fetch_duo_game_notes(db) -> List[DuoEntry]:
    """Récupère pour chaque partie terminée les duos (paires sur la même équipe)
    et la note brute pt_fait/pt_total pour cette partie.

    Retourne une liste où chaque élément correspond à un duo au sein d'une partie unique
    (les entrées du même duo sur des parties différentes seront agrégées plus tard).
    """
    entries: List[DuoEntry] = []
    with closing(db.cursor()) as cur:
        # On prend chaque paire (u1,u2) sur la même équipe dans une partie finie
        # On attache les points de l'équipe de la paire et la date de mise à jour de la partie
        cur.execute(
            """
            SELECT 
                g.updated_at,
                CASE WHEN gp1.team = 'A' THEN g.points_team_a ELSE g.points_team_b END AS team_points,
                (g.points_team_a + g.points_team_b) AS total_points,
                u1.id, u1.username,
                u2.id, u2.username
            FROM games g
            JOIN game_players gp1 ON gp1.game_id = g.id
            JOIN game_players gp2 ON gp2.game_id = g.id AND gp2.team = gp1.team AND gp2.user_id > gp1.user_id
            JOIN users u1 ON u1.id = gp1.user_id
            JOIN users u2 ON u2.id = gp2.user_id
            WHERE g.state = 'terminee'
            """
        )
        for updated_at, team_points, total_points, u1_id, u1_name, u2_id, u2_name in cur.fetchall():
            if not total_points or total_points <= 0:
                continue
            # Mise à l'échelle sur [0,2] pour avoir ~1 en neutre (50/50), >1 victoire, <1 défaite
            note = 2.0 * float(team_points) / float(total_points)
            entries.append(
                DuoEntry(
                    user1_id=u1_id,
                    user1_name=u1_name,
                    user2_id=u2_id,
                    user2_name=u2_name,
                    notes=[(updated_at, note)],
                )
            )
    return entries


def _group_duo_entries(entries: List[DuoEntry]) -> Dict[Tuple[int, int], Dict]:
    """Agrège les entrées par duo (user_id triés) et accumule la liste des notes (date, note)."""
    grouped: Dict[Tuple[int, int], Dict] = {}
    for e in entries:
        key = (min(e.user1_id, e.user2_id), max(e.user1_id, e.user2_id))
        if key not in grouped:
            grouped[key] = {
                'user_ids': key,
                'user_names': (e.user1_name, e.user2_name) if e.user1_id <= e.user2_id else (e.user2_name, e.user1_name),
                'notes': []  # list of (updated_at_iso, note)
            }
        grouped[key]['notes'].extend(e.notes)
    # Trie des notes par date décroissante (plus récent d'abord)
    for v in grouped.values():
        v['notes'].sort(key=lambda t: t[0] or '', reverse=True)
    return grouped


def _compute_weighted_score(notes: List[Tuple[str, float]], *, alpha: float, lambda_: float, k: float) -> float:
    """Calcule le score_duo au sens de la formule.

    notes: liste triée du plus récent (i=0) au plus ancien (i=n-1),
           chaque élément est (updated_at_iso, note_brute in [0,1..])
    """
    n = len(notes)
    if n == 0:
        return 0.0

    num = 0.0
    den = 0.0
    for i, (_date, note) in enumerate(notes):
        # Transformation de valorisation
        note_alpha = (note ** alpha) if note > 0 else 0.0
        # Poids temporel
        w = exp(lambda_ * i)
        num += note_alpha * w
        den += w

    base = (num / den) if den > 0 else 0.0
    confiance = 1.0 - exp(-k * n)
    return base * confiance


def get_duo_rankings(
    db,
    *,
    alpha: float = 2.0,
    lambda_: float = -0.2,
    k: float = 0.3,
    A: float = 100.0,
    B: float = 100.0,
    min_games: int = 1,
    limit: int = 50,
) -> List[Dict]:
    """Construit le classement des duos.

    Retourne une liste de dictionnaires triés par score décroissant:
    {
      'duo_name': 'Alice & Bob',
      'user_ids': (1, 2),
      'games_played': n,
      'score_raw': score_duo,               # [0, +inf) typiquement ~ [0.6, 1.4]
      'note_display': A + B * ln(score_duo) # si score_duo>0
    }
    """
    # 1) Récup toutes les notes par duo/partie
    entries = _fetch_duo_game_notes(db)
    # 2) regrouper par duo
    grouped = _group_duo_entries(entries)

    results: List[Dict] = []
    for (_u1, _u2), data in grouped.items():
        notes = data['notes']
        n = len(notes)
        if n < min_games:
            continue
        score = _compute_weighted_score(notes, alpha=alpha, lambda_=lambda_, k=k)
        if score <= 0:
            note_aff = None
        else:
            note_aff = A + B * log(score)
        u1_name, u2_name = data['user_names']
        duo_name = f"{u1_name} & {u2_name}"
        results.append({
            'duo_name': duo_name,
            'user_ids': data['user_ids'],
            'games_played': n,
            'score_raw': round(score, 3),
            'note_display': round(note_aff, 2) if note_aff is not None else None,
        })

    # 3) tri par score décroissant puis par n décroissant
    results.sort(key=lambda d: (d['score_raw'], d['games_played']), reverse=True)
    if limit and limit > 0:
        results = results[:limit]
    return results
