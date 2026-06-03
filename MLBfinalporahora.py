import requests
import re
from datetime import datetime, date, timezone, timedelta

# ==========================================
# CONFIG
# ==========================================
BASE_URL = "https://statsapi.mlb.com/api/v1"
LIVE_URL = "https://statsapi.mlb.com/api/v1.1/game/{gamePk}/feed/live"
VZLA_TZ = timezone(timedelta(hours=-4))

PA_POR_JUEGO = 4.2
PA_POR_ORDEN = {1: 4.75, 2: 4.65, 3: 4.55, 4: 4.45, 5: 4.35, 6: 4.25, 7: 4.10, 8: 3.95, 9: 3.80}

PADDING_BATEADOR = 60
PADDING_PITCHER = 150

XBA_LIGA_PA_FALLBACK = 0.225 
WIDTH = 75 

# WEATHER FACTOR (versión Script 2)
TEMP_BASE = 72
COEF_TEMP = 0.003
COEF_VIENTO = 0.004

# MÓDULO ISO/HR (del Script 3)
ISO_REF = 0.150
ISO_MIN = 0.85
ISO_MAX = 1.20

ESTADIOS = {
    "Arizona Diamondbacks": {"nombre": "Chase Field", "pf": 104},
    "Atlanta Braves": {"nombre": "Truist Park", "pf": 100},
    "Baltimore Orioles": {"nombre": "Oriole Park", "pf": 103},
    "Boston Red Sox": {"nombre": "Fenway Park", "pf": 102},
    "Chicago Cubs": {"nombre": "Wrigley Field", "pf": 95},
    "Chicago White Sox": {"nombre": "Rate Field", "pf": 99},
    "Cincinnati Reds": {"nombre": "Great American", "pf": 103},
    "Cleveland Guardians": {"nombre": "Progressive Field", "pf": 98},
    "Colorado Rockies": {"nombre": "Coors Field", "pf": 112},
    "Detroit Tigers": {"nombre": "Comerica Park", "pf": 101},
    "Houston Astros": {"nombre": "Daikin Park", "pf": 101},
    "Kansas City Royals": {"nombre": "Kauffman Stadium", "pf": 100},
    "Los Angeles Angels": {"nombre": "Angel Stadium", "pf": 100},
    "Los Angeles Dodgers": {"nombre": "Dodger Stadium", "pf": 102},
    "Miami Marlins": {"nombre": "loanDepot park", "pf": 100},
    "Milwaukee Brewers": {"nombre": "AmFam Field", "pf": 97},
    "Minnesota Twins": {"nombre": "Target Field", "pf": 103},
    "New York Mets": {"nombre": "Citi Field", "pf": 99},
    "New York Yankees": {"nombre": "Yankee Stadium", "pf": 102},
    "Oakland Athletics": {"nombre": "Sutter Health", "pf": 109},
    "Philadelphia Phillies": {"nombre": "Citizens Bank", "pf": 102},
    "Pittsburgh Pirates": {"nombre": "PNC Park", "pf": 100},
    "San Diego Padres": {"nombre": "Petco Park", "pf": 97},
    "San Francisco Giants": {"nombre": "Oracle Park", "pf": 98},
    "Seattle Mariners": {"nombre": "T-Mobile Park", "pf": 92},
    "St. Louis Cardinals": {"nombre": "Busch Stadium", "pf": 98},
    "Tampa Bay Rays": {"nombre": "Tropicana Field", "pf": 95},
    "Texas Rangers": {"nombre": "Globe Life Field", "pf": 92},
    "Toronto Blue Jays": {"nombre": "Rogers Centre", "pf": 101},
    "Washington Nationals": {"nombre": "Nationals Park", "pf": 101}
}
def evaluar_estadio(pf):
    if pf > 102: return "🔥 Hit Friendly"
    elif pf < 98: return "🧊 Pit Friendly"
    return "⚖️ Neutral"

def get_json(url, params=None):
    r = requests.get(url, params=params)
    r.raise_for_status()
    return r.json()

def convertir_utc_a_venezuela(iso_str):
    dt_utc = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
    return dt_utc.astimezone(VZLA_TZ)

# WEATHER FACTOR (versión Script 2)
def calcular_weather_factor(clima):
    condicion = clima.get("condition", "").lower()
    wind_str = clima.get("wind", "").lower()
    
    try:
        temp = float(clima.get("temp", TEMP_BASE))
    except ValueError:
        temp = float(TEMP_BASE)
        
    if "closed" in condicion or "dome" in condicion:
        return 1.00, "Techo Cerrado / Dome"
        
    delta_t = temp - TEMP_BASE
    impacto_temp = delta_t * COEF_TEMP
    
    velocidad_viento = 0
    match = re.search(r'(\d+)\s*mph', wind_str)
    if match:
        velocidad_viento = float(match.group(1))
        
    impacto_viento = 0.0
    if "out" in wind_str:
        impacto_viento = velocidad_viento * COEF_VIENTO
    elif "in" in wind_str:
        impacto_viento = -velocidad_viento * COEF_VIENTO
        
    wf = 1.0 + impacto_temp + impacto_viento
    wf = max(0.85, min(wf, 1.15))
    
    desc_str = f"🌡️ {int(temp)}°F | 🌬️ {clima.get('wind', 'N/A')}"
    return wf, desc_str
# ==========================================
# MODULE: MLB_DATA_FETCHER
# ==========================================

def obtener_juegos_del_dia(fecha):
    data = get_json(
        f"{BASE_URL}/schedule",
        {"sportId": 1, "date": fecha.strftime("%Y-%m-%d")}
    )
    juegos = []
    for game in data.get("dates", [{}])[0].get("games", []):
        dt_vzla = convertir_utc_a_venezuela(game["gameDate"])
        home_name = game["teams"]["home"]["team"]["name"]
        pf = ESTADIOS.get(home_name, {}).get("pf", 100)

        juegos.append({
            "gamePk": game["gamePk"],
            "home": home_name,
            "away": game["teams"]["away"]["team"]["name"],
            "home_id": game["teams"]["home"]["team"]["id"],
            "away_id": game["teams"]["away"]["team"]["id"],
            "hora_vzla": dt_vzla.strftime("%H:%M"),
            "park_factor": pf
        })
    return juegos


def obtener_live_game(game_pk):
    return get_json(LIVE_URL.format(gamePk=game_pk))


def extraer_clima(live_data):
    weather = live_data.get("gameData", {}).get("weather", {})
    return {
        "condition": weather.get("condition", "Unknown"),
        "temp": weather.get("temp", TEMP_BASE),
        "wind": weather.get("wind", "0 mph, Calm")
    }


def extraer_probable_pitchers(live_data):
    prob = live_data.get("gameData", {}).get("probablePitchers", {})
    players_data = live_data.get("gameData", {}).get("players", {})
    out = {}

    for side in ["home", "away"]:
        p = prob.get(side)
        if p:
            pid = p["id"]
            p_info = players_data.get(f"ID{pid}", {})
            hand = p_info.get("pitchHand", {}).get("code", "R")
            out[side] = {
                "id": pid,
                "fullName": p["fullName"],
                "hand": hand
            }
        else:
            out[side] = None

    return out


def extraer_lineup_y_batting_order(live_data):
    box = live_data.get("liveData", {}).get("boxscore", {})
    players_data = live_data.get("gameData", {}).get("players", {})
    equipos = {}

    for side in ["home", "away"]:
        players = box.get("teams", {}).get(side, {}).get("players", {})
        lineup = []

        for pid, pdata in players.items():
            bo_str = pdata.get("battingOrder")
            if not bo_str:
                continue

            orden_real = int(bo_str) // 100
            p_id_num = pdata["person"]["id"]
            bat_side = players_data.get(f"ID{p_id_num}", {}).get("batSide", {}).get("code", "R")

            lineup.append({
                "orden": orden_real,
                "name": pdata["person"]["fullName"],
                "id": p_id_num,
                "pos": pdata.get("position", {}).get("abbreviation", ""),
                "batSide": bat_side
            })

        lineup = [p for p in lineup if 1 <= p["orden"] <= 9]
        equipos[side] = sorted(lineup, key=lambda x: x["orden"])

    return equipos


def extraer_records_equipos(live_data):
    records = {}
    for side in ["away", "home"]:
        try:
            pct_str = (
                live_data.get("gameData", {})
                .get("teams", {})
                .get(side, {})
                .get("record", {})
                .get("leagueRecord", {})
                .get("pct", ".500")
            )
            records[side] = float(pct_str)
        except (KeyError, ValueError):
            records[side] = 0.500
    return records

def obtener_talento_bullpen_equipo(team_id, season):
    url = f"{BASE_URL}/teams/{team_id}/stats"
    params = {
        "season": season,
        "stats": "season",
        "group": "pitching",
        "gameType": "R"
    }
    try:
        data = get_json(url, params=params)
        splits = data.get("stats", [{}])[0].get("splits", [])
        if splits:
            stat = splits[0].get("stat", {})
            hits = int(stat.get("hits", 0))
            bf = int(stat.get("battersFaced", 0))
            if bf > 0:
                return (hits / bf) + 0.008
        return None
    except Exception:
        return None
def evaluar_racha(racha_str):
    try:
        nums = [int(x) for x in racha_str.replace('[', '').replace(']', '').split() if x.isdigit()]
        if not nums: return ""
        total_hits = sum(nums)
        if total_hits >= 7: return "🔥"
        elif total_hits <= 1 and len(nums) >= 3: return "🧊"
        return ""
    except Exception:
        return ""

def calcular_prob_hr_por_pa(tasa_hit_pa, iso, dist_hr, pf):
    if tasa_hit_pa <= 0:
        return 0.0
    
    iso_mult = max(ISO_MIN, min(ISO_MAX, iso / ISO_REF))
    pf_mult = pf / 100
    
    prob_hr_pa = tasa_hit_pa * dist_hr * iso_mult * pf_mult
    return min(prob_hr_pa, tasa_hit_pa * 0.90)

def obtener_xba_liga_pa(season):
    url = f"{BASE_URL}/teams/stats"
    params = {"season": season, "stats": "season", "group": "hitting", "sportIds": 1, "gameType": "R"}
    try:
        data = get_json(url, params=params)
        splits = data.get("stats", [{}])[0].get("splits", [])
        if not splits:
            return XBA_LIGA_PA_FALLBACK

        hits_liga = 0
        pa_liga = 0
        for team in splits:
            stat = team.get("stat", {})
            hits_liga += int(stat.get("hits", 0))
            pa_liga += int(stat.get("plateAppearances", 0))

        if pa_liga < 15000:
            return XBA_LIGA_PA_FALLBACK

        return hits_liga / pa_liga
    except Exception:
        return XBA_LIGA_PA_FALLBACK
        
def obtener_era_pitcher(player_id, season):
    url = f"{BASE_URL}/people/{player_id}/stats"
    params = {"stats": "season", "group": "pitching", "season": season}
    try:
        data = get_json(url, params=params)
        splits = data.get("stats", [{}])[0].get("splits", [])
        if splits:
            era_str = splits[0].get("stat", {}).get("era", "-.--")
            try:
                return float(era_str)
            except ValueError:
                return None
        return None
    except Exception:
        return None
        
def predecir_ganador_log5(pct_a, pct_b):
    if (pct_a == 0 and pct_b == 0) or (pct_a == 1 and pct_b == 1):
        return 0.5
    numerador = (pct_a - (pct_a * pct_b))
    denominador = (pct_a + pct_b - (2 * pct_a * pct_b))
    if denominador == 0:
        return 0.5
    return numerador / denominador
    
def obtener_talento_xba_split(player_id, season, opp_hand, xba_liga, group="hitting"):
    url = f"{BASE_URL}/people/{player_id}/stats"
    sit_code = "vl" if opp_hand == "L" else "vr" if opp_hand == "R" else None

    try:
        # 1️⃣ Obtener estadísticas globales
        data_season = get_json(url, {"stats": "season", "group": group, "season": season})
        splits = data_season.get("stats", [{}])[0].get("splits", [])
        if not splits:
            return None, 0

        stat_global = splits[0].get("stat", {})
        pa_key = "plateAppearances" if group == "hitting" else "battersFaced"
        pa_global = int(stat_global.get(pa_key, 0))
        hits_global = int(stat_global.get("hits", 0))

        if pa_global == 0:
            return None, 0

        avg_global = hits_global / pa_global

        # 2️⃣ Intentar obtener xBA global (Statcast)
        xba_global = avg_global
        try:
            data_xba = get_json(url, {"stats": "expectedStatistics", "group": group, "season": season})
            splits_xba = data_xba.get("stats", [{}])[0].get("splits", [])
            if splits_xba:
                xba_val = float(splits_xba[0].get("stat", {}).get("estimatedBa", 0))
                if xba_val > 0:
                    xba_global = xba_val
        except Exception:
            pass

        # 3️⃣ Split vs mano del rival
        xh_pa_final = xba_global
        pa_split = pa_global

        if sit_code:
            try:
                data_split = get_json(url, {"stats": "statSplits", "group": group, "season": season, "sitCodes": sit_code})
                splits_list = data_split.get("stats", [{}])[0].get("splits", [])
                if splits_list:
                    stat_split = splits_list[0].get("stat", {})
                    pa_split_val = int(stat_split.get(pa_key, 0))
                    hits_split = int(stat_split.get("hits", 0))

                    if pa_split_val > 5:
                        tasa_split = hits_split / pa_split_val
                        ratio = tasa_split / avg_global if avg_global > 0 else 1.0
                        xh_pa_final = xba_global * ratio
                        pa_split = pa_split_val
            except Exception:
                pass

        # 4️⃣ Estabilización matemática
        pad = PADDING_BATEADOR if group == "hitting" else PADDING_PITCHER
        hits_esperados = xh_pa_final * pa_split
        hits_fantasma = pad * xba_liga
        tasa_estabilizada = (hits_esperados + hits_fantasma) / (pa_split + pad)

        return tasa_estabilizada, pa_split

    except Exception:
        return None, 0
        
def log5_con_park_factor(A, B, L, PF):
    if A <= 0 or A >= 1 or B <= 0 or B >= 1 or L <= 0 or L >= 1:
        return None
    odds_A = A / (1 - A)
    odds_B = B / (1 - B)
    odds_L = L / (1 - L)

    odds_matchup_neutral = (odds_A * odds_B) / odds_L

    multiplicador_pf = ((PF - 100) / 200.0) + 1.0
    odds_matchup_pf = odds_matchup_neutral * multiplicador_pf

    return odds_matchup_pf / (1 + odds_matchup_pf)
    
def prob_hit_en_juego_con_bullpen(p_hit_abridor, p_hit_bullpen, pa_total, pa_esperadas_abridor=2.4):
    """
    Calcula la probabilidad de que un bateador consiga al menos un hit en el juego,
    considerando enfrentamientos contra el abridor y el bullpen.
    """
    if p_hit_abridor is None or p_hit_bullpen is None:
        return None

    pa_vs_abridor = min(pa_total, pa_esperadas_abridor)
    pa_vs_bullpen = max(0, pa_total - pa_vs_abridor)

    prob_fallar_abridor = (1 - p_hit_abridor) ** pa_vs_abridor
    prob_fallar_bullpen = (1 - p_hit_bullpen) ** pa_vs_bullpen

    prob_fallar_juego = prob_fallar_abridor * prob_fallar_bullpen
    return 1 - prob_fallar_juego
    
def obtener_ultimos_hits(player_id, season):
    url = f"{BASE_URL}/people/{player_id}/stats"
    params = {"stats": "gameLog", "group": "hitting", "season": season, "gameType": "R"}
    try:
        data = get_json(url, params=params)
        splits = data.get("stats", [{}])[0].get("splits", [])

        # Invertir el orden para que el último juego esté primero
        juegos_validos = [
            juego for juego in splits
            if int(juego.get("stat", {}).get("plateAppearances", 0)) > 0
        ][::-1]

        # Tomar los últimos 5 juegos reales (más recientes)
        ultimos_juegos = juegos_validos[:5]
        hits_list = [str(juego.get("stat", {}).get("hits", 0)) for juego in ultimos_juegos]

        if not hits_list:
            return "[--]"
        return "[" + " ".join(hits_list[::-1]) + "]"  # ← opcional: muestra del más antiguo al más reciente
    except Exception:
        return "[--]"
        
def calcular_probabilidades_jugador(jugador, pitcher_rival, juego):
    """
    Devuelve:
        p_hit_juego, p_hr_juego
    para un jugador específico usando TODA la lógica del modelo.
    """

    season = datetime.now().year

    # 1️⃣ Determinar mano real del bateador vs pitcher
    bat_hand = jugador.get("batSide", "R")
    if bat_hand == "S":
        bat_hand = "L" if pitcher_rival["hand"] == "R" else "R"

    # 2️⃣ Obtener xBA liga dinámico
    xba_liga = obtener_xba_liga_pa(season)

    # 3️⃣ Obtener talento del bateador vs abridor
    tasa_abridor, pa_split = obtener_talento_xba_split(
        jugador["id"], season, pitcher_rival["hand"], xba_liga, "hitting"
    )

    # 4️⃣ Obtener talento del bateador vs bullpen (neutral)
    tasa_bullpen_neutral, _ = obtener_talento_xba_split(
        jugador["id"], season, None, xba_liga, "hitting"
    )

    # 5️⃣ Obtener talento del pitcher rival vs mano del bateador
    tasa_pitcher, _ = obtener_talento_xba_split(
        pitcher_rival["id"], season, bat_hand, xba_liga, "pitching"
    )

    if tasa_abridor is None or tasa_bullpen_neutral is None or tasa_pitcher is None:
        return None, None

    # 6️⃣ Park factor del estadio
    pf = ESTADIOS.get(juego["home"], {}).get("pf", 100)

    # 7️⃣ Probabilidad de hit por PA vs abridor y bullpen
    p_hit_pa_abridor = log5_con_park_factor(tasa_abridor, tasa_pitcher, xba_liga, pf)
    p_hit_pa_bullpen = log5_con_park_factor(tasa_bullpen_neutral, tasa_pitcher, xba_liga, pf)

    if p_hit_pa_abridor is None or p_hit_pa_bullpen is None:
        return None, None

    # 8️⃣ PA estimados según orden
    orden = jugador.get("orden", 5)
    pa_total = PA_POR_ORDEN.get(orden, PA_POR_JUEGO)
    pa_abridor_estimadas = 2.6 if orden <= 4 else 2.1

    # 9️⃣ Probabilidad de hit en el juego
    p_hit_juego = prob_hit_en_juego_con_bullpen(
        p_hit_pa_abridor,
        p_hit_pa_bullpen,
        pa_total,
        pa_esperadas_abridor=pa_abridor_estimadas
    )

    # 🔟 HR MODULE
    stats_hr = get_json(
        f"{BASE_URL}/people/{jugador['id']}/stats",
        {"stats": "season", "group": "hitting", "season": season}
    )

    try:
        stat = stats_hr["stats"][0]["splits"][0]["stat"]
        h = int(stat.get("hits", 0))
        hr = int(stat.get("homeRuns", 0))
        ab = int(stat.get("atBats", 0))

        iso = float(stat.get("iso", 0.0)) if "iso" in stat else (
            (stat.get("doubles", 0)*2 + stat.get("triples", 0)*3 + hr*4) / ab - (h/ab)
            if ab > 0 else 0.0
        )
        dist_hr = hr / h if h > 0 else 0.0
    except:
        iso = 0.0
        dist_hr = 0.0

    prob_hr_pa = calcular_prob_hr_por_pa(p_hit_pa_abridor, iso, dist_hr, pf)
    p_hr_juego = 1 - (1 - prob_hr_pa) ** pa_total

    return p_hit_juego, p_hr_juego
        
# ==========================================
# PRINT FINAL — LINEUPS, PROBABILIDADES, HR, ERA, SP/BP
# ==========================================

def imprimir_resultados_juego(juego, lineups, pitchers, eras_pitchers, talento_bullpen,
                              pf_ajustado, xba_liga_dinamico, season, cache_stats_pitcher):

    for side_sel in ["away", "home"]:
        lineup = lineups.get(side_sel)
        if not lineup:
            print(f"\n⚠️ Lineup de {juego[side_sel]} no disponible en API todavía.")
            continue

        side_rival = "home" if side_sel == "away" else "away"
        pitcher = pitchers.get(side_rival)

        if not pitcher:
            print(f"\n⚠️ Pitcher abridor de {juego[side_rival]} no anunciado.")
            continue

        era_pitcher = eras_pitchers.get(side_rival)
        era_str = f"{era_pitcher:.2f}" if era_pitcher is not None else "-.--"

        mejor_sp = "👑" if (
            eras_pitchers["away"] is not None and
            eras_pitchers["home"] is not None and
            (
                (side_rival == "away" and eras_pitchers["away"] < eras_pitchers["home"]) or
                (side_rival == "home" and eras_pitchers["home"] < eras_pitchers["away"])
            )
        ) else ""

        mejor_bp = "⭐" if (
            talento_bullpen["away"] is not None and
            talento_bullpen["home"] is not None and
            (
                (side_rival == "away" and talento_bullpen["away"] < talento_bullpen["home"]) or
                (side_rival == "home" and talento_bullpen["home"] < talento_bullpen["away"])
            )
        ) else ""

        baa_bullpen_rival = talento_bullpen[side_rival]

        print("\n" + "=" * WIDTH)
        print(f"⚾ {juego[side_sel]}".center(WIDTH))
        print(f"🎯 P: {pitcher['fullName']} ({pitcher['hand']}) | ERA: {era_str} {mejor_sp}".center(WIDTH))
        print(f"🛡️ Bullpen AVG: {baa_bullpen_rival:.3f} {mejor_bp}".center(WIDTH))
        print("=" * WIDTH)

        print(f"{'Jugador':<22} | B | PA |  xBA | pPA% | pJue% | HR%")
        print("-" * WIDTH)

        resultados = []

        for p in lineup:
            bat_hand_real = p["batSide"]
            if bat_hand_real == "S":
                bat_hand_real = "L" if pitcher["hand"] == "R" else "R"

            cache_key = (pitcher["id"], bat_hand_real)

            tasa_abridor, pa_split = obtener_talento_xba_split(
                p["id"], season, pitcher["hand"], xba_liga_dinamico, "hitting"
            )
            tasa_bullpen_neutral, _ = obtener_talento_xba_split(
                p["id"], season, None, xba_liga_dinamico, "hitting"
            )

            if cache_key in cache_stats_pitcher:
                tasa_pitcher = cache_stats_pitcher[cache_key]
            else:
                tasa_pitcher, _ = obtener_talento_xba_split(
                    pitcher["id"], season, bat_hand_real, xba_liga_dinamico, "pitching"
                )
                cache_stats_pitcher[cache_key] = tasa_pitcher

            if tasa_abridor is None or tasa_pitcher is None or tasa_bullpen_neutral is None:
                continue

            p_hit_pa_abridor = log5_con_park_factor(tasa_abridor, tasa_pitcher, xba_liga_dinamico, pf_ajustado)
            p_hit_pa_bullpen = log5_con_park_factor(tasa_bullpen_neutral, baa_bullpen_rival, xba_liga_dinamico, pf_ajustado)

            orden_real = p["orden"]
            n_pa_est = PA_POR_ORDEN.get(orden_real, PA_POR_JUEGO)
            pa_abridor_estimadas = 2.6 if orden_real <= 4 else 2.1

            p_hit_juego = prob_hit_en_juego_con_bullpen(
                p_hit_pa_abridor,
                p_hit_pa_bullpen,
                n_pa_est,
                pa_esperadas_abridor=pa_abridor_estimadas
            )

            # Racha corregida
            racha_reciente = obtener_ultimos_hits(p["id"], season)
            emoji_racha = evaluar_racha(racha_reciente)

            # HR Module
            stats_hr = get_json(
                f"{BASE_URL}/people/{p['id']}/stats",
                {"stats": "season", "group": "hitting", "season": season}
            )

            try:
                stat = stats_hr["stats"][0]["splits"][0]["stat"]
                h = int(stat.get("hits", 0))
                hr = int(stat.get("homeRuns", 0))
                ab = int(stat.get("atBats", 0))
                iso = float(stat.get("iso", 0.0)) if "iso" in stat else (
                    (stat.get("doubles", 0)*2 + stat.get("triples", 0)*3 + hr*4) / ab - (h/ab)
                    if ab > 0 else 0.0
                )
                dist_hr = hr / h if h > 0 else 0.0
            except:
                iso = 0.0
                dist_hr = 0.0

            prob_hr_pa = calcular_prob_hr_por_pa(p_hit_pa_abridor, iso, dist_hr, pf_ajustado)
            prob_hr_juego = 1 - (1 - prob_hr_pa) ** n_pa_est

            nombre_tabla = p["name"][:22]

            print(
                f"{nombre_tabla:<22} | {bat_hand_real} | {pa_split:>2} | "
                f"{tasa_abridor:.3f} | {p_hit_pa_abridor*100:>5.1f}% | "
                f"{p_hit_juego*100:>5.1f}% | {prob_hr_juego*100:>4.1f}% {emoji_racha}"
            )
            print(f" ↳ {racha_reciente}")

            resultados.append({
                "name": nombre_tabla,
                "pa": pa_split,
                "p_g": p_hit_juego * 100,
                "p_hr": prob_hr_juego * 100,
                "emoji": emoji_racha,
                "racha": racha_reciente
            })

        # TOP 3 — racha debajo del jugador
        if resultados:
            top3 = sorted(resultados, key=lambda x: x["p_g"], reverse=True)[:3]
            print("\n" + "🏆 TOP 3 VALOR ESPERADO (Hits)".center(WIDTH))
            print("-" * WIDTH)

            for i, r in enumerate(top3, 1):
                msg = f" {r['emoji']}" if r["emoji"] else ""

                # Línea principal
                print(
                    f"{i}. {r['name']:<22} | PA:{r['pa']:>3} | Hit%:{r['p_g']:>5.1f}% | "
                    f"HR%:{r['p_hr']:>4.1f}%{msg}"
                )

                # Racha debajo (igual que en lineup)
                print(f"    ↳ {r['racha']}")

            print("-" * WIDTH)
            
# ==========================================
# MAIN
# ==========================================

def main():
    hoy = date.today()
    season = hoy.year

    print(f"\n{'='*WIDTH}")
    print(f" MLB LOG5 PRO v7.5 (WF v2 + HR Module + Bullpen Real) ".center(WIDTH))
    print(f"{'='*WIDTH}\n")

    print("⏳ Consultando datos de la liga...")
    xba_liga_dinamico = obtener_xba_liga_pa(season)
    print(f"📊 Promedio de Liga (Hits/PA): {xba_liga_dinamico:.4f}\n")

    # Obtener juegos del día
    juegos = obtener_juegos_del_dia(hoy)
    if not juegos:
        print("No hay juegos programados hoy.")
        return

    for i, g in enumerate(juegos, 1):
        print(f"{i:2}) {g['away']:<25} @ {g['home']:<25} [{g['hora_vzla']}]")

    # Selección de juego
    try:
        idx = int(input("\nJuego: "))
        juego = juegos[idx - 1]
    except (ValueError, IndexError):
        print("Selección inválida.")
        return

    game_pk = juego["gamePk"]
    equipo_local = juego["home"]
    datos_estadio = ESTADIOS.get(equipo_local, {"nombre": "Desconocido", "pf": 100})
    pf_base = datos_estadio["pf"]

    print("\n⏳ Descargando Lineups, Clima y Bullpens...")
    live = obtener_live_game(game_pk)
    pitchers = extraer_probable_pitchers(live)
    lineups = extraer_lineup_y_batting_order(live)
    records = extraer_records_equipos(live)
    clima = extraer_clima(live)
    cache_stats_pitcher = {}

    # Bullpen real
    bullpen_away = obtener_talento_bullpen_equipo(juego["away_id"], season)
    bullpen_home = obtener_talento_bullpen_equipo(juego["home_id"], season)
    talento_bullpen = {"away": bullpen_away, "home": bullpen_home}

    # ERA de abridores
    era_away = obtener_era_pitcher(pitchers["away"]["id"], season) if pitchers.get("away") else None
    era_home = obtener_era_pitcher(pitchers["home"]["id"], season) if pitchers.get("home") else None
    eras_pitchers = {"away": era_away, "home": era_home}

    # Weather Factor
    wf_valor, clima_desc = calcular_weather_factor(clima)
    pf_ajustado = pf_base * wf_valor

    # Win Probabilities (Log5)
    pct_away = records["away"]
    pct_home = records["home"]

    prob_neutral_away = predecir_ganador_log5(pct_away, pct_home)
    prob_neutral_home = 1 - prob_neutral_away

    if 0 < prob_neutral_home < 1:
        odds_home = (prob_neutral_home / (1 - prob_neutral_home)) * 1.08
        prob_victoria_home = (odds_home / (1 + odds_home)) * 100
    else:
        prob_victoria_home = prob_neutral_home * 100

    prob_victoria_away = 100 - prob_victoria_home

    # PRINT DEL ESTADIO Y WF
    print("\n" + "*" * WIDTH)
    print(f"🏟️ {datos_estadio['nombre']} | PF Base: {pf_base} | WF: {wf_valor:.2f}".center(WIDTH))
    print(f"{clima_desc}  =>  PF Ajustado: {pf_ajustado:.1f}".center(WIDTH))
    print(f"({evaluar_estadio(pf_ajustado)})".center(WIDTH))
    print("*" * WIDTH)

    # PRINT DE WIN PROBABILITIES
    print("\n" + "🏆 PREDICCIÓN DEL JUEGO (Log5 Win%)".center(WIDTH))
    print("-" * WIDTH)
    print(f" 🔹 {juego['away']:<28} [Win%: {pct_away:.3f}] -> {prob_victoria_away:>5.1f}%")
    print(f" 🔸 {juego['home']:<28} [Win%: {pct_home:.3f}] -> {prob_victoria_home:>5.1f}%")
    print("-" * WIDTH)

    # LLAMADA AL PRINT FINAL (Bloque 5)
    imprimir_resultados_juego(
        juego=juego,
        lineups=lineups,
        pitchers=pitchers,
        eras_pitchers=eras_pitchers,
        talento_bullpen=talento_bullpen,
        pf_ajustado=pf_ajustado,
        xba_liga_dinamico=xba_liga_dinamico,
        season=season,
        cache_stats_pitcher=cache_stats_pitcher
    )

    # Loop para otro juego
    if input("¿Otro? (1: Sí): ") == "1":
        main()
if __name__ == "__main__":
    main()