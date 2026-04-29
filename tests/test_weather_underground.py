#!/usr/bin/env python3
"""Simulador de estación meteorológica WH2900 / Wunderground.

Genera valores realistas para una estación en Tucumán y los envía por HTTP
GET al endpoint del datalogger, replicando el protocolo "Customized Website"
del WH2900.

Uso:
    python tests/test_weather_underground.py            # un único envío al server por defecto
    python tests/test_weather_underground.py --loop 60  # envía cada 60 s
    python tests/test_weather_underground.py --host 192.168.1.50 --port 4712

Endpoint default: http://lealab.duckdns.org:4712/weatherstation/updateweatherstation.php
"""

import argparse
import math
import random
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone


def generar_payload(station_id: str, password: str) -> dict:
    """Devuelve un dict con campos en el formato Wunderground PWS, valores
    realistas alrededor de un día tipo en Tucumán."""
    ahora = datetime.now(timezone.utc)
    hora_local = (ahora.hour - 3) % 24  # UTC-3
    # Temp diurna 22 + 8*sin((h-6)/24*pi) approx
    temp_c = 22 + 8 * math.sin((hora_local - 6) / 24 * 2 * math.pi)
    temp_c += random.uniform(-1.5, 1.5)
    temp_f = temp_c * 9 / 5 + 32

    rh = max(20, min(95, 70 - (temp_c - 18) * 1.5 + random.uniform(-5, 5)))
    # Punto de rocío aproximado (Magnus simplificado)
    a, b = 17.27, 237.7
    gamma = (a * temp_c) / (b + temp_c) + math.log(rh / 100.0)
    dew_c = (b * gamma) / (a - gamma)
    dew_f = dew_c * 9 / 5 + 32

    pres_mbar = 968 + random.uniform(-2, 2)
    pres_inhg = pres_mbar / 33.8639

    wind_ms = max(0.0, random.gauss(2.5, 1.5))
    gust_ms = wind_ms + random.uniform(0, 3)
    wind_mph = wind_ms / 0.44704
    gust_mph = gust_ms / 0.44704
    wind_dir = random.randint(0, 359)

    rain_in_hour = round(random.choice([0, 0, 0, 0, 0, 0.05, 0.1]), 3)
    rain_in_day = round(rain_in_hour + random.uniform(0, 0.5), 3)

    # Solar: 0 de noche, hasta ~900 W/m2 al mediodía
    solar = 0.0
    if 6 <= hora_local <= 19:
        solar = 900 * math.sin(((hora_local - 6) / 13) * math.pi)
        solar = max(0, solar + random.uniform(-50, 50))

    uv = max(0, min(11, round(solar / 100, 1)))

    return {
        "ID": station_id,
        "PASSWORD": password,
        "dateutc": ahora.strftime("%Y-%m-%d+%H:%M:%S"),
        "tempf": f"{temp_f:.2f}",
        "humidity": f"{rh:.1f}",
        "dewptf": f"{dew_f:.2f}",
        "baromin": f"{pres_inhg:.3f}",
        "windspeedmph": f"{wind_mph:.2f}",
        "windgustmph": f"{gust_mph:.2f}",
        "winddir": str(wind_dir),
        "rainin": f"{rain_in_hour:.3f}",
        "dailyrainin": f"{rain_in_day:.3f}",
        "solarradiation": f"{solar:.1f}",
        "UV": str(uv),
        "indoortempf": f"{temp_f - random.uniform(2, 5):.2f}",
        "indoorhumidity": f"{max(20, rh - random.uniform(10, 25)):.1f}",
        "softwaretype": "WH2900_Simulator",
        "action": "updateraw",
    }


def enviar(host: str, port: int, station_id: str, password: str, path: str) -> None:
    payload = generar_payload(station_id, password)
    qs = urllib.parse.urlencode(payload)
    url = f"http://{host}:{port}{path}?{qs}"
    print(f"\n--- {datetime.now().isoformat(timespec='seconds')} ---")
    print(f"GET {url[:120]}{'...' if len(url) > 120 else ''}")
    print("Datos legibles:")
    for k, v in payload.items():
        if k not in ("PASSWORD", "action", "softwaretype"):
            print(f"  {k:18s} = {v}")

    req = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            body = resp.read().decode("utf-8", errors="ignore").strip()
            print(f"--> HTTP {resp.status}: {body!r}")
    except Exception as error:
        print(f"--> ERROR: {error}")


def main():
    p = argparse.ArgumentParser(description="Simulador WH2900 (protocolo Wunderground)")
    p.add_argument("--host", default="lealab.duckdns.org")
    p.add_argument("--port", type=int, default=4712)
    p.add_argument(
        "--path",
        default="/weatherstation/updateweatherstation.php",
        help="Endpoint Wunderground PWS",
    )
    p.add_argument("--id", dest="station_id", default="KEALAB")
    p.add_argument("--password", default="changeme")
    p.add_argument(
        "--loop",
        type=int,
        default=0,
        help="Si > 0, repite cada N segundos. Default: un solo envío.",
    )
    args = p.parse_args()

    if args.loop > 0:
        print(f"Modo loop: enviando cada {args.loop} s. Ctrl-C para terminar.")
        while True:
            enviar(args.host, args.port, args.station_id, args.password, args.path)
            time.sleep(args.loop)
    else:
        enviar(args.host, args.port, args.station_id, args.password, args.path)


if __name__ == "__main__":
    main()
