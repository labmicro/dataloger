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
import serial

from analyzers import Analyzer, FrancesO3, EcoPhysicsNOx
from pytest_mock import MockerFixture
from unittest.mock import MagicMock


STX = b"\x02"
ETX = b"\x03"
ACK = b"\x06"
NAK = b"\x15"


@pytest.fixture(autouse=True)
def mock_port_port_init(mocker):
    mocker.serial_port = MagicMock()
    mocker.init_serial = mocker.patch.object(
        serial, "Serial", return_value=mocker.serial_port
    )


def test_crear_Analyzer(mocker: MockerFixture):
    analyzer = Analyzer("NO", port="/dev/tty.USB", publisher=None, topic="")
    mocker.init_serial.assert_called_once_with(port="/dev/tty.USB", baudrate=9600)


def test_analizar_O3(mocker: MockerFixture):
    mocker.serial_port.read_until.side_effect = [
        b"14-00-01 23:04  M000  O3   17.8  PPB   EXT1   1.5   mv   EXT2   0.0   mv   \x0D\x0A"
    ]
    esperado = {
        "O3": "17.8 PPB",
        "EXT1": "1.5 mv",
        "EXT2": "0.0 mv",
    }
    analyzer = FrancesO3("O3", port="/dev/tty.USB", publisher=None, topic="")
    mocker.init_serial.assert_called_once_with(port="/dev/tty.USB", baudrate=9600)

    resultado = analyzer.poll()
    assert esperado == resultado


def test_analizar_NO2(mocker: MockerFixture):
    esperado = {"NO2": "123456", "NO": "125689", "NOx": "123789"}
    mocker.serial_port.read_until.side_effect = [
        ACK + b"\x40" + STX + b"123456,125689,123789" + ETX
    ]
    mocker.serial_port.read.side_effect = [b"\x47"]

    analyzer = EcoPhysicsNOx(
        "NO", address=1, port="/dev/tty.USB", publisher=None, topic=""
    )
    resultado = analyzer.poll()
    mocker.serial_port.write.assert_called_once_with(STX + b"01RD3" + ETX + b"\x25")
    assert resultado == esperado
