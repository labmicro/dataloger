#!/usr/bin/env python3
# encoding: utf-8

##################################################################################################
# Copyright (c) 2022-2023, Laboratorio de Microprocesadores
# Facultad de Ciencias Exactas y Tecnología, Universidad Nacional de Tucumán
# https://www.microprocesadores.unt.edu.ar/
#
# Copyright (c) 2022-2023, Esteban Volentini <evolentini@herrera.unt.edu.ar>
#
# Permission is hereby granted, free of charge, to any person obtaining a copy of this software and
# associated documentation files (the "Software"), to deal in the Software without restriction,
# including without limitation the rights to use, copy, modify, merge, publish, distribute,
# sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all copies or substantial
# portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT
# NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES
# OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
# CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
#
# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: 2023, Esteban Volentini <evolentini@herrera.unt.edu.ar>
##################################################################################################

import os
import shutil
import socket
import serial
import logging
import threading
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs

STX = b"\x02"
ETX = b"\x03"
ACK = b"\x06"
NAK = b"\x15"

registro = logging.getLogger(__name__)


def _status_valido(campo: str) -> bool:
    """Valida el código de estado en las tramas seriales de los analizadores
    Environnement S.A. (O342M, AF22M). El campo suele llegar como "M000" y el
    manual lo define como hex de 3 dígitos donde 00 es la única medición
    válida; cualquier otro valor indica ciclo interno (cero 08, span 10),
    calibración, mantenimiento o fallo, y no refleja aire ambiente real.
    """
    digitos = "".join(c for c in campo if c.isdigit() or c in "abcdefABCDEF")
    return digitos[-2:].upper() == "00" if len(digitos) >= 2 else False


class Analyzer:
    COLUMNS = None

    def __init__(
        self,
        name: str,
        port: str,
        publisher: callable,
        topic: str,
        simulated=False,
    ) -> None:
        self._name = name
        self._simulated = simulated
        try:
            self._puerto = serial.Serial(
                port=port,
                baudrate=9600,
                timeout=1,
                write_timeout=1,
            )
        except:
            if self._simulated:
                self._puerto = None
        self._publisher = publisher
        self._topic = topic
        self.dir = ""
        self._last_data = None
        self.filter_data = 0
        self.respuesta = ""

    @property
    def name(self) -> str:
        return self._name

    @property
    def topic(self) -> str:
        return self._topic

    def _get_header(self):
        result = '"Fecha","Hora"'
        for column in self.COLUMNS:
            result = result + f',"{column}"'
        return result

    def _serialize_values(self, values) -> str:
        result = datetime.strftime(datetime.now(), '"%Y-%m-%d","%H:%M:%S"')
        for column in self.COLUMNS:
            result = result + f',"{values[column]}"'
        return result

    def logfile(self):
        filename = f"{self.name}.csv"
        new = not os.path.isfile(f"{self.name}.csv")
        if not new and self._last_data:
            published = (
                f"{self.name}-{self._last_data.year}-{self._last_data.month}.csv"
            )
            if not os.path.exists(self.dir):
                os.mkdir(self.dir)
            if self._last_data.month != datetime.now().month:
                registro.debug(f"Rotando el archivo de log por cambio de mes")
                os.rename(filename, f"{self.dir}/{published}")
                new = True
            elif self._last_data.day != datetime.now().day:
                registro.debug(f"Publicando el archivo de log por cambio de dia")
                shutil.copy(filename, f"{self.dir}/{published}")

        file = open(filename, "a+")
        if new:
            file.write(f"{self._get_header()}\r\n")
        return file

    def log(self, values: dict):
        registro.debug(f"Ultimo dato {self._last_data} y fecha actual {datetime.now()}")
        if self._last_data:
            seconds = (datetime.now() - self._last_data).total_seconds()
        else:
            seconds = self.filter_data
        registro.debug(f"Delta {seconds} y filter {self.filter_data}")

        if seconds >= self.filter_data:
            if self.dir:
                with self.logfile() as archivo:
                    archivo.write(f"{self._serialize_values(values)}\r\n")
                    archivo.close()
                # print(f"{self._last_data} => {data}")
                registro.debug(f"Escribiendo valores en el archivo de log")
            else:
                registro.debug(f"No hay un archivo de log asignado")
            self._last_data = datetime.now()
        else:
            registro.info(f"Los datos no se almacenan por las reglas de filtrado")

    def poll(self) -> dict:
        registro.debug(f"Obteniendo valores del analizador {self.name}")
        values = self._get_values()

        if values:
            registro.info(
                f"Se obtuvieron los siguiente valores del analizador {self.name} {values}"
            )
            self.log(values)

            if self._publisher:
                registro.info(f"Publicando valores del analizador {self.name}")
                self._publisher(topic=self.topic, values=values)
        else:
            registro.warning(f"No se obtuvieron los valores del analizador {self.name}")

        return values


class O341M(Analyzer):
    COLUMNS = ("O3", "EXT1", "EXT2")

    def _get_values(self) -> dict:
        registro.debug(f"Leyendo el puerto serial del analizador {self.name}")
        respuesta = ""
        try:
            if self._simulated:
                respuesta = "14-00-01 23:06  M000  O3   17.7  PPB   EXT1   1.0   mv   EXT2   0.0   mv   \x0D\x0A"
            else:
                respuesta = self._puerto.read_until().decode(errors="ignore")
        except serial.SerialTimeoutException:
            pass
        except Exception as error:
            registro.error(
                f"No se pudo leer desde el puerto {self._puerto.port}, error {str(error)}"
            )

        resultado = {}
        valores = respuesta.replace("\0", " ").split()
        if len(valores) > 11 and _status_valido(valores[2]):
            resultado = {
                valores[3]: f"{valores[4]} {valores[5]}",
                valores[6]: f"{valores[7]} {valores[8]}",
                valores[9]: f"{valores[10]} {valores[11]}",
            }
            registro.info(f"Se recibieron los siguientes datos: {valores}")
        elif len(valores) > 11:
            registro.warning(
                f"Lectura descartada de {self.name} por status {valores[2]}: {valores}"
            )

        return resultado


class AF22M(Analyzer):
    COLUMNS = ("SO2",)

    def _get_values(self) -> dict:
        registro.debug(f"Leyendo el puerto serial del analizador {self.name}")
        respuesta = ""
        try:
            if self._simulated:
                respuesta = "07-09-23 16:41  M000 SO2       3.510 PPB  \x0D\x0A"
            else:
                respuesta = self._puerto.read_until().decode(errors="ignore")
        except serial.SerialTimeoutException:
            pass
        except Exception as error:
            registro.error(
                f"No se pudo leer desde el puerto {self._puerto.port}, error {str(error)}"
            )

        resultado = {}
        valores = respuesta.replace("\0", " ").split()
        if len(valores) > 5 and _status_valido(valores[2]):
            resultado = {
                valores[3]: f"{valores[4]} {valores[5]}",
            }
            registro.info(f"Se recibieron los siguientes datos: {valores}")
        elif len(valores) > 5:
            registro.warning(
                f"Lectura descartada de {self.name} por status {valores[2]}: {valores}"
            )

        return resultado


class EcoPhysicsNOx(Analyzer):
    COLUMNS = ("NO2", "NO", "NOx")

    def __init__(
        self,
        name: str,
        address: int,
        port: str,
        publisher: callable,
        topic: str,
        simulated=False,
    ) -> None:
        super().__init__(name, port, publisher, topic, simulated)
        self._address = address

        # self.transaccion("HR", "1")
        # self.transaccion("SR", "4")
        # self.transaccion("SM", "0")

        # self.transaccion("HR", "0")

    def _get_values(self) -> dict:
        resultado = {}
        if self._simulated:
            respuesta = " 0.012, 0.004, 0.017"
        else:
            respuesta = self.transaccion("RD", "3")
        try:
            valores = respuesta.split(",")
            resultado = {
                "NO2": valores[0].strip(),
                "NO": valores[1].strip(),
                "NOx": valores[2].strip(),
            }
        except Exception as error:
            registro.error(f"No se pudo leer los datos del analizador, {str(error)}")

        return resultado

    def transaccion(self, comando, argumento):
        comando = STX + f"{self._address:02}{comando}{argumento}".encode() + ETX
        comando = self.bcc(comando, True)

        resultado = None
        registro.debug(f"Enviando la trama {comando} por el puerto {self._puerto.port}")
        try:
            self._puerto.write(comando)
        except:
            registro.error(
                f"No se pudo enviar la trama {comando} por el puerto {self._puerto.port}"
            )
            return resultado

        try:
            respuesta = self._puerto.read_until(ETX)
            bcc = self._puerto.read()
            bcc = self.bcc(respuesta, False)
            registro.debug(
                f"Se recibió la trama {respuesta} por el puerto {self._puerto.port} con el bcc {bcc}"
            )

            if bcc == self.bcc(respuesta, False):
                # registro.debug(f"La trama tiene el status {respuesta[3]}")
                resultado = respuesta[3:-1].decode()
            else:
                registro.warning(f"La trama no pasa el control de errores")

        except:
            registro.error(
                f"No se pudo leer la respuesta al {comando} desde el puerto {self._puerto.port}"
            )

        return resultado

    def bcc(self, datos: bytes, conatenar: False) -> bytes:
        resultado = 0
        for dato in datos:
            resultado = resultado ^ dato
        if conatenar:
            resultado = datos + resultado.to_bytes(1, "little")
        else:
            resultado = resultado.to_bytes(1, "little")
        return resultado


class GrimmEDM264(Analyzer):
    """Espectrómetro de partículas GRIMM EDM 264 vía TCP.

    Protocolo estándar (manual EDM 264 cap. 9.1): el equipo entrega cada
    intervalo al menos dos líneas:
      - P-line: fecha/hora, sensores de clima (Temp, rH, presión), GPS.
      - N-line: 13 fracciones de masa en µg/m³ (TSP, PM10, PM4, PM2.5, PM1,
        PMcoarse, inhalable, thoracic, respirable, pm10, pm2.5, pm1, TC).

    Al abrir el socket enviamos ^E (0x05) para habilitar la salida de datos.
    La clase mantiene el último P-line en caché para adjuntar los valores
    de clima al próximo N-line (ambos se emiten en bloque cada intervalo).
    """

    COLUMNS = (
        "TSP",
        "PM10",
        "PM4",
        "PM25",
        "PM1",
        "PMcoarse",
        "TC",
        "GrimmTemp",
        "GrimmRH",
        "GrimmPres",
    )

    def __init__(
        self,
        name: str,
        host: str,
        port,
        publisher: callable,
        topic: str,
        simulated=False,
    ) -> None:
        self._name = name
        self._host = host
        self._tcp_port = int(port)
        self._publisher = publisher
        self._topic = topic
        self._simulated = simulated
        self._socket = None
        self._rx_buffer = b""
        self._last_p = {}
        self.dir = ""
        self._last_data = None
        self.filter_data = 0
        self.respuesta = ""

    def _ensure_connection(self):
        if self._socket is not None:
            return
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(5)
            s.connect((self._host, self._tcp_port))
            s.sendall(b"\x05")
            self._socket = s
            self._rx_buffer = b""
            registro.info(
                f"Grimm {self._name}: conectado a {self._host}:{self._tcp_port}"
            )
        except Exception as error:
            registro.error(
                f"Grimm {self._name}: no se pudo conectar a {self._host}:{self._tcp_port}, {error}"
            )
            self._socket = None

    def _drop_connection(self):
        if self._socket is not None:
            try:
                self._socket.close()
            except Exception:
                pass
        self._socket = None
        self._rx_buffer = b""

    def _read_available_lines(self):
        if self._simulated:
            return [
                "P   26    4   22   13   55   1    1  100    0   NA   34   17.7   83.5     NA  967.8     NA     NA   0   84659.1  1511418.4   42.2   28.6  -26.8344  -65.2044    514   99.4A    NA      NA      NA",
                "N_     17.2      9.2      5.6      4.7      4.0      4.6     14.8     12.2      7.1     11.7      5.3      4.3    53459",
            ]

        self._ensure_connection()
        if self._socket is None:
            return []

        lines = []
        try:
            self._socket.settimeout(0.3)
            while True:
                chunk = self._socket.recv(4096)
                if not chunk:
                    registro.warning(
                        f"Grimm {self._name}: el equipo cerró el socket"
                    )
                    self._drop_connection()
                    break
                self._rx_buffer += chunk
        except socket.timeout:
            pass
        except Exception as error:
            registro.warning(f"Grimm {self._name}: error leyendo socket, {error}")
            self._drop_connection()

        while b"\r\n" in self._rx_buffer:
            raw, self._rx_buffer = self._rx_buffer.split(b"\r\n", 1)
            decoded = raw.decode("ascii", errors="ignore").strip()
            if decoded:
                lines.append(decoded)
        return lines

    @staticmethod
    def _f(text):
        if text is None:
            return None
        if text.upper() == "NA":
            return None
        try:
            return float(text.rstrip("Aam"))
        except ValueError:
            return None

    def _parse_n_line(self, parts):
        if len(parts) < 14:
            return None
        v = parts[1:14]
        return {
            "TSP": self._f(v[0]),
            "PM10": self._f(v[1]),
            "PM4": self._f(v[2]),
            "PM25": self._f(v[3]),
            "PM1": self._f(v[4]),
            "PMcoarse": self._f(v[5]),
            "TC": self._f(v[12]),
        }

    def _parse_p_line(self, parts):
        if len(parts) < 16:
            return None
        p = parts[1:]
        return {
            "GrimmTemp": self._f(p[11]) if len(p) > 11 else None,
            "GrimmRH": self._f(p[12]) if len(p) > 12 else None,
            "GrimmPres": self._f(p[14]) if len(p) > 14 else None,
        }

    def _get_values(self) -> dict:
        lines = self._read_available_lines()
        n_data = None

        for line in lines:
            parts = line.split()
            if not parts:
                continue
            ident = parts[0]
            if ident == "P":
                p = self._parse_p_line(parts)
                if p:
                    self._last_p = {k: v for k, v in p.items() if v is not None}
                    registro.debug(
                        f"Grimm {self._name}: P-line clima {self._last_p}"
                    )
            elif len(ident) <= 2 and ident.startswith("N"):
                parsed = self._parse_n_line(parts)
                if parsed:
                    n_data = {k: v for k, v in parsed.items() if v is not None}
                    registro.info(
                        f"Grimm {self._name}: N-line masas {n_data}"
                    )

        if not n_data:
            return {}

        resultado = dict(n_data)
        for k, v in self._last_p.items():
            resultado.setdefault(k, v)
        return resultado

    def _serialize_values(self, values) -> str:
        result = datetime.strftime(datetime.now(), '"%Y-%m-%d","%H:%M:%S"')
        for column in self.COLUMNS:
            result = result + f',"{values.get(column, "NA")}"'
        return result


class WeatherUnderground(Analyzer):
    """Estación meteorológica que envía datos por HTTP en formato Wunderground.

    Funciona con cualquier estación que soporte el protocolo PWS de Weather
    Underground (Ecowitt WH2900, Ambient Weather, etc.) configurada en modo
    "Customized Website". El equipo manda peticiones HTTP GET a
    /weatherstation/updateweatherstation.php?ID=...&PASSWORD=...&...&action=updateraw

    Esta clase levanta un servidor HTTP en un hilo en segundo plano que
    captura cada update, lo convierte a unidades métricas y lo deja en un
    estado interno para que la próxima invocación de poll() lo publique al
    MQTT como cualquier otro analyzer. Si no llega un update entre dos polls
    consecutivos, _get_values devuelve {} y no se publica nada.

    Conversiones aplicadas:
      tempf, indoortempf, dewptf  →  °C
      windspeedmph, windgustmph    →  m/s
      baromin                       →  mbar
      rainin, dailyrainin           →  mm
    """

    COLUMNS = (
        "MeteoTempOut",
        "MeteoRHOut",
        "MeteoDewPoint",
        "MeteoWindChill",
        "MeteoPressure",
        "MeteoWindSpeed",
        "MeteoWindGust",
        "MeteoWindDir",
        "MeteoRainHour",
        "MeteoRainDay",
        "MeteoRainWeek",
        "MeteoRainMonth",
        "MeteoSolarRad",
        "MeteoUV",
        "MeteoTempIn",
        "MeteoRHIn",
    )

    def __init__(
        self,
        name: str,
        port,
        publisher: callable,
        topic: str,
        station_id: str = None,
        password: str = None,
        bind: str = "0.0.0.0",
        simulated=False,
    ) -> None:
        self._name = name
        self._http_port = int(port)
        self._publisher = publisher
        self._topic = topic
        self._simulated = simulated
        self._station_id = station_id
        self._password = password
        self._bind = bind
        self._lock = threading.Lock()
        self._latest = None
        self._server = None
        self.dir = ""
        self._last_data = None
        self.filter_data = 0
        self.respuesta = ""

        if not self._simulated:
            self._start_server()

    def _start_server(self):
        try:
            handler_cls = self._make_handler()
            self._server = HTTPServer((self._bind, self._http_port), handler_cls)
            thread = threading.Thread(
                target=self._server.serve_forever,
                name=f"WU-{self._name}",
                daemon=True,
            )
            thread.start()
            registro.info(
                f"WU {self._name}: escuchando HTTP en {self._bind}:{self._http_port}"
            )
        except Exception as error:
            registro.error(
                f"WU {self._name}: no se pudo iniciar HTTP en "
                f"{self._bind}:{self._http_port}, {error}"
            )
            self._server = None

    def _make_handler(self):
        outer = self

        class _Handler(BaseHTTPRequestHandler):
            def do_GET(handler):
                outer._handle_get(handler)

            def log_message(handler, fmt, *args):
                # silencio el access log default; loggea registro.debug si querés
                return

        return _Handler

    def _handle_get(self, handler):
        try:
            raw_path = handler.path
            # Workaround: el firmware EasyWeather V1.7.2 del WH2900 concatena
            # los parámetros del query string directamente al path sin el "?"
            # separador (ej. "/path.phpID=...&tempf=..."). Si detectamos esa
            # forma, insertamos el "?" en el primer campo conocido para que
            # urlparse pueda extraer correctamente la query.
            if "?" not in raw_path:
                for marker in (
                    "ID=",
                    "PASSWORD=",
                    "tempf=",
                    "indoortempf=",
                    "humidity=",
                    "action=",
                    "dateutc=",
                ):
                    idx = raw_path.find(marker)
                    if idx > 0:
                        raw_path = raw_path[:idx] + "?" + raw_path[idx:]
                        break

            parsed = urlparse(raw_path)
            params = {k: v[0] for k, v in parse_qs(parsed.query).items()}
            client_ip = handler.client_address[0]
            registro.info(
                f"WU {self._name}: GET de {client_ip} path={parsed.path} "
                f"campos={list(params.keys())}"
            )

            if self._station_id and params.get("ID") != self._station_id:
                registro.warning(
                    f"WU {self._name}: rechazado por ID inválido "
                    f"(recibido={params.get('ID')!r}, esperado={self._station_id!r})"
                )
                handler.send_response(401)
                handler.end_headers()
                handler.wfile.write(b"bad station id\n")
                return

            if self._password and params.get("PASSWORD") != self._password:
                registro.warning(
                    f"WU {self._name}: rechazado por PASSWORD inválido"
                )
                handler.send_response(401)
                handler.end_headers()
                handler.wfile.write(b"bad password\n")
                return

            valores = self._convertir(params)

            if valores:
                with self._lock:
                    if self._latest is None:
                        self._latest = {}
                    self._latest.update(valores)
                registro.info(
                    f"WU {self._name}: update recibido {valores}"
                )
            else:
                registro.warning(
                    f"WU {self._name}: GET sin campos parseables, params={params}"
                )

            handler.send_response(200)
            handler.send_header("Content-Type", "text/plain")
            handler.end_headers()
            handler.wfile.write(b"success\n")
        except Exception as error:
            registro.warning(f"WU {self._name}: error procesando GET, {error}")
            try:
                handler.send_response(500)
                handler.end_headers()
            except Exception:
                pass

    @staticmethod
    def _f_to_c(f):
        return (float(f) - 32.0) * 5.0 / 9.0

    @staticmethod
    def _mph_to_ms(mph):
        return float(mph) * 0.44704

    @staticmethod
    def _inhg_to_mbar(inhg):
        return float(inhg) * 33.8639

    @staticmethod
    def _in_to_mm(inches):
        return float(inches) * 25.4

    def _convertir(self, params):
        resultado = {}

        def grabar(field, src_key, fn=float):
            v = params.get(src_key)
            if v is None or v == "" or v.lower() == "nan":
                return
            try:
                resultado[field] = round(fn(v), 3)
            except (ValueError, TypeError):
                pass

        grabar("MeteoTempOut", "tempf", self._f_to_c)
        grabar("MeteoTempIn", "indoortempf", self._f_to_c)
        grabar("MeteoRHOut", "humidity")
        grabar("MeteoRHIn", "indoorhumidity")
        grabar("MeteoDewPoint", "dewptf", self._f_to_c)
        grabar("MeteoWindChill", "windchillf", self._f_to_c)
        # Presión: se prefiere absbaromin (presión absoluta de estación) sobre
        # baromin (que viene corregida al nivel del mar). La absoluta es la que
        # corresponde comparar con la del Grimm (GrimmPres).
        if "absbaromin" in params:
            grabar("MeteoPressure", "absbaromin", self._inhg_to_mbar)
        else:
            grabar("MeteoPressure", "baromin", self._inhg_to_mbar)
        grabar("MeteoWindSpeed", "windspeedmph", self._mph_to_ms)
        grabar("MeteoWindGust", "windgustmph", self._mph_to_ms)
        grabar("MeteoWindDir", "winddir")
        grabar("MeteoRainHour", "rainin", self._in_to_mm)
        grabar("MeteoRainDay", "dailyrainin", self._in_to_mm)
        grabar("MeteoRainWeek", "weeklyrainin", self._in_to_mm)
        grabar("MeteoRainMonth", "monthlyrainin", self._in_to_mm)
        grabar("MeteoSolarRad", "solarradiation")
        grabar("MeteoUV", "UV")
        return resultado

    def _get_values(self) -> dict:
        with self._lock:
            data = self._latest
            self._latest = None
        return data or {}

    def _serialize_values(self, values) -> str:
        result = datetime.strftime(datetime.now(), '"%Y-%m-%d","%H:%M:%S"')
        for column in self.COLUMNS:
            result = result + f',"{values.get(column, "NA")}"'
        return result
