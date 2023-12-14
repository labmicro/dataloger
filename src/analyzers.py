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

import serial
import logging

STX = b"\x02"
ETX = b"\x03"
ACK = b"\x06"
NAK = b"\x15"

registro = logging.getLogger(__name__)


class Analyzer:
    def __init__(self, name: str, port: str, publisher: callable, topic: str) -> None:
        self._name = name
        self._puerto = serial.Serial(
            port=port,
            baudrate=9600,
            timeout=0.5,
            write_timeout=0.5,
        )
        self._publisher = publisher
        self._topic = topic

    @property
    def name(self) -> str:
        return self._name

    @property
    def topic(self) -> str:
        return self._topic

    def poll(self) -> dict:
        registro.debug(f"Obteniendo valores del analizador {self.name}")
        values = self._get_values()

        if values:
            registro.info(
                f"Se obtuvieron los siguiente valores del analizador {self.name} {values}"
            )
            if self._publisher:
                registro.info(f"Publicando valores del analizador {self.name}")
                self._publisher(topic=self.topic, values=values)
        else:
            registro.warning(f"No se obtuvieron los valores del analizador {self.name}")

        return values


class O341M(Analyzer):
    def _get_values(self) -> dict:
        resultado = {}
        try:
            respuesta = self._puerto.read_until()
            valores = respuesta.decode().split()
            registro.error(f"Se recibieron los siguientes datos: {valores}")

            if len(valores) > 11:
                resultado = {
                    valores[3]: f"{valores[4]} {valores[5]}",
                    valores[6]: f"{valores[7]} {valores[8]}",
                    valores[9]: f"{valores[10]} {valores[11]}",
                }
        except:
            registro.error(f"No se pudo leer desde el puerto {self._puerto.port}")
        return resultado


class AF22M(Analyzer):
    def _get_values(self) -> dict:
        resultado = {}
        try:
            respuesta = self._puerto.read_until()
            valores = respuesta.decode().replace("\0", " ").split()
            registro.error(f"Se recibieron los siguientes datos: {valores}")

            if len(valores) > 5:
                resultado = {
                    valores[3]: f"{valores[4]} {valores[5]}",
                }
        except:
            registro.error(f"No se pudo leer desde el puerto {self._puerto.port}")
        return resultado


class EcoPhysicsNOx(Analyzer):
    def __init__(
        self, name: str, address: int, port: str, publisher: callable, topic: str
    ) -> None:
        super().__init__(name, port, publisher, topic)
        self._address = address

        # self.transaccion("HR", "1")
        # self.transaccion("SR", "4")
        # self.transaccion("SM", "0")

        # self.transaccion("HR", "0")

    def _get_values(self) -> dict:
        resultado = {}
        respuesta = self.transaccion("RD", "3")
        try:
            valores = respuesta.split(",")
            resultado = {
                "NO2": valores[0],
                "NO": valores[1],
                "NOx": valores[2],
            }
        except:
            registro.error(f"No se pudo leer los datos del analizador")

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
