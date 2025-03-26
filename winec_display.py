import os
import argparse
import sqlite3
import pandas as pd
from dash import Dash, html, dcc, Input, Output, callback, State
import dash_bootstrap_components as dbc
import plotly.graph_objs as go
from plotly.subplots import make_subplots
from datetime import timedelta
import numpy as np
import time
import json

parser = argparse.ArgumentParser()
parser.add_argument("--mode")
parser.add_argument("--host")
parser.add_argument("--port")
parser.add_argument("--dash_ip", default="127.0.0.1")
# parser.add_argument("--dash_ip", default="192.168.1.13")
# parser.add_argument("--rundir", default="/home/cav/winec_rundir")
parser.add_argument("--rundir", default=r"C:\Users\flori\OneDrive\Documents\winec_temp")
parser.add_argument("--debug", default=True)
# parser.add_argument("--rundir", default=r"C:\Users\flori\OneDrive - univ-angers.fr\Documents\Home\Documents\winec\rundir")
args = parser.parse_args()

args.debug = args.debug is not None

params_minutes = 120  # TODO set
df_buffer = {'time': None, 'data': None, 'minutes': None}
df_refresh_delay = 5  # refresh at most every 5 seconds  # TODO set


def load_params():
    json_path = os.path.join(args.rundir, "settings.json")
    with open(json_path, "r") as f:
        params = json.load(f)
    return params


def save_params(params):
    json_path = os.path.join(args.rundir, "settings.json")
    with open(json_path, "w") as f:
        json.dump(params, f, indent=4)



# get temp/tec status measurements over the last X minutes, formatted as a pandas dataframe
def db_get_measurements_(minutes):
    if args.debug:
        import numpy as np
        from datetime import datetime, timedelta
        rng = np.random.RandomState()
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
            temp_dec += rng.normal(loc=.0, scale=.1)
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
        output_data = pd.DataFrame({"time": [datetime.now() - timedelta(minutes=minutes - int(t)) for t in times],
                                    "left_temperature": temps,
                                    "left_target": np.repeat(target, len(times)),
                                    "left_limithi": np.repeat(limithi, len(times)),
                                    "left_limitlo": np.repeat(limitlo, len(times)),
                                    "left_tec_status": tec_statuses,
                                    "right_temperature": temps,
                                    "right_target": np.repeat(target, len(times)),
                                    "right_limithi": np.repeat(limithi, len(times)),
                                    "right_limitlo": np.repeat(limitlo, len(times)),
                                    "right_tec_status": tec_statuses})
        return output_data
    connection = sqlite3.connect(os.path.join(args.rundir, "winec_db_v1.db"))
    cursor = connection.cursor()
    colnames = ["time",
                "left_temperature", "left_target", "left_limithi", "left_limitlo", "left_tec_status",
                "right_temperature", "right_target", "right_limithi", "right_limitlo", "right_tec_status", ]
    cursor.execute(
        f"SELECT {', '.join(colnames)} FROM temperature_measurements WHERE time > DATETIME('now', '-{minutes} minute')")  # execute a simple SQL select query
    query_results = cursor.fetchall()
    connection.commit()
    connection.close()
    output_data = pd.DataFrame(query_results, columns=colnames)
    return output_data


def db_get_measurements(minutes, df_buffer):
    if (df_buffer["data"] is not None) and ((time.time() - df_buffer['time']) < df_refresh_delay) and (
            df_buffer['minutes'] == minutes):
        return df_buffer['data']
    else:
        data = db_get_measurements_(minutes=minutes)
        df_buffer["time"] = time.time()
        df_buffer["minutes"] = minutes
        df_buffer["data"] = data
        return data


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
        go.Scatter(x=time_rw, y=tec_status_rw, name="TEC status", line=dict(width=.5, color='rgb(255,200,200)'),
                   fill='tozeroy'),
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


SIDEBAR_STYLE = {
    "position": "fixed",
    "top": 0,
    "left": 0,
    "bottom": 0,
    "width": "20rem",
    "padding": "2rem 1rem",
    "background-color": "#f8f9fa",
}

CONTENT_STYLE = {
    "margin-left": "20rem",
    "margin-right": "2rem",
    "padding": "2rem 1rem",
}

sidebar = html.Div(
    [
        html.H2("WineC", className="display-4"),
        html.Hr(),
        html.P("Settings"),
        html.Button('Reload', id='json-load', style={"width": "50%"}, n_clicks=0),
        html.Button('Save', id='json-save', style={"width": "50%"}, n_clicks=0),
        html.Hr(),
        html.P(id="set-cycle-length"),
        html.Hr(),
        html.P("Left", className="lead"),
        html.Hr(),
        html.P(id="set-left-status"),
        html.P(id="set-left-target-temp"),
        html.P(id="set-left-temperature-deviation"),
        html.P(id="set-left-tec-cooldown"),
        html.Hr(),
        html.P("Right", className="lead"),
        html.Hr(),
        html.P(id="set-right-status"),
        html.P(id="set-right-target-temp"),
        html.P(id="set-right-temperature-deviation"),
        html.P(id="set-right-tec-cooldown"),
    ],
    style=SIDEBAR_STYLE,
)

content = html.Div(
    [
        html.Div([
            html.H2(children='Left compartment'),
            html.Div([
                html.Div([
                    html.Div([dcc.Graph(id='live-update-graph-left')])
                ], style={'width': '50%', 'display': 'inline-block'}),
                html.Div([
                    html.P(id="left-frac-on", style={"display": "inline-block", "vertical-align": "middle", "width": "100%"}),
                    html.P(id="left-watts", style={"display": "inline-block", "vertical-align": "middle", "width": "100%"}),
                    html.P(id="left-tempdec", style={"display": "inline-block", "vertical-align": "middle", "width": "100%"}),
                    html.P(id="left-tempinc", style={"display": "inline-block", "vertical-align": "middle", "width": "100%"}),
                ], style={'width': '50%', 'display': 'inline-block'}),
            ], style={})
        ], id='left-div', style={'width': '100%', 'display': 'inline-block'}),
        html.Div([
            html.H2(children='Right compartment'),
            html.Div([
                html.Div([
                    html.Div([dcc.Graph(id='live-update-graph-right')])
                ], style={'width': '50%', 'display': 'inline-block'}),
                html.Div([
                    html.P(id="right-frac-on"),
                    html.P(id="right-watts"),
                    html.P(id="right-tempdec"),
                    html.P(id="right-tempinc"),
                ], style={'width': '50%', 'display': 'inline-block', 'vertical-align': 'middle'}),

            ])
        ], id='right-div', style={'width': '100%', 'display': 'inline-block'}),
        dcc.Interval(
            id='interval-component',
            interval=df_refresh_delay * 1000,  # in milliseconds
            n_intervals=0
        ),
    ], id="page-content", style=CONTENT_STYLE
)

app.layout = html.Div(
    html.Div([
        sidebar,
        content,
    ], id='main-div')
)


@callback(
    Output('set-cycle-length', 'children'),
    Input('json-load', 'n_clicks')
)
def set_cycle_length(n_clicks):
    params = load_params()
    return f"Cycle length (seconds): {params['loop_delay_seconds']}"


@callback(
    Output('set-left-status', 'children'),
    Input('json-load', 'n_clicks')
)
def set_left_status(n_clicks):
    params = load_params()
    return f"Status: {'ON' if params['left']['status'] else 'OFF'}"


@callback(
    Output('set-left-target-temp', 'children'),
    Input('json-load', 'n_clicks')
)
def set_left_ttemp(n_clicks):
    params = load_params()
    return f"Ttarget temperature (°C): {params['left']['target_temperature']}"


@callback(
    Output('set-left-temperature-deviation', 'children'),
    Input('json-load', 'n_clicks')
)
def set_left_tdev(n_clicks):
    params = load_params()
    return f"Temperature tolerance (°C): +/-{params['left']['temperature_deviation']}"


@callback(
    Output('set-left-tec-cooldown', 'children'),
    Input('json-load', 'n_clicks')
)
def set_left_tdev(n_clicks):
    params = load_params()
    return f"TEC cooldown (min): {params['left']['tec_cooldown_minutes']:.0f}"


@callback(
    Output('set-right-status', 'children'),
    Input('json-load', 'n_clicks')
)
def set_rt_status(n_clicks):
    params = load_params()
    return f"Status: {'ON' if params['right']['status'] else 'OFF'}"


@callback(
    Output('set-right-target-temp', 'children'),
    Input('json-load', 'n_clicks')
)
def set_rt_ttemp(n_clicks):
    params = load_params()
    return f"Target temperature (°C): {params['right']['target_temperature']}"


@callback(
    Output('set-right-temperature-deviation', 'children'),
    Input('json-load', 'n_clicks')
)
def set_rt_tdev(n_clicks):
    params = load_params()
    return f"Temperature tolerance (°C): +/-{params['right']['temperature_deviation']}"


@callback(
    Output('set-right-tec-cooldown', 'children'),
    Input('json-load', 'n_clicks')
)
def set_rt_tdev(n_clicks):
    params = load_params()
    return f"TEC cooldown (min): {params['right']['tec_cooldown_minutes']:.0f}"


@callback(Output('live-update-graph-left', 'figure'),
          Input('interval-component', 'n_intervals'))
def update_graph_live_left(n):
    latest_measurements = db_get_measurements(minutes=params_minutes, df_buffer=df_buffer)
    fig = draw_main_grap(time=latest_measurements.time, temperature=latest_measurements.left_temperature,
                         target=latest_measurements.left_target, limithi=latest_measurements.left_limithi,
                         limitlo=latest_measurements.left_limitlo, tec_status=latest_measurements.left_tec_status)
    return fig


@callback(Output('live-update-graph-right', 'figure'),
          Input('interval-component', 'n_intervals'))
def update_graph_live_right(n):
    latest_measurements = db_get_measurements(minutes=params_minutes, df_buffer=df_buffer)
    fig = draw_main_grap(time=latest_measurements.time, temperature=latest_measurements.right_temperature,
                         target=latest_measurements.right_target, limithi=latest_measurements.right_limithi,
                         limitlo=latest_measurements.right_limitlo, tec_status=latest_measurements.right_tec_status)
    return fig


@callback(
    Output("left-frac-on", "children"),
    Input('interval-component', 'n_intervals')
)
def left_stats_tecib(n):
    latest_measurements = db_get_measurements(minutes=params_minutes, df_buffer=df_buffer)
    total_time = (latest_measurements.time.tolist()[-1] - latest_measurements.time.tolist()[0]) / timedelta(minutes=1)
    # how much time on
    times_minutes = ((latest_measurements.time.tolist()[-1] - latest_measurements.time) / timedelta(minutes=1)).values
    tec_measurements = latest_measurements.left_tec_status.values
    pct_time_on = (np.trapezoid(tec_measurements[::-1], times_minutes[::-1])) / total_time
    return f"Fraction time ON: {100 * pct_time_on:.1f}%"


@callback(
    Output("right-frac-on", "children"),
    Input('interval-component', 'n_intervals')
)
def left_stats_tecib(n):
    latest_measurements = db_get_measurements(minutes=params_minutes, df_buffer=df_buffer)
    total_time = (latest_measurements.time.tolist()[-1] - latest_measurements.time.tolist()[0]) / timedelta(minutes=1)
    # how much time on
    times_minutes = ((latest_measurements.time.tolist()[-1] - latest_measurements.time) / timedelta(minutes=1)).values
    tec_measurements = latest_measurements.right_tec_status.values
    pct_time_on = (np.trapezoid(tec_measurements[::-1], times_minutes[::-1])) / total_time
    return f"Fraction time ON: {100 * pct_time_on:.1f}%"


@callback(
    Output("left-watts", "children"),
    Input('interval-component', 'n_intervals')
)
def left_stats_watts(n):
    WATTS_PER_TEC = 85
    latest_measurements = db_get_measurements(minutes=params_minutes, df_buffer=df_buffer)
    total_time = (latest_measurements.time.tolist()[-1] - latest_measurements.time.tolist()[0]) / timedelta(minutes=1)
    # how much time on
    times_minutes = ((latest_measurements.time.tolist()[-1] - latest_measurements.time) / timedelta(minutes=1)).values
    tec_measurements = latest_measurements.left_tec_status.values
    pct_time_on = (np.trapezoid(tec_measurements[::-1], times_minutes[::-1])) / total_time
    return f"Average consumption for {WATTS_PER_TEC}W TEC: {pct_time_on * WATTS_PER_TEC:.1f}W"


@callback(
    Output("right-watts", "children"),
    Input('interval-component', 'n_intervals')
)
def left_stats_watts(n):
    WATTS_PER_TEC = 85
    latest_measurements = db_get_measurements(minutes=params_minutes, df_buffer=df_buffer)
    total_time = (latest_measurements.time.tolist()[-1] - latest_measurements.time.tolist()[0]) / timedelta(minutes=1)
    # how much time on
    times_minutes = ((latest_measurements.time.tolist()[-1] - latest_measurements.time) / timedelta(minutes=1)).values
    tec_measurements = latest_measurements.right_tec_status.values
    pct_time_on = (np.trapezoid(tec_measurements[::-1], times_minutes[::-1])) / total_time
    return f"Average consumption for {WATTS_PER_TEC}W TEC: {pct_time_on * WATTS_PER_TEC:.1f}W"


@callback(
    Output("left-tempinc", "children"),
    Input('interval-component', 'n_intervals')
)
def left_stats_avgincrease(n):
    latest_measurements = db_get_measurements(minutes=params_minutes, df_buffer=df_buffer)
    # how much time on
    times_minutes = ((latest_measurements.time.tolist()[-1] - latest_measurements.time) / timedelta(minutes=1)).values
    tec_measurements = latest_measurements.left_tec_status.values
    temp_measurements = latest_measurements.left_temperature.values
    # select only measures when tec is off
    times_minutes = times_minutes[tec_measurements == 0]
    temp_measurements = temp_measurements[tec_measurements == 0]
    median_var = float(-np.median(np.diff(temp_measurements) / np.diff(times_minutes)))
    return f"Average temperature increase when TEC is OFF: {median_var:+.2f}°C"


@callback(
    Output("right-tempinc", "children"),
    Input('interval-component', 'n_intervals')
)
def left_stats_avgincrease(n):
    latest_measurements = db_get_measurements(minutes=params_minutes, df_buffer=df_buffer)
    # how much time on
    times_minutes = ((latest_measurements.time.tolist()[-1] - latest_measurements.time) / timedelta(minutes=1)).values
    tec_measurements = latest_measurements.right_tec_status.values
    temp_measurements = latest_measurements.right_temperature.values
    # select only measures when tec is off
    times_minutes = times_minutes[tec_measurements == 0]
    temp_measurements = temp_measurements[tec_measurements == 0]
    median_var = float(-np.median(np.diff(temp_measurements) / np.diff(times_minutes)))
    return f"Average temperature increase when TEC is OFF: {median_var:+.2f}°C"


@callback(
    Output("left-tempdec", "children"),
    Input('interval-component', 'n_intervals')
)
def left_stats_avgdecrease(n):
    latest_measurements = db_get_measurements(minutes=params_minutes, df_buffer=df_buffer)
    # how much time on
    times_minutes = ((latest_measurements.time.tolist()[-1] - latest_measurements.time) / timedelta(minutes=1)).values
    tec_measurements = latest_measurements.left_tec_status.values
    temp_measurements = latest_measurements.left_temperature.values
    # select only measures when tec is off
    times_minutes = times_minutes[tec_measurements == 1]
    temp_measurements = temp_measurements[tec_measurements == 1]
    median_var = float(-np.median(np.diff(temp_measurements) / np.diff(times_minutes)))
    return f"Average temperature decrease when TEC is ON: {median_var:+.2f}°C"


@callback(
    Output("right-tempdec", "children"),
    Input('interval-component', 'n_intervals')
)
def left_stats_avgdecrease(n):
    latest_measurements = db_get_measurements(minutes=params_minutes, df_buffer=df_buffer)
    # how much time on
    times_minutes = ((latest_measurements.time.tolist()[-1] - latest_measurements.time) / timedelta(minutes=1)).values
    tec_measurements = latest_measurements.right_tec_status.values
    temp_measurements = latest_measurements.right_temperature.values
    # select only measures when tec is off
    times_minutes = times_minutes[tec_measurements == 1]
    temp_measurements = temp_measurements[tec_measurements == 1]
    median_var = float(-np.median(np.diff(temp_measurements) / np.diff(times_minutes)))
    return f"Average temperature decrease when TEC is ON: {median_var:+.2f}°C"


if __name__ == '__main__':
    # TODO propose inputs

    # TODO display some stats e.g. % time the TEC was on
    app.run(host=args.dash_ip)
