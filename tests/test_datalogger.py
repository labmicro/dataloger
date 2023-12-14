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

import pytest
import paho.mqtt.client as mqtt
import serial

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
    mocker.client_instance = MagicMock()
    mocker.create_client = mocker.patch.object(
        mqtt, "Client", return_value=mocker.client_instance
    )

    mocker.serial_port = MagicMock()
    mocker.init_serial = mocker.patch.object(
        serial, "Serial", return_value=mocker.serial_port
    )


def test_crear_datalogger(mocker: MockerFixture):
    datalogger = Datalogger(config=CONFIG_FILE)
    datalogger.start()

    mocker.create_client.assert_called_once_with(
        clean_session=True, client_id="laboratorio", protocol=4, transport="tcp"
    )
    mocker.client_instance.connect.assert_called_once_with(
        server="test.mosquitto.org", port=8883
    )

    assert mocker.init_serial.call_args_list[0] == call(
        port="/dev/tty.USB1", baudrate=9600
    )
    assert mocker.init_serial.call_args_list[1] == call(
        port="/dev/tty.USB2", baudrate=9600
    )


def test_publicar_datos_recibidos_oxidonitroso(mocker: MockerFixture):
    datalogger = Datalogger(config=CONFIG_FILE)
    datalogger.start()

    mocker.serial_port.read_until.side_effect = [
        ACK + b"\x40" + STX + b"123456,125689,123789" + ETX
    ]
    mocker.serial_port.read.side_effect = [b"\x47"]

    datalogger._analyzers[0].poll()

    assert mocker.client_instance.publish.call_count == 3

    assert mocker.client_instance.publish.call_args_list[0] == call(
        topic="lea/nox/NO2", payload="123456"
    )
    assert mocker.client_instance.publish.call_args_list[1] == call(
        topic="lea/nox/NO", payload="125689"
    )
    assert mocker.client_instance.publish.call_args_list[2] == call(
        topic="lea/nox/NOx", payload="123789"
    )


def test_publicar_datos_recibidos_ozono(mocker: MockerFixture):
    datalogger = Datalogger(config=CONFIG_FILE)
    datalogger.start()

    mocker.serial_port.read_until.side_effect = [
        b"14-00-01 23:04  M000  O3   17.8  PPB   EXT1   1.5   mv   EXT2   0.0   mv   \x0D\x0A"
    ]

    datalogger._analyzers[1].poll()

    assert mocker.client_instance.publish.call_count == 3

    assert mocker.client_instance.publish.call_args_list[0] == call(
        topic="lea/ozono/O3", payload="17.8 PPB"
    )
    assert mocker.client_instance.publish.call_args_list[1] == call(
        topic="lea/ozono/EXT1", payload="1.5 mv"
    )
    assert mocker.client_instance.publish.call_args_list[2] == call(
        topic="lea/ozono/EXT2", payload="0.0 mv"
    )
