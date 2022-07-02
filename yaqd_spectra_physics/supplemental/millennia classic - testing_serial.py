import serial
import time
from yaqd_core import aserial
import asyncio

mil = aserial.ASerial("COM7", baudrate=9600, xonxoff=True)
mil.timeout=0.1
# mil = serial.Serial("COM7", baudrate=9600, xonxoff=True, timeout=2)

start = time.time()
try:
    # mil.write("?P\r".encode())  #  b"4.04W\n"
    mil.write("?IDN\r".encode())  #  b'Spectra Physics Lasers,Millennia V,4.11,0\n'
    # mil.write("?M\r".encode())  # b'1\n'
    # mil.write("?EC\r".encode())  #  b'0e\n'
    # mil.write("?C%\r".encode())  # b'68.6%\n'
    # mil.write("?C1\r".encode())  # b'23.02A1\n'
    # mil.write("?H\r".encode())  # b'\x01\x03\x01\x03\x01\x03\x01\x03\x01\x03\x01\x03\x01\x03\x01\x03\n'
    # mil.write("?STB\r".encode())  # b'195\n'
    # TODO: put status into state (laser on, check for errors)
    power = mil.read_until()
    print(power)
finally:
    mil.close()
