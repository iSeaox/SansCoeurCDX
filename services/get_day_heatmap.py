from datetime import datetime, timedelta
import calendar
from db import games as games_repo

def get_day_heatmap(db):
    now = datetime.now()
    year = now.year
    month = now.month
    days_in_month = calendar.monthrange(year, month)[1]
    month_name = now.strftime('%B')

    weekdays = ['Lun', 'Mar', 'Mer', 'Jeu', 'Ven', 'Sam', 'Dim']

    first_day = datetime(year, month, 1)
    dates = []
    for day in range(1, days_in_month + 1):
        date = datetime(year, month, day)
        weekday = (date.weekday())

        week_number = ((date - first_day).days + first_day.weekday()) // 7
        dates.append({
            'day': day,
            'weekday': weekday,
            'week_number': week_number
        })

    games_by_day = games_repo.get_games_count_by_day(db, year, month)

    max_week = max(d['week_number'] for d in dates) + 1
    z = [[None for _ in range(7)] for _ in range(max_week)]
    text = [['' for _ in range(7)] for _ in range(max_week)]

    for d in dates:
        value = games_by_day.get(d['day'], 0)
        z[d['week_number']][d['weekday']] = value
        
        if value == 0:
            game_text = "Aucune partie"
        elif value == 1:
            game_text = "1 partie"
        else:
            game_text = f"{value} parties"
            
        text[d['week_number']][d['weekday']] = f"{str(d['day']).zfill(2)} {month_name} : {game_text}"

    heatmap_data = {
        'x': weekdays,
        'y': [f"Semaine {i + 1}" for i in range(max_week)],
        'z': z,
        'text': text,
        'title': f"Activité du mois - {month_name} {year}"
    }
    return heatmap_data