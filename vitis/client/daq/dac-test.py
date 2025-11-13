from dac import DAC
from daq import DAQ
import h5py
from time import sleep
import numpy as np
from functools import partial
import math

dac_channel = 1

steps = 10000


def collect_data(daq, dac_channel, file):
    daq.connect()
    while True:
        restart = False
        row = []

        buffer = daq.download_frame()
        words = daq.unpack_buffer(buffer)[0]
        dac_output = dac.voltage
        row.append(dac_output)

        readings = []
        for i in range(0, len(words), daq.channels):
            code = words[i + dac_channel]
            if not daq.pll_settled(code):
                print("PLL IS NOT LOCKED")
                restart = True
                break

            if not daq.no_chip_error(code):
                print("CHIP ERROR")
                restart = True
                break

            adc_reading = daq.convert_to_voltage(code)
            readings.append(adc_reading)

        if restart:
            continue

        mean = sum(readings) / len(readings)
        std = float(np.std(readings, ddof=1))
        se = std / math.sqrt(len(readings))

        row.extend([mean, se])

        print(row)

        voltages = np.array(row, dtype=np.float32)
        old_n = data_ds.shape[0]
        new_n = old_n + voltages.shape[0]
        data_ds.resize(new_n, axis=0)
        data_ds[old_n:new_n] = voltages
        file.flush()
        break
    daq.disconnect()


file_name = "dac-test.hdf5"

dac = DAC(
    voltage_range=(-3.9, 3.9),
    reference_voltage=5,
    resolution=20,
    serial_port="/dev/ttyACM1",
)

dac.initialize()

daq = DAQ()


try:
    with h5py.File(file_name, "w", libver="latest") as file:
        data_ds = file.create_dataset(
            "data", shape=(0, 3), maxshape=(None, 3), chunks=(1, 3), dtype="float32"
        )

        file.swmr_mode = True

        counter = 0
        for i in range(0, 1 << dac.resolution, steps):
            if dac.set_voltage(i) == dac.voltage:
                print(f"Set voltage to {dac.voltage}")
                sleep(1)
                collect_data(daq, dac_channel, file)
            else:
                print(
                    f"Could not set voltage to {dac.convert_hex_to_voltage(i)} V (Code: {hex(i)})"
                )


except KeyboardInterrupt:
    print("Intterupted by user")

finally:
    dac.close()
