import plotly.express as px
from plotly.subplots import make_subplots
import plotly.graph_objects as go
import numpy as np
from scipy.signal import decimate
from client.utils.reader import Reader, DAC_Reader
import matplotlib.pyplot as plt


class Live_View:
    def __init__(self, file_name):
        self.file_name = file_name
        self.subplot_rows = 2
        self.subplot_cols = 2

    def create_live_plots(self):
        reader = Reader(self.file_name)
        reader.open()
        indices, data = reader.live_view_data()
        decimation_factor = 1

        if data.shape[0] == 0:
            reader.close()
            return go.Figure().update_layout(title="No data yet")

        fig = make_subplots(rows=self.subplot_rows, cols=self.subplot_cols)

        for subplot_row in range(1, self.subplot_rows + 1):
            for subplot_col in range(1, self.subplot_cols + 1):
                downsampled_signal = decimate(
                    data[:, 2 * (subplot_row - 1) + (subplot_col - 1)],
                    decimation_factor,
                )
                downsampled_indices = indices[::decimation_factor]
                fig.add_trace(
                    go.Scattergl(x=downsampled_indices, y=downsampled_signal),
                    row=subplot_row,
                    col=subplot_col,
                )
        reader.close()
        return fig

    def create_live_plot_aggregate(self):
        reader = Reader(self.file_name)
        reader.open()
        indices, data = reader.live_view_data()
        decimation_factor = 1

        if data.shape[0] == 0:
            reader.close()
            return go.Figure().update_layout(title="No data yet")

        fig = go.Figure()

        num_traces = data.shape[1]
        for ch in range(num_traces):

            downsampled_signal = decimate(data[:, ch], decimation_factor)
            downsampled_indices = indices[::decimation_factor]

            fig.add_trace(
                go.Scattergl(
                    x=downsampled_indices, y=downsampled_signal, name=f"Channel {ch+1}"
                )
            )

        fig.update_layout(
            title="Live Data (All Channels)",
            xaxis_title="Sample Index",
            yaxis_title="Amplitude",
            legend_title="Channel",
            uirevision="liveview",
        )

        reader.close()
        return fig


class Overview:
    def __init__(self, file_name, decimation_factor):
        self.file_name = file_name
        self.subplot_rows = 2
        self.subplot_cols = 2
        self.decimation_factor = decimation_factor

    def create_overview_plots(self):
        reader = Reader(self.file_name)
        reader.open()
        indices, data = reader.overview_data()
        if data.shape[0] == 0:
            reader.close()
            return go.Figure().update_layout(title="No data yet")

        decimation_factor = self.decimation_factor

        fig = make_subplots(rows=self.subplot_rows, cols=self.subplot_cols)

        for subplot_row in range(1, self.subplot_rows + 1):
            for subplot_col in range(1, self.subplot_cols + 1):
                downsampled_signal = decimate(
                    data[:, 2 * (subplot_row - 1) + (subplot_col - 1)],
                    decimation_factor,
                )
                downsampled_indices = indices[::decimation_factor]
                fig.add_trace(
                    go.Scattergl(x=downsampled_indices, y=downsampled_signal),
                    row=subplot_row,
                    col=subplot_col,
                )
        reader.close()

        return fig


class DacTestLiveView:
    def __init__(self, file_name, decimation_factor=1):
        self.file_name = file_name
        self.decimation_factor = decimation_factor

    def fit(self, dac_ds, adc_ds):
        slope, intercept = np.polyfit(dac_ds, adc_ds, 1)
        return slope, intercept

    def create_live_plots(self):
        reader = DAC_Reader(self.file_name)
        reader.open()
        dac, adc, se = reader.live_view_data()
        reader.close()

        # no raw data at all?  show placeholder
        if len(dac) == 0:
            return go.Figure().update_layout(title="No data yet")

        # downsample
        df = max(1, self.decimation_factor)
        if df > 1 and len(dac) > 27:
            dac_ds = decimate(dac, df)
            adc_ds = decimate(adc, df)
            se_ds = decimate(se, df)
        else:
            dac_ds = dac[::df]
            adc_ds = adc[::df]
            se_ds = se[::df]

        order = np.argsort(dac_ds)

        dac_ds = dac_ds[order]
        adc_ds = adc_ds[order]
        se_ds = se_ds[order]
        trace = go.Scattergl(
            x=dac_ds,
            y=adc_ds,
            customdata=se_ds,
            mode="markers+lines",
            name="ADC vs DAC",
            marker=dict(size=1),
            error_y=dict(type="data", array=se_ds, visible=True, width=1),
            hovertemplate=(
                "DAC: %{x:.6f} V<br>"
                "ADC: %{y:.6f} V<br>"
                "SEM: %{customdata:.6f} V"
                "<extra></extra>"
            ),
        )

        if len(dac_ds) < 2:
            fig = go.Figure([trace])
            fig.update_layout(
                title=f"ADC vs DAC (N = {len(dac_ds)})",
                xaxis_title="DAC Voltage (V)",
                yaxis_title="ADC Voltage (V)",
                showlegend=False,
                uirevision="liveview",
            )
            return fig

        slope, intercept = self.fit(dac_ds, adc_ds)
        x_fit = np.array([dac_ds.min(), dac_ds.max()])
        y_fit = slope * x_fit + intercept
        fit_trace = go.Scatter(
            x=x_fit,
            y=y_fit,
            mode="lines",
            name=f"Fit: y={slope:.4f}x+{intercept:.4f}",
            line=dict(dash="dash"),
        )

        fig = go.Figure([trace, fit_trace])
        fig.update_layout(
            title=f"ADC vs DAC (N = {len(dac_ds)})",
            xaxis_title="DAC Voltage (V)",
            yaxis_title="ADC Voltage (V)",
            showlegend=True,
            uirevision="liveview",
        )

        # … add your annotations/residual‐stats here …

        return fig


if __name__ == "__main__":
    import h5py

    def create_overview_plots(file_name, decimation_factor=1):
        with h5py.File(file_name, "r", libver="latest", swmr=True) as f:
            dset = f["data"]
            num_chunks = dset.shape[0] // dset.chunks[0]
            if num_chunks > 10:
                end_index = dset.shape[0] - 5 * dset.chunks[0]
            else:
                end_index = num_chunks * dset.chunks[0]

            indices = np.arange(0, end_index)
            data = dset[0:end_index]

        fig, axes = plt.subplots(2, 2, figsize=(12, 8))
        axes = axes.flatten()

        for i in range(4):
            downsampled_signal = decimate(data[:, i], decimation_factor)
            downsampled_indices = indices[::decimation_factor]
            axes[i].plot(downsampled_indices, downsampled_signal)
            axes[i].set_title(f"Channel {i+1}")
            axes[i].set_xlabel("Sample Index")
            axes[i].set_ylabel("Amplitude")
            axes[i].grid(True)

        plt.tight_layout()
        plt.show()

    create_overview_plots("sine_data.h5")
