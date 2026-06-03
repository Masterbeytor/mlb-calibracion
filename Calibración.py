import csv
import requests
from datetime import date, timedelta
from tqdm import tqdm   # ← BARRA DE PROGRESO

from MLBfinalporahora import (
    obtener_juegos_del_dia,
    calcular_probabilidades_jugador,
)

BASE_URL = "https://statsapi.mlb.com/api/v1"


def obtener_boxscore(game_pk):
    url = f"{BASE_URL}/game/{game_pk}/boxscore"
    r = requests.get(url)
    r.raise_for_status()
    return r.json()


def extraer_lineups_y_pitchers(box):
    players = box.get("players", {})
    teams = box.get("teams", {})

    lineups = {"home": [], "away": []}
    pitchers = {"home": None, "away": None}

    for side in ["home", "away"]:
        t = teams.get(side, {})
        t_players = t.get("players", {})

        # Lineup
        for pid, pdata in t_players.items():
            bo = pdata.get("battingOrder")
            if not bo:
                continue

            orden = int(bo) // 100
            if not (1 <= orden <= 9):
                continue

            p_id = pdata["person"]["id"]
            p_info = players.get(f"ID{p_id}", {})

            lineups[side].append({
                "orden": orden,
                "name": pdata["person"]["fullName"],
                "id": p_id,
                "pos": pdata.get("position", {}).get("abbreviation", ""),
                "batSide": p_info.get("batSide", {}).get("code", "R")
            })

        lineups[side] = sorted(lineups[side], key=lambda x: x["orden"])

        # Pitcher abridor
        pitchers_ids = t.get("pitchers", [])
        if pitchers_ids:
            pid = pitchers_ids[0]
            p_info = players.get(f"ID{pid}", {})
            pitchers[side] = {
                "id": pid,
                "fullName": p_info.get("fullName", "Unknown"),
                "hand": p_info.get("pitchHand", {}).get("code", "R")
            }

    return lineups, pitchers


def extraer_hits_reales(box):
    """Devuelve dict: hits_reales[player_id] = (hits, HR)"""
    out = {}
    players = box.get("players", {})

    for pid, pdata in players.items():
        stat = pdata.get("stats", {}).get("batting", {})
        hits = int(stat.get("hits", 0))
        hr = int(stat.get("homeRuns", 0))
        real_id = pdata.get("person", {}).get("id")
        if real_id:
            out[real_id] = (hits, hr)

    return out


def correr_calibracion(desde, hasta, archivo_salida="calibracion.csv"):
    with open(archivo_salida, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "fecha", "jugador", "equipo", "rival",
            "p_hit", "hit_real",
            "p_hr", "hr_real",
            "pitcher_rival", "park_factor"
        ])

        fecha = desde
        while fecha <= hasta:
            print(f"\n📅 Procesando fecha: {fecha}")

            juegos = obtener_juegos_del_dia(fecha)
            print(f"  Juegos: {len(juegos)}")

            # BARRA DE PROGRESO POR JUEGOS
            for juego in tqdm(juegos, desc=f"{fecha} — Juegos", ncols=80):

                try:
                    box = obtener_boxscore(juego["gamePk"])
                except:
                    continue

                lineups, pitchers = extraer_lineups_y_pitchers(box)
                hits_reales = extraer_hits_reales(box)

                # BARRA DE PROGRESO POR JUGADORES
                for side in ["away", "home"]:
                    lineup = lineups.get(side)
                    if not lineup:
                        continue

                    rival = "home" if side == "away" else "away"
                    pitcher_rival = pitchers.get(rival)
                    if not pitcher_rival:
                        continue

                    for jugador in tqdm(lineup, desc=f"{juego['away']}@{juego['home']} — {side}", leave=False, ncols=80):

                        p_hit, p_hr = calcular_probabilidades_jugador(
                            jugador, pitcher_rival, juego
                        )
                        if p_hit is None or p_hr is None:
                            continue

                        hit_real, hr_real = hits_reales.get(jugador["id"], (0, 0))

                        writer.writerow([
                            fecha.strftime("%Y-%m-%d"),
                            jugador["name"],
                            juego[side],
                            juego[rival],
                            round(p_hit, 6),
                            hit_real,
                            round(p_hr, 6),
                            hr_real,
                            pitcher_rival["fullName"],
                            juego.get("park_factor", 100)
                        ])
                      
