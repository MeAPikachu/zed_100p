import math
from time import sleep
import serial
import numpy as np
import h5py


class DAC:
    def __init__(
        self,
        voltage_range,
        reference_voltage=5,
        resolution=20,
        serial_port="/dev/ttyACM0",
    ):
        self.voltage_range = voltage_range
        self.reference_voltage = reference_voltage
        self.resolution = resolution
        self.lsb = 2 * self.reference_voltage / math.pow(2, self.resolution)
        self.baudrate = 115200
        self.serial_port = serial_port
        self.serial = None
        self.voltage = None
        self.raw_voltage = None

    def convert_voltage_to_hex(self, voltage):
        min_voltage, max_voltage = self.voltage_range
        if not (min_voltage <= voltage <= max_voltage):
            raise ValueError(
                f"Voltage {voltage} V out of range [{min_voltage}, {max_voltage}]"
            )

        signed = int(round(voltage / self.lsb))
        max_signed = (1 << (self.resolution - 1)) - 1
        min_signed = -(1 << (self.resolution - 1))
        signed = max(min_signed, min(signed, max_signed))

        raw = signed & ((1 << self.resolution) - 1)
        return raw

    def convert_hex_to_voltage(self, hex_code):
        sign_bit = (hex_code >> 19) & 0x1
        if sign_bit:
            hex_code = hex_code - (1 << self.resolution)
        raw_voltage = hex_code * self.lsb
        voltage = raw_voltage

        if raw_voltage > self.reference_voltage:
            voltage = raw_voltage - self.reference_voltage

        return voltage

    def initialize(self):
        try:
            self.serial = serial.Serial(
                port=self.serial_port, baudrate=self.baudrate, timeout=1
            )
            print("Initialized serial communication with DAC")
            self.set_voltage(0x0)
            print("Set voltage to 0 V")
            return True

        except serial.SerialException as e:
            raise ConnectionError(f"Failed to open {self.serial_port}: {e}")

    def read_voltage(self):
        cmd = f"drr 1\n"
        return self.send_command(cmd)

    def set_voltage(self, hex_code):
        if self.validate_voltage(hex_code):
            cmd = f"drw 1 {hex(hex_code).lower()}\n"
            self.send_command(cmd)
            self.voltage = self.parse_response(self.read_voltage())
            self.raw_voltage = hex_code
            return self.voltage
        else:
            return f"{hex(hex_code)} ({self.convert_hex_to_voltage(hex_code)}) is out of range"

    def validate_voltage(self, hex_code):
        min_voltage, max_voltage = self.voltage_range
        if min_voltage < self.convert_hex_to_voltage(hex_code) < max_voltage:
            return True
        else:
            return False

    def parse_response(self, response):
        hex_code = int(str(response).replace("Register 0x1 = ", ""), 16)
        voltage = self.convert_hex_to_voltage(hex_code)
        return voltage

    def send_command(self, command):
        if not self.serial or not self.serial.is_open:
            raise ConnectionError("Serial port not initialized or already closed.")
        data = command.encode("ascii")
        self.serial.write(data)
        self.serial.flush()

        response_line = None
        while True:
            raw = self.serial.readline()
            if not raw:
                break

            line = raw.decode("ascii", errors="ignore").strip()

            if not line:
                continue

            if line == ">":
                break

            response_line = line
        return response_line

    def close(self):
        if self.serial and self.serial.is_open:
            self.serial.close()
        return True


if __name__ == "__main__":
    dac = DAC((-4, 4), 5, 20, "/dev/ttyACM1")
    dac.initialize()
    # print(dac.set_voltage(dac.convert_voltage_to_hex(1)))
    dac.set_voltage(dac.convert_voltage_to_hex(2))
    # dac.scan(5, print)
    dac.close()
