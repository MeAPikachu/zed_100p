from dash import Dash, dcc, html, Input, Output, callback, exceptions
import dash_daq as daq
import plotly.express as px
import h5py
from Plotting import Live_View, Overview, DacTestLiveView

######################
#       Config       #
######################
file_name = "dac-test.hdf5"
# voltage_data_file = f = h5py.File(file_name, "r", libver="latest", swmr=True)


app = Dash(__name__, suppress_callback_exceptions=True)

app.layout = html.Div(
    [
        dcc.Tabs(
            id="dashboard-tabs",
            value="live-view",
            children=[
                dcc.Tab(label="Live View", value="live-view"),
            ],
        ),
        html.Div(id="dashboard-content"),
    ]
)


@app.callback(Output("dashboard-content", "children"), Input("dashboard-tabs", "value"))
def render_dashboard_content(tab):
    if tab == "control-panel":
        return html.Div(
            [
                html.Label("ODR (Hz)"),
                dcc.Input(placeholder="Enter a value...", type="number", value=""),
                html.Button("Submit", id="button-example-1"),
                html.Br(),
                html.Br(),
                html.Button("Start Sampling", id="button-example-2"),
            ]
        )
    else:
        return html.Div(
            [
                dcc.Graph(id="live-view-graphs"),
                dcc.Interval(id="live-view-interval", interval=1 * 1000, n_intervals=0),
            ]
        )


@app.callback(
    Output("live-view-graphs", "figure"),
    Input("live-view-interval", "n_intervals", allow_optional=True),
    prevent_initial_call=True,
)
def render_live_view(n_intervals):
    live_view = DacTestLiveView(file_name)
    return live_view.create_live_plots()


@app.callback(
    Output("overview-graphs", "figure"),
    Input("overview-interval", "n_intervals", allow_optional=True),
    prevent_initial_call=True,
)
def render_overview(n_intervals):
    overview = Overview(file_name, 1000)
    return overview.create_overview_plots()


if __name__ == "__main__":
    app.run(debug=False)
