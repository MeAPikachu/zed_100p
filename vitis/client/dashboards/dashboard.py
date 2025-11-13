from dash import Dash, dcc, html, Input, Output, callback, exceptions
import dash_daq as daq
import plotly.express as px
import h5py
from client.utils.plotting import Live_View, Overview

######################
#       Config       #
######################


def create_dashboard(file_name="test.hdf5"):
    app = Dash(__name__, suppress_callback_exceptions=True)

    app.layout = html.Div(
        [
            dcc.Tabs(
                id="dashboard-tabs",
                value="control-panel",
                children=[
                    dcc.Tab(label="Control Panel", value="control-panel"),
                    dcc.Tab(label="Live View", value="live-view"),
                ],
            ),
            html.Div(id="dashboard-content"),
        ]
    )

    @app.callback(
        Output("dashboard-content", "children"), Input("dashboard-tabs", "value")
    )
    def render_dashboard_content(tab):
        if tab == "control-panel":
            return html.Div(
                [
                    html.H1("Not Functional"),
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
                    html.P("Test 1"),
                    dcc.Graph(id="live-view-graphs"),
                    dcc.Interval(
                        id="live-view-interval", interval=1 * 1000, n_intervals=0
                    ),
                ]
            )

    @app.callback(
        Output("live-view-graphs", "figure"),
        Input("live-view-interval", "n_intervals", allow_optional=True),
        prevent_initial_call=True,
    )
    def render_live_view(n_intervals):
        live_view = Live_View(file_name)
        return live_view.create_live_plot_aggregate()

    @app.callback(
        Output("overview-graphs", "figure"),
        Input("overview-interval", "n_intervals", allow_optional=True),
        prevent_initial_call=True,
    )
    def render_overview(n_intervals):
        overview = Overview(file_name, 1000)
        return overview.create_overview_plots()

    app.run(debug=False, port=8051)


if __name__ == "__main__":
    create_dashboard()
