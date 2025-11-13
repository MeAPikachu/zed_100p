import os
import socket
import struct
import h5py
import numpy as np
import signal, sys
import time
import math

"""
@todo Update FPGA to output timestamps
@todo Separate logic for polling data and saving data into separate functions.
@todo AD4134 currently uses hard-coded parameters. Add configurable parameters 
      (e.g. ODR) for AD4134 before collecting data. ODR is currently configured
      in lines 171 and 179 of main.c. Update FPGA code to listen for incoming
      Ethernet packets with config information.
@todo Support for detecting and logging PLL lock and chip error
@todo Add timestamps for each frame and reconstruction
@todo Increase amount of data transferred in Ethernet buffer. 
@todo Real-time plotting
"""


class DAQ_UDP:

    BYTES_PER_SAMPLE = 4
    LSB = 4.096 / (2**23)
    TICKS_PER_SECOND = 666_666_687

    def __init__(
        self,
        board_ip: str = "192.168.1.10",
        port: int = 12345,
        samples: int = 1024 * 20,
        channels: int = 4,
        timestamp_header: int = 0,
        filename: str = "test.hdf5",
        limit_frames: bool = False,
        num_frames: int = 10,
    ):
        self.board_ip = board_ip
        self.port = port
        self.samples = samples
        self.channels = channels
        self.timestamp_header = timestamp_header
        self.filename = filename
        self.socket = None
        self.connected = False
        self.frame_count = 0
        self.limit_frames = limit_frames
        self.num_frames = num_frames
        self.timestamp = 0

        # Frame size in bytes
        self.frame_size = (
            self.samples * self.channels + self.timestamp_header
        ) * self.BYTES_PER_SAMPLE

    def init_hdf5(self):
        self.file = h5py.File(self.filename, "w", libver="latest")
        self.data_ds = self.file.create_dataset(
            "data",
            shape=(0, self.channels),
            maxshape=(None, self.channels),
            chunks=(self.samples, self.channels),
            dtype="float64",
        )

        self.file.swmr_mode = True

        if self.timestamp_header:
            self.time_ds = self.file.create_dataset(
                "time",
                shape=(0, 1),
                maxshape=(None, 1),
                chunks=(self.samples, 1),
                dtype="float64",
            )
        print(f"Writing to '{self.filename}'...")

    @staticmethod
    def pll_settled(code: int) -> int:
        pll_lock_mask = 0x00000040
        result = (code & pll_lock_mask) >> 6
        if result == 1:
            return True
        else:
            return False

    @staticmethod
    def no_chip_error(code: int) -> int:
        pll_lock_mask = 0x00000080
        result = (code & pll_lock_mask) >> 7
        if result == 1:
            return True
        else:
            return False

    @staticmethod
    def convert_to_voltage(code: int) -> float:
        raw24 = (code & 0xFFFFFF00) >> 8
        if raw24 & 0x800000:
            raw24 -= 1 << 24
        return raw24 * DAQ_UDP.LSB

    @staticmethod
    def convert_voltage_to_code(voltage: float) -> int:
        raw24 = int(round(voltage / DAQ_UDP.LSB))
        if raw24 < 0:
            raw24 += 1 << 24
        return raw24

    @staticmethod
    def convert_to_timestamp_sec(header: tuple[int, int]) -> float:
        hi, lo = header
        ticks = (hi << 32) | lo
        return ticks / DAQ_UDP.TICKS_PER_SECOND

    def connect(self):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.bind(("0.0.0.0", self.port))
        self.connected = True
        # print(f"Connected to {self.board_ip}:{self.port}")

    def disconnect(self):
        if self.connected:
            # print("Shutting down socket.")
            self.socket.close()
            # print("Disconnected from socket")
            self.connected = False
        else:
            print("DAQ is already disconnected")

    def _on_term(self, signum, frame):
        raise SystemExit

    def download_frame(self):

        buffer, addr = self.socket.recvfrom(self.samples * self.channels * 4)
        """
        buffer = b""
        while len(buffer) < self.frame_size:
            chunk = self.socket.recv(self.frame_size - len(buffer))
            if not chunk:
                print("Connection closed by remote.")
                return
            buffer += chunk
        """
        return buffer

    def unpack_buffer(self, buffer):
        offset = self.timestamp_header * self.BYTES_PER_SAMPLE
        raw = buffer[offset:]
        words = struct.unpack(f"<{self.samples * self.channels}I", raw)
        return words, offset

    def write_data(self, voltages, buffer, offset):
        # Append to dataset
        old_n = self.data_ds.shape[0]
        new_n = old_n + voltages.shape[0]
        self.data_ds.resize(new_n, axis=0)
        self.data_ds[old_n:new_n] = voltages

        # Handle timestamps
        if self.timestamp_header:
            # Unpack header words
            hdr_words = struct.unpack(f"<{self.timestamp_header}I", buffer[:offset])
            ts = self.convert_to_timestamp_sec(tuple(hdr_words))
            self.time_ds.resize(new_n, axis=0)
            self.time_ds[old_n:new_n, 0] = ts

        self.file.flush()
        self.frame_count += 1
        print(f"Frame {self.frame_count} stored (total rows: {new_n})")

    def run(self, stop_event=None):
        signal.signal(signal.SIGTERM, self._on_term)
        if not self.connected:
            self.connect()

        try:

            while stop_event is None or not stop_event.is_set():

                if self.timestamp != 0:
                    current_timestamp = time.time_ns()
                    difference = current_timestamp - self.timestamp
                    print(
                        f"Time since last time stamp: {difference * math.pow(10, -9)} s"
                    )
                    self.timestamp = current_timestamp
                else:
                    self.timestamp = time.time_ns()

                if self.limit_frames and self.frame_count == self.num_frames:
                    break
                download_start_timestamp = time.time_ns()
                buffer = self.download_frame()

                words, offset = self.unpack_buffer(buffer)
                # print(words)
                # raise KeyboardInterrupt

                # Convert to voltages
                rows = []
                for i in range(0, len(words), self.channels):
                    row = []
                    for c in range(self.channels):
                        code = words[i + c]
                        if not self.pll_settled(code):
                            print("PLL IS NOT LOCKED")
                        if not self.no_chip_error(code):
                            print("CHIP ERROR")
                        row.append(self.convert_to_voltage(code))
                    rows.append(row)

                voltages = np.array(rows, dtype=np.float64)
                print(voltages)
                self.write_data(voltages, buffer, offset)
                print(f"Download time: {time.time_ns() - download_start_timestamp} ns")

        except KeyboardInterrupt:
            print("\nInterrupted by user.")

        except SystemExit:
            print("\nInterrupted by terminate (SIGTERM)")
        finally:
            self.disconnect()


if __name__ == "__main__":
    daq = DAQ_UDP(
        samples=256,
        filename="continuous-offload.hdf5",
        limit_frames=True,
        num_frames=6,
    )
    code = 0x00000020
    print(bin(code))
    print(daq.pll_settled(code))
    daq.init_hdf5()
    daq.run()
