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

import re
import yaml
import json
import getmac
import logging
import paho.mqtt.client as mqtt

from datetime import datetime
from typing import Dict, List
from analyzers import *

registro = logging.getLogger(__name__)


class MqttHandler(logging.Handler):
    def __init__(self, client, topic):
        logging.Handler.__init__(self)
        self._client = client
        self._topic = topic

    def emit(self, record):
        # noinspection PyBroadException,PyPep8
        try:
            message = self.format(record)
            if message.find("\n"):
                message = message.split("\n")[0]
            self._client.publish(topic=self._topic, payload=message)
        except (KeyboardInterrupt, SystemExit):
            raise
        except:
            self.handleError(record)


class Datalogger:
    def __init__(self, config: str, simulated=False) -> None:
        registro.debug(f"Configurando el datalogger desde el archivo {config}")
        with open(config, "r") as stream:
            self._config = yaml.load(stream, Loader=yaml.FullLoader)

        self._name = self.config("name", "datalogger")
        self._latitude = self.config("latitude", "0.0")
        self._longitude = self.config("longitude", "0.0")
        self._mac = getmac.get_mac_address()
        self._last_heart_beat = datetime.now()
        self._updated = False
        self._values = []

        self.configure_mqtt()
        self.condigure_logger()

        self._analyzers = []
        for analyzer in self.config("anayzers", []):
            registro.debug(
                f"Creando un analizador con {analyzer.get('name','')} de la clase {analyzer.get('class','')}",
            )

            try:
                clase = analyzer.pop("class")
                analyzer["publisher"] = self.publisher
                analyzer["simulated"] = simulated
                analizador = eval(clase)(**analyzer)
                analizador.dir = self.config("storage.dir", None)
                registro.debug(
                    f"Asignando {analizador.dir} para publicar los archivos de log"
                )
                analizador.filter_data = self.config("storage.filter", 0)
                self._analyzers.append(analizador)
            except:
                registro.error(
                    f"No se pudo crear el analizador {analyzer['name']} del tipo {clase}"
                )

    def configure_mqtt(self):
        servidor = self.config("mqtt.server", "datalogger")
        registro.debug(f"Conectando al servidor mqtt {servidor}")
        self._client = mqtt.Client(
            client_id=self._name,
            transport="tcp",
            protocol=mqtt.MQTTv311,
            clean_session=True,
        )
        if self.config("mqtt.username", None):
            self._client.username_pw_set(
                username=self.config("mqtt.username", ""),
                password=self.config("mqtt.password", ""),
            )
        self._client.connect(
            host=self.config("mqtt.server", ""),
            port=self.config("mqtt.port", 1883),
        )
        self._client.loop_start()

    def condigure_logger(self):
        logger = logging.getLogger()
        handler = MqttHandler(self._client, f"V0/NLOG/{self._mac}")
        formatter = logging.Formatter(
            "%(asctime)-20s %(levelname)-10s %(name)-15s %(message)-s",
            "%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(formatter)
        handler.setLevel(logging.WARNING)
        logger.addHandler(handler)

    def config(self, ruta: str, predeterminado: any) -> dict:
        resultado = predeterminado
        dicccionario = self._config
        for clave in ruta.split("."):
            if clave in ruta and type(dicccionario[clave]) == dict:
                dicccionario = dicccionario[clave]
            else:
                break
        if clave in ruta and type(dicccionario[clave]):
            resultado = dicccionario[clave]
        return resultado

    def start(self):
        topic = f"V0/NBIRTH/{self._mac}"
        payload = {
            "ts": int(datetime.now().timestamp()),
            "lbl": self._name,
            "mac": self._mac,
            "lat": self._latitude,
            "lon": self._longitude,
        }
        self._client.publish(topic=topic, payload=json.dumps(payload))
        registro.debug(f"Iniciando el cliente MQTT")

    def poll(self):
        if (datetime.now() - self._last_heart_beat).total_seconds() > 10:
            self._last_heart_beat = datetime.now()
            topic = f"V0/NHI/{self._mac}"
            self._client.publish(topic=topic, payload=1)

        for analyzer in self._analyzers:
            analyzer.poll()

        if self._updated:
            topic = f"V0/NDATA/{self._mac}"
            payload = {
                "meta": {
                    "ts": int(datetime.now().timestamp()),
                    "mac": self._mac,
                },
                "data": self._values,
            }
            self._client.publish(topic=topic, payload=json.dumps(payload))
            self._values = []
            self._updated = False

    def publisher(self, topic: str, values: List[Dict]):
        for key, value in values.items():
            value = float(re.sub("[^\d\.]", "", value))
            updated = False
            for entry in self._values:
                if entry["parameter"] == key:
                    entry["value"] = value
                    updated = True
                    break
            if not updated:
                self._values.append({"parameter": key, "value": value})
        self._updated = True
