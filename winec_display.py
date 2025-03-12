import argparse
import sqlite3
import pandas as pd
from dash import Dash, html, dcc, Input, Output, callback
import plotly.graph_objs as go
from plotly.subplots import make_subplots

parser = argparse.ArgumentParser()
parser.add_argument("--mode")
parser.add_argument("--host")
parser.add_argument("--port")
parser.add_argument("--rundir", default="~/winec_res")
# parser.add_argument("--rundir", default=r"C:\Users\flori\OneDrive - univ-angers.fr\Documents\Home\Documents\winec\rundir")
args = parser.parse_args()


# get temp/tec status measurements over the last X minutes, formatted as a pandas dataframe
def db_get_measurements(minutes):
    connection = sqlite3.connect(os.path.join(args.rundir, "winec_db_v1.db"))
    cursor = connection.cursor()
    colnames = ["time", "left_temperature", "right_temperature", "left_tec_status", "right_tec_status"]
    cursor.execute(f"SELECT {', '.join(colnames)} FROM temperature_measurements WHERE time > DATETIME('now', '-{minutes} minute')")  # execute a simple SQL select query
    query_results = cursor.fetchall()
    connection.commit()
    connection.close()
    output_data = pd.DataFrame(query_results, columns=colnames)
    return output_data


app = Dash()


def draw_main_grap(time, temperature, tec_status):
    fig = make_subplots(specs=[[{"secondary_y": True}]])

    # Add traces
    fig.add_trace(
        go.Scatter(x=time, y=temperature, name="Temperature"),
        secondary_y=False,
    )

    fig.add_trace(
        go.Scatter(x=time, y=tec_status, name="TEC status"),
        secondary_y=True,
    )

    # Add figure title
    # fig.update_layout(
    #     title_text="Temperature monitoring"
    # )

    # Set x-axis title
    fig.update_xaxes(title_text="Time")

    # Set y-axes titles
    fig.update_yaxes(title_text="Temperature (°C)", secondary_y=False)
    fig.update_yaxes(title_text="TEC status", range=(-.01, 1.01), secondary_y=True)

    fig.update_yaxes(
        ticktext=["Off", "On"],
        tickvals=[0, 1],
        secondary_y=True,
    )

    fig.update_layout(template="plotly_white")

    return fig


app.layout = html.Div(
    html.Div([
        html.H1(children='Wine C'),
        html.Div([
            html.H2(children='Left compartment'),
            dcc.Graph(id='live-update-graph-left'),
            dcc.Interval(
                id='interval-component-left',
                interval=5 * 1000,  # in milliseconds
                n_intervals=0
            )
        ], id='left-div', style={'width': '100%', 'display': 'inline-block'}),
        html.Div([
            html.H2(children='Right compartment'),
            dcc.Graph(id='live-update-graph-right'),
            dcc.Interval(
                id='interval-component-right',
                interval=5 * 1000,  # in milliseconds
                n_intervals=0
            )
        ], id='right-div', style={'width': '100%', 'display': 'inline-block'}),
    ], id='main-div')
)


@callback(Output('live-update-graph-left', 'figure'),
          Input('interval-component-left', 'n_intervals'))
def update_graph_live_left(n):
    latest_measurements = db_get_measurements(minutes=120)
    fig = draw_main_grap(time=latest_measurements.time, temperature=latest_measurements.left_temperature, tec_status=latest_measurements.left_tec_status)
    return fig


@callback(Output('live-update-graph-right', 'figure'),
          Input('interval-component-right', 'n_intervals'))
def update_graph_live_right(n):
    latest_measurements = db_get_measurements(minutes=120)
    fig = draw_main_grap(time=latest_measurements.time, temperature=latest_measurements.right_temperature, tec_status=latest_measurements.right_tec_status)
    return fig


if __name__ == '__main__':
    # TODO propose inputs

    # TODO display some stats e.g. % time the TEC was on
    app.run()
