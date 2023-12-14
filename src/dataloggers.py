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

import yaml
import logging
import paho.mqtt.client as mqtt

from typing import Dict, List
from analyzers import *

registro = logging.getLogger(__name__)


class Datalogger:
    def __init__(self, config: str) -> None:
        registro.debug(f"Configurando el datalogger desde el archivo {config}")
        with open(config, "r") as stream:
            self._config = yaml.load(stream, Loader=yaml.FullLoader)

        servidor = self.config("mqtt.id", "datalogger")
        registro.debug(f"Conectando al servidor mqtt {servidor}")
        self._client = mqtt.Client(
            client_id=servidor,
            transport="tcp",
            protocol=mqtt.MQTTv311,
            clean_session=True,
        )

        self._analyzers = []
        for analyzer in self.config("anayzers", []):
            registro.debug(
                f"Creando un analizador con {analyzer.get('name','')} de la clase {analyzer.get('class','')}",
            )

            try:
                clase = analyzer.pop("class")
                analyzer["publisher"] = self.publisher
                analizador = eval(clase)(**analyzer)
                analizador.datafile = self.config("storage.filename", None)
                analizador.filter_data = self.config("storage.filter", 0)
                self._analyzers.append(analizador)
            except:
                registro.error(
                    f"No se pudo crear el analizador {analyzer['name']} del tipo {clase}"
                )

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
        # self._client.connect(
        #     self.config("mqtt.server", ""),
        #     port=self.config("mqtt.port", 1883),
        # )
        self._client.connect("test.mosquitto.org", port=1883, keepalive=60)
        self._client.loop_start()
        registro.debug(f"Iniciando el cliente MQTT")

    def poll(self):
        for analyzer in self._analyzers:
            analyzer.poll()

    def publisher(self, topic: str, values: List[Dict]):
        for key, value in values.items():
            registro.debug(f"Publicando {value} en {topic}/{key}")
            self._client.publish(topic=f"{topic}/{key}", payload=value)
