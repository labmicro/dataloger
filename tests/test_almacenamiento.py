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
import glob
import shutil
import pytest
import paho.mqtt.client as mqtt
import serial

from datetime import datetime
from dataloggers import Datalogger
from pytest_mock import MockerFixture
from unittest.mock import MagicMock, call
from pathlib import Path

STX = b"\x02"
ETX = b"\x03"
ACK = b"\x06"
NAK = b"\x15"

CONFIG_FILE = Path(__file__).parent / "data" / "config.yaml"


@pytest.fixture(autouse=True)
def mock_plataform(mocker):
    mocker.serial_port = MagicMock()
    mocker.init_serial = mocker.patch.object(
        serial, "Serial", return_value=mocker.serial_port
    )
    mocker.now = MagicMock()
    mocker.datetime = mocker.patch("analyzers.datetime", wraps=datetime)


# def test_deshabilitar_almacenamiento(mocker: MockerFixture):
#     registro = "data.log"

#     if os.path.isfile(registro):
#         os.remove(registro)

#     datalogger = Datalogger(config=CONFIG_FILE)
#     datalogger.start()

#     mocker.serial_port.read_until.side_effect = [
#         b"14-00-01 23:04  M000  O3   17.8  PPB   EXT1   1.5   mv   EXT2   0.0   mv   \x0D\x0A"
#     ]

#     mocker.datetime.now.return_value = datetime(2023, 12, 24, 8, 3, 1)
#     datalogger._analyzers[1].datafile = None

#     datalogger._analyzers[1].poll()

#     assert not os.path.isfile(registro)


def test_almacenar_datos_recibidos_oxidonitroso(mocker: MockerFixture):
    registro = "DioxidoNitroso.csv"

    if os.path.isfile(registro):
        os.remove(registro)

    datalogger = Datalogger(config=CONFIG_FILE)
    datalogger.start()

    mocker.serial_port.read_until.side_effect = [
        ACK + b"\x40" + STX + b"123456,125689,123789" + ETX
    ]
    mocker.serial_port.read.side_effect = [b"\x47"]

    mocker.datetime.now.return_value = datetime(2023, 12, 24, 8, 3, 1)
    datalogger._analyzers[0].poll()

    with open(registro, "r") as archivo:
        lineas = archivo.read().splitlines()

    assert len(lineas) == 2
    assert lineas[0] == '"Fecha","Hora","NO2","NO","NOx"'
    assert lineas[1] == '"2023-12-24","08:03:01","123456","125689","123789"'


def test_almacenar_datos_recibidos_ozono(mocker: MockerFixture):
    registro = "Ozono.csv"

    if os.path.isfile(registro):
        os.remove(registro)

    datalogger = Datalogger(config=CONFIG_FILE)
    datalogger.start()

    mocker.serial_port.read_until.side_effect = [
        b"14-00-01 23:04  M000  O3   17.8  PPB   EXT1   1.5   mv   EXT2   0.0   mv   \x0D\x0A"
    ]

    mocker.datetime.now.return_value = datetime(2023, 12, 24, 8, 3, 1)
    datalogger._analyzers[1].poll()

    with open(registro, "r") as archivo:
        lineas = archivo.read().splitlines()

    assert len(lineas) == 2
    assert lineas[0] == '"Fecha","Hora","O3","EXT1","EXT2"'
    assert lineas[1] == '"2023-12-24","08:03:01","17.8 PPB","1.5 mv","0.0 mv"'


def test_publicar_archivo_almacenamiento_diariamente(mocker: MockerFixture):
    registro = "Ozono.csv"
    if os.path.isfile(registro):
        os.remove(registro)

    shutil.rmtree("./ftp")

    datalogger = Datalogger(config=CONFIG_FILE)
    datalogger.start()

    mocker.serial_port.read_until.side_effect = [
        b"14-00-01 23:04  M000  O3   17.8  PPB   EXT1   1.5   mv   EXT2   0.0   mv   \x0D\x0A",
    ]
    mocker.datetime.now.return_value = datetime(2023, 11, 29, 7, 3, 1)
    datalogger._analyzers[1].poll()

    mocker.serial_port.read_until.side_effect = [
        b"14-00-01 23:04  M000  O3   19.8  PPB   EXT1   0.5   mv   EXT2   1.0   mv   \x0D\x0A",
    ]
    mocker.datetime.now.return_value = datetime(2023, 11, 30, 8, 4, 2)
    datalogger._analyzers[1].poll()

    # mocker.datetime.now.return_value = datetime(2023, 12, 1, 9, 5, 3)
    # datalogger._analyzers[1].poll()

    with open("./ftp/Ozono-2023-11.csv", "r") as archivo:
        lineas = archivo.read().splitlines()

    assert len(lineas) == 2
    assert lineas[0] == '"Fecha","Hora","O3","EXT1","EXT2"'
    assert lineas[1] == '"2023-11-29","07:03:01","17.8 PPB","1.5 mv","0.0 mv"'

    with open("Ozono.csv", "r") as archivo:
        lineas = archivo.read().splitlines()

    assert len(lineas) == 3
    assert lineas[0] == '"Fecha","Hora","O3","EXT1","EXT2"'
    assert lineas[1] == '"2023-11-29","07:03:01","17.8 PPB","1.5 mv","0.0 mv"'
    assert lineas[2] == '"2023-11-30","08:04:02","19.8 PPB","0.5 mv","1.0 mv"'


def test_rotar_archivo_almacenamiento_mensualmente(mocker: MockerFixture):
    registro = "Ozono.csv"
    if os.path.isfile(registro):
        os.remove(registro)

    shutil.rmtree("./ftp")

    datalogger = Datalogger(config=CONFIG_FILE)
    datalogger.start()

    mocker.serial_port.read_until.side_effect = [
        b"14-00-01 23:04  M000  O3   17.8  PPB   EXT1   1.5   mv   EXT2   0.0   mv   \x0D\x0A",
    ]
    mocker.datetime.now.return_value = datetime(2023, 11, 29, 7, 3, 1)
    datalogger._analyzers[1].poll()

    mocker.serial_port.read_until.side_effect = [
        b"14-00-01 23:04  M000  O3   19.8  PPB   EXT1   0.5   mv   EXT2   1.0   mv   \x0D\x0A",
    ]
    mocker.datetime.now.return_value = datetime(2023, 11, 30, 8, 4, 2)
    datalogger._analyzers[1].poll()

    mocker.serial_port.read_until.side_effect = [
        b"14-00-01 23:04  M000  O3   15.6  PPB   EXT1   1.2   mv   EXT2   0.7   mv   \x0D\x0A",
    ]
    mocker.datetime.now.return_value = datetime(2023, 12, 1, 9, 5, 3)
    datalogger._analyzers[1].poll()

    with open("./ftp/Ozono-2023-11.csv", "r") as archivo:
        lineas = archivo.read().splitlines()
    assert len(lineas) == 3
    assert lineas[0] == '"Fecha","Hora","O3","EXT1","EXT2"'
    assert lineas[1] == '"2023-11-29","07:03:01","17.8 PPB","1.5 mv","0.0 mv"'
    assert lineas[2] == '"2023-11-30","08:04:02","19.8 PPB","0.5 mv","1.0 mv"'

    with open("Ozono.csv", "r") as archivo:
        lineas = archivo.read().splitlines()
    assert lineas[0] == '"Fecha","Hora","O3","EXT1","EXT2"'
    assert lineas[1] == '"2023-12-01","09:05:03","15.6 PPB","1.2 mv","0.7 mv"'


def test_deshabilitar_filtro_datos_frecuentes(mocker: MockerFixture):
    registro = "Ozono.csv"
    if os.path.isfile(registro):
        os.remove(registro)

    datalogger = Datalogger(config=CONFIG_FILE)

    mocker.datetime.now.return_value = datetime(2023, 12, 24, 8, 2, 0)
    datalogger.start()
    datalogger._analyzers[1].filter_data = 0

    mocker.serial_port.read_until.side_effect = [
        b"14-00-01 23:04  M000  O3   17.8  PPB   EXT1   1.5   mv   EXT2   0.0   mv   \x0D\x0A",
    ]

    mocker.datetime.now.return_value = datetime(2023, 12, 24, 8, 3, 1)
    datalogger._analyzers[1].poll()

    mocker.serial_port.read_until.side_effect = [
        b"14-00-01 23:04  M000  O3   19.8  PPB   EXT1   0.5   mv   EXT2   1.0   mv   \x0D\x0A",
    ]
    mocker.datetime.now.return_value = datetime(2023, 12, 24, 8, 3, 10)
    datalogger._analyzers[1].poll()

    mocker.serial_port.read_until.side_effect = [
        b"14-00-01 23:04  M000  O3   15.6  PPB   EXT1   1.2   mv   EXT2   0.7   mv   \x0D\x0A",
    ]
    mocker.datetime.now.return_value = datetime(2023, 12, 24, 8, 4, 5)
    datalogger._analyzers[1].poll()

    with open(registro, "r") as archivo:
        lineas = archivo.read().splitlines()
    assert len(lineas) == 4
    assert lineas[1] == '"2023-12-24","08:03:01","17.8 PPB","1.5 mv","0.0 mv"'
    assert lineas[2] == '"2023-12-24","08:03:10","19.8 PPB","0.5 mv","1.0 mv"'
    assert lineas[3] == '"2023-12-24","08:04:05","15.6 PPB","1.2 mv","0.7 mv"'


def test_remover_datos_demasiado_frecuentes_ozono(mocker: MockerFixture):
    registro = "Ozono.csv"
    if os.path.isfile(registro):
        os.remove(registro)

    datalogger = Datalogger(config=CONFIG_FILE)

    mocker.datetime.now.return_value = datetime(2023, 12, 24, 8, 2, 0)
    datalogger.start()

    mocker.serial_port.read_until.side_effect = [
        b"14-00-01 23:04  M000  O3   17.8  PPB   EXT1   1.5   mv   EXT2   0.0   mv   \x0D\x0A",
    ]
    mocker.datetime.now.return_value = datetime(2023, 12, 24, 8, 3, 1)
    datalogger._analyzers[1].poll()

    mocker.serial_port.read_until.side_effect = [
        b"14-00-01 23:04  M000  O3   19.8  PPB   EXT1   0.5   mv   EXT2   1.0   mv   \x0D\x0A",
    ]
    mocker.datetime.now.return_value = datetime(2023, 12, 24, 8, 3, 10)
    datalogger._analyzers[1].poll()

    mocker.serial_port.read_until.side_effect = [
        b"14-00-01 23:04  M000  O3   15.6  PPB   EXT1   1.2   mv   EXT2   0.7   mv   \x0D\x0A",
    ]
    mocker.datetime.now.return_value = datetime(2023, 12, 24, 8, 4, 5)
    datalogger._analyzers[1].poll()

    with open(registro, "r") as archivo:
        lineas = archivo.read().splitlines()
    assert len(lineas) == 3
    assert lineas[1] == '"2023-12-24","08:03:01","17.8 PPB","1.5 mv","0.0 mv"'
    assert lineas[2] == '"2023-12-24","08:04:05","15.6 PPB","1.2 mv","0.7 mv"'
