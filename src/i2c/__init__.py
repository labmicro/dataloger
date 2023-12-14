#!/usr/bin/env python3
# encoding: utf-8

from .. import real

if real():
    from .smbus import SMBus
else:
    class SMBus(object):
        def __init__(self, bus=None):
            pass

        def read_byte_data(self, addr, cmd):
            return bytes(1)

        def read_i2c_block_data(self, addr, cmd, length=32):
            return bytes(length)

        def write_byte_data(self, addr, cmd, val):
            pass

bus = SMBus(0)

def leer(dispositivo: int, direccion: int) -> int:
    byte = bus.read_byte_data(dispositivo, direccion)
    return byte

def leer_bloque(dispositivo: int, direccion: int, cantidad: int) -> list:
    resultado = bus.read_i2c_block_data(dispositivo, direccion, cantidad)
    return resultado

def escribir(dispositivo: int, direccion: int, dato: int):
    bus.write_byte_data(dispositivo, direccion, dato)
