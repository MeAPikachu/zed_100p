import serial.tools.list_ports

ports = [p.device for p in serial.tools.list_ports.comports()]
if '/dev/ttyACM0' in ports:
    print('/dev/ttyACM0 is available as a serial port')
else:
    print('/dev/ttyACM0 not found among:', ports)
