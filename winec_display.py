import os
import argparse
import sqlite3
import pandas as pd
from dash import Dash, html, dcc, Input, Output, callback
import dash_bootstrap_components as dbc
import plotly.graph_objs as go
from plotly.subplots import make_subplots
from datetime import timedelta
import numpy as np

parser = argparse.ArgumentParser()
parser.add_argument("--mode")
parser.add_argument("--host")
parser.add_argument("--port")
parser.add_argument("--dash_ip", default="127.0.0.1")
# parser.add_argument("--dash_ip", default="192.168.1.13")
parser.add_argument("--rundir", default="/home/cav/winec_rundir")
parser.add_argument("--debug", default=True)
# parser.add_argument("--rundir", default=r"C:\Users\flori\OneDrive - univ-angers.fr\Documents\Home\Documents\winec\rundir")
args = parser.parse_args()

args.debug = args.debug is not None

# get temp/tec status measurements over the last X minutes, formatted as a pandas dataframe
def db_get_measurements(minutes, side):
    if args.debug:
        import numpy as np
        from datetime import datetime, timedelta
        times = np.arange(0, minutes)
        target = 12
        limithi = target + 2
        limitlo = target - 2
        tini = (1 - (datetime.now().second / 60)) * (limithi - limitlo) + limitlo
        temps = [tini, ]
        tec_statuses = [1, ]
        for _ in times[1:]:
            temp_dec = .1
            if (len(tec_statuses) > 1):
                temp_dec = temps[-1] - temps[-2]
                temp_dec = temp_dec * 1.05
                if (temp_dec < 0):
                    temp_dec = .1
            if tec_statuses[-1] == 1:
                temps.append(temps[-1] - temp_dec)
            else:
                temps.append(temps[-1] + temp_dec)
            if (temps[-1] < limitlo) and (tec_statuses[-1] == 1):
                tec_statuses.append(0)
            elif (temps[-1] > limithi) and (tec_statuses[-1] == 0):
                tec_statuses.append(1)
            else:
                tec_statuses.append(tec_statuses[-1])
        output_data = pd.DataFrame({"time": [datetime.now() - timedelta(minutes=minutes-int(t)) for t in times],
                                    f"{side}_temperature": temps,
                                    f"{side}_target": np.repeat(target, len(times)),
                                    f"{side}_limithi": np.repeat(limithi, len(times)),
                                    f"{side}_limitlo": np.repeat(limitlo, len(times)),
                                    f"{side}_tec_status": tec_statuses})
        return output_data
    connection = sqlite3.connect(os.path.join(args.rundir, "winec_db_v1.db"))
    cursor = connection.cursor()
    colnames = ["time", f"{side}_temperature", f"{side}_target", f"{side}_limithi", f"{side}_limitlo", f"{side}_tec_status", ]
    cursor.execute(f"SELECT {', '.join(colnames)} FROM temperature_measurements WHERE time > DATETIME('now', '-{minutes} minute')")  # execute a simple SQL select query
    query_results = cursor.fetchall()
    connection.commit()
    connection.close()
    output_data = pd.DataFrame(query_results, columns=colnames)
    return output_data


app = Dash(external_stylesheets=[dbc.themes.BOOTSTRAP])


def draw_main_grap(time, temperature, target, limithi, limitlo, tec_status):
    fig = make_subplots(specs=[[{"secondary_y": True}]])

    # rework data for tec display
    time_rw, tec_status_rw = [], []
    prev_tec = None
    for new_t, new_tec in zip(time, tec_status):
        if prev_tec is not None:
            if prev_tec != new_tec:
                time_rw.append(new_t)
                tec_status_rw.append(prev_tec)
        prev_tec = new_tec
        time_rw.append(new_t)
        tec_status_rw.append(new_tec)

    # TEC status
    fig.add_trace(
        go.Scatter(x=time_rw, y=tec_status_rw, name="TEC status", line=dict(width=.5, color='rgb(255,200,200)'), fill='tozeroy'),
        secondary_y=True,
    )

    # Limits
    fig.add_trace(
        go.Scatter(x=time, y=limithi, name="Upper limit", line=dict(width=0.5, color='#cccccc')),
        secondary_y=False,
    )
    fig.add_trace(
        go.Scatter(x=time, y=limitlo, name="Lower limit", line=dict(width=0.5, color='#cccccc'), fill='tonexty'),
        secondary_y=False,
    )

    # Temperature measures
    fig.add_trace(
        go.Scatter(x=time, y=temperature, name="Measured", line=dict(color='blue')),
        secondary_y=False,
    )

    # Target
    fig.add_trace(
        go.Scatter(x=time, y=target, name="Target", line=dict(color='black')),
        secondary_y=False,
    )
    
    # Add figure title
    # fig.update_layout(
    #     title_text="Temperature monitoring"
    # )

    # Set x-axis title
    fig.update_xaxes(title_text="Time")

    # get first y axis range
    upper_temp_limit = max(max(temperature), max(limithi)) + 1
    lower_temp_limit = min(min(temperature), min(limithi)) - 1

    # Set y-axes titles
    fig.update_yaxes(title_text="Temperature (°C)", range=(lower_temp_limit, upper_temp_limit), secondary_y=False)
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
        html.H1(children='WineC'),
        html.Div([
            html.H2(children='Left compartment'),
            html.Div([
                html.Div([dcc.Graph(id='live-update-graph-left')])
            ], style={'width': '50%', 'display': 'inline-block'}),
            html.Div([
                html.P(id="left-text-summary"),
            ], style={'width': '50%', 'display': 'inline-block', 'vertical-align': 'top'}),
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
    latest_measurements = db_get_measurements(minutes=120, side="left")
    fig = draw_main_grap(time=latest_measurements.time, temperature=latest_measurements.left_temperature, target=latest_measurements.left_target, limithi=latest_measurements.left_limithi, limitlo=latest_measurements.left_limitlo, tec_status=latest_measurements.left_tec_status)
    return fig


@callback(Output('live-update-graph-right', 'figure'),
          Input('interval-component-right', 'n_intervals'))
def update_graph_live_right(n):
    latest_measurements = db_get_measurements(minutes=120, side='right')
    fig = draw_main_grap(time=latest_measurements.time, temperature=latest_measurements.right_temperature, target=latest_measurements.right_target, limithi=latest_measurements.right_limithi, limitlo=latest_measurements.right_limitlo, tec_status=latest_measurements.right_tec_status)
    return fig


@callback(
    Output("left-text-summary", "children"),
    Input('interval-component-left', 'n_intervals')
    )
def left_stats(n):
    WATTS_PER_TEC = 85
    latest_measurements = db_get_measurements(minutes=120, side="left")
    total_time = (latest_measurements.time.tolist()[-1] - latest_measurements.time.tolist()[0]) / timedelta(minutes=1)
    # how much time on
    times_minutes = ((latest_measurements.time.tolist()[-1] - latest_measurements.time) / timedelta(minutes=1)).values
    tec_measurements = latest_measurements.left_tec_status.values
    pct_time_on = (np.trapezoid(tec_measurements[::-1], times_minutes[::-1])) / total_time
    return f"Fraction time ON: {100 * pct_time_on:.1f}%" + "\n" + f"Average consumption for {WATTS_PER_TEC}W TEC: {pct_time_on * WATTS_PER_TEC:.1f}W"


if __name__ == '__main__':
    # TODO propose inputs

    # TODO display some stats e.g. % time the TEC was on
    app.run(host=args.dash_ip)
