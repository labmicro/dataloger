#!/usr/bin/env python3
# encoding: utf-8

from datetime import datetime, timedelta
from .. import i2c

REGISTRO_SEGUNDOS = 0x00
REGISTRO_MINUTOS = 0x01
REGISTRO_HORAS = 0x02
REGISTRO_DIA_SEMANA = 0x03
REGISTRO_DIAS = 0x04
REGISTRO_MESES = 0x05
REGISTRO_ANOS = 0x06
REGISTRO_CONTROL = 0x07
REGISTRO_DATOS = 0x08

APAGADO_MINUTOS = 0x18
APAGADO_HORAS = 0x19
APAGADO_DIAS = 0x1A
APAGADO_MESES = 0x1B

ENCENDIDO_MINUTOS = 0x1C
ENCENDIDO_HORAS = 0x1D
ENCENDIDO_DIAS = 0x1E
ENCENDIDO_MESES = 0x1F

DS1307 = 'DS1307'
MCP7940N ='MCP7940N'

try:
    DIRECCION = 0x68
    i2c.leer(DIRECCION, REGISTRO_SEGUNDOS)
    MODELO = DS1307
except:
    DIRECCION = 0x6F
    i2c.leer(DIRECCION, REGISTRO_SEGUNDOS)
    MODELO = MCP7940N

def habilitado() -> bool:
    if MODELO == MCP7940N:
        return (i2c.leer(DIRECCION, REGISTRO_DIA_SEMANA) & 0x20) == 0x20
    else:
        return (i2c.leer(DIRECCION, REGISTRO_SEGUNDOS) & 0x80) == 0x00

def fecha_actual() -> datetime:
    def from_bdc(numero: int) -> int:
        return int('%x' % numero)

    resultado = None
    if habilitado():
        segundo = from_bdc(i2c.leer(DIRECCION, REGISTRO_SEGUNDOS) & 0x7F)
        minuto = from_bdc(i2c.leer(DIRECCION, REGISTRO_MINUTOS))
        hora = from_bdc(i2c.leer(DIRECCION, REGISTRO_HORAS) & 0x3F)
        dia = from_bdc(i2c.leer(DIRECCION, REGISTRO_DIAS))
        mes = from_bdc(i2c.leer(DIRECCION, REGISTRO_MESES) & 0x1F)
        ano = 2000 + from_bdc(i2c.leer(DIRECCION, REGISTRO_ANOS))
        resultado = datetime(ano, mes, dia, hora, minuto, segundo)
    return resultado


def actualizar_fecha(fecha: datetime):
    def to_bcd(numero: int) -> int:
        return int(str(numero % 100), 16)

    valor = to_bcd(fecha.second)
    if MODELO == MCP7940N:
        valor |= 0x80
    i2c.escribir(DIRECCION, REGISTRO_SEGUNDOS, valor)
    i2c.escribir(DIRECCION, REGISTRO_MINUTOS, to_bcd(fecha.minute))
    i2c.escribir(DIRECCION, REGISTRO_HORAS, to_bcd(fecha.hour) & 0x3F)
    i2c.escribir(DIRECCION, REGISTRO_DIAS, to_bcd(fecha.day))

    valor = to_bcd(fecha.isoweekday())
    if MODELO == MCP7940N:
        valor |= 0x08
    i2c.escribir(DIRECCION, REGISTRO_DIA_SEMANA, valor)
    i2c.escribir(DIRECCION, REGISTRO_MESES, to_bcd(fecha.month))
    i2c.escribir(DIRECCION, REGISTRO_ANOS, to_bcd(fecha.year))

def leer_datos(inicio: int = 0, cantidad: int = 56):
    resultado = bytearray(b'')
    for indice in range(inicio, cantidad):
        resultado.append(i2c.leer(DIRECCION, REGISTRO_DATOS + indice))
    return resultado


def actualizar_datos(datos: bytearray, inicio: int = 0):
    for indice in range(len(datos)):
        i2c.escribir(DIRECCION, REGISTRO_DATOS + inicio + indice, datos[indice])


def ultimo_reinicio() -> dict:
    def from_bdc(numero: int) -> int:
        return int('%x' % numero)

    resultado = dict()
    if (MODELO == MCP7940N) and ((i2c.leer(DIRECCION, REGISTRO_DIA_SEMANA) & 0x10) != 0x00):
        minuto = from_bdc(i2c.leer(DIRECCION, ENCENDIDO_MINUTOS))
        hora = from_bdc(i2c.leer(DIRECCION, ENCENDIDO_HORAS) & 0x3F)
        dia = from_bdc(i2c.leer(DIRECCION, ENCENDIDO_DIAS))
        mes = from_bdc(i2c.leer(DIRECCION, ENCENDIDO_MESES) & 0x1F)
        ano = 2000 + from_bdc(i2c.leer(DIRECCION, REGISTRO_ANOS))
        resultado['encendido'] = datetime(ano, mes, dia, hora, minuto)

        minuto = from_bdc(i2c.leer(DIRECCION, APAGADO_MINUTOS))
        hora = from_bdc(i2c.leer(DIRECCION, APAGADO_HORAS) & 0x3F)
        dia = from_bdc(i2c.leer(DIRECCION, APAGADO_DIAS))
        mes = from_bdc(i2c.leer(DIRECCION, APAGADO_MESES) & 0x1F)
        ano = 2000 + from_bdc(i2c.leer(DIRECCION, REGISTRO_ANOS))
        resultado['apagado'] = datetime(ano, mes, dia, hora, minuto)

        if resultado['encendido'] < resultado['apagado']:
            ano = 2000 + from_bdc(i2c.leer(DIRECCION, REGISTRO_ANOS)) - 1
            resultado['apagado'] = datetime(ano, mes, dia, hora, minuto)

    return resultado


def borrar_reinicio() -> None:
    valor = i2c.leer(DIRECCION, REGISTRO_DIA_SEMANA)
    i2c.escribir(DIRECCION, REGISTRO_DIA_SEMANA, valor & 0xEF)

