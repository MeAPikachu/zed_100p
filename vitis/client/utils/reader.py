import h5py
import plotly.express as px
from plotly.subplots import make_subplots
import plotly.graph_objects as go
import numpy as np
from scipy.signal import decimate


class Reader:
    def __init__(
        self, file_name, samples=1024 * 20, channels=4, header=0, dtype="float32"
    ):
        self.file_name = file_name
        self.h5 = None
        self.dset = None
        self.samples = samples
        self.channels = channels
        self.headers = header
        self.dtype = dtype
        self.current_index = 0

    def open(self):
        self.h5 = h5py.File(self.file_name, "r", libver="latest", swmr=True)
        self.dset = self.h5["data"]

    def live_view_data(self):
        self.dset.refresh()
        num_chunks = self.dset.shape[0] // self.dset.chunks[0]
        start_index = 0
        if num_chunks > 10:
            start_index = self.dset.shape[0] - 10 * self.dset.chunks[0]
            end_index = self.dset.shape[0] - 5 * self.dset.chunks[0]
        else:
            end_index = num_chunks * self.dset.chunks[0]
        indices = np.arange(start=start_index, stop=end_index)
        sliced_chunks = self.dset[start_index:end_index]
        return indices, sliced_chunks

    def overview_data(self):
        self.dset.refresh()
        num_chunks = self.dset.shape[0] // self.dset.chunks[0]

        if num_chunks > 10:
            end_index = self.dset.shape[0] - 5 * self.dset.chunks[0]
        else:
            end_index = num_chunks * self.dset.chunks[0]
        indices = np.arange(start=0, stop=end_index)
        sliced_chunks = self.dset[0:end_index]
        return indices, sliced_chunks

    def close(self):
        try:
            self.h5.close()
        except:
            print("Could not close file")


class DAC_Reader:
    def __init__(self, file_name, dataset_name="data", header=0, dtype="float32"):
        self.file_name = file_name
        self.dataset_name = dataset_name
        self.header = header
        self.dtype = dtype

        self.h5 = None
        self.dset = None

    def open(self):
        self.h5 = h5py.File(self.file_name, "r", libver="latest", swmr=True)
        self.dset = self.h5[self.dataset_name]

    def live_view_data(self, look_back_chunks: int = 1000, lag_samples: int = 2):
        self.dset.refresh()

        chunk_size = self.dset.chunks[0]
        total_samples = self.dset.shape[0]
        num_chunks = total_samples // chunk_size

        if num_chunks > look_back_chunks:
            start = total_samples - look_back_chunks * chunk_size
        else:
            start = 0

        end = max(start, total_samples - lag_samples)

        indices = np.arange(start, end)

        block = self.dset[start:end]

        dac = block[:, 0]
        adc = block[:, 1]
        se = block[:, 2]

        return dac, adc, se

    def overview_data(self):
        self.dset.refresh()
        chunk_size = self.dset.chunks[0]
        total = self.dset.shape[0]
        num_chunks = total // chunk_size

        if num_chunks > 10:
            end = total - 5 * chunk_size
        else:
            end = total

        indices = np.arange(0, end)
        block = self.dset[0:end]
        dac = block[:, 0]
        adc = block[:, 1]
        se = block[:, 2]
        return dac, adc, se

    def close(self):
        if self.h5 is not None:
            try:
                self.h5.close()
            except Exception as e:
                print(f"Warning: could not close file: {e}")


if __name__ == "__main__":
    test = Reader("2025-07-15-01-02-33.h5")
    test.open()
    test.overview_data()

    while True:
        test.dset.refresh()
        subplot_rows = 2
        subplot_cols = 2
        indices = np.arange(test.dset.shape[0])

        decimation_factor = 1

        print(test.dset[:])

        fig = make_subplots(rows=subplot_rows, cols=subplot_cols)
        """
        for subplot_row in range(1, subplot_rows + 1):
            for subplot_col in range(1, subplot_cols + 1):
                downsampled_signal = decimate(test.dset[:, 2 * (subplot_row - 1) + (subplot_col-1)], decimation_factor)
                downsampled_indices = indices[::decimation_factor]
                fig.add_trace(
                    go.Scattergl(x=downsampled_indices, y=downsampled_signal),
                    row=subplot_row, 
                    col=subplot_col
                )
        fig.show()
        """
        break

    test.close()
