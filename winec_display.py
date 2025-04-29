import os
import argparse
import pandas as pd
from dash import Dash, html, dcc, Input, Output, callback, State
import dash_bootstrap_components as dbc
import plotly.graph_objs as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta
import numpy as np
import time
import json

parser = argparse.ArgumentParser()
parser.add_argument("--mode")
parser.add_argument("--host")
parser.add_argument("--port")
parser.add_argument("--dash_ip", default="192.168.1.13")
parser.add_argument("--rundir", default="/home/cav/winec_rundir")
parser.add_argument("--auto_debug", default=True)
parser.add_argument("--db_platform", default="mariadb")
parser.add_argument("--db_host", default="localhost")
parser.add_argument("--db_port", default=3306)
parser.add_argument("--db_user", default="cav")
parser.add_argument("--db_password", default="caveavin")
parser.add_argument("--db_database", default="winec")
args = parser.parse_args()

args.auto_debug = args.auto_debug is not None


def now():
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')


def log(s):
    print(f"{now()}    {s}")


if args.auto_debug and not os.path.exists(args.rundir):
    args.dash_ip = "127.0.0.1"
    # args.rundir = r"C:\Users\flori\OneDrive - univ-angers.fr\Documents\Home\Research\Common"
    args.rundir = r"C:\Users\flori\OneDrive\Documents\winec_temp"

if args.db_platform == "sqlite3":
    import sqlite3
elif args.db_platform == "mariadb":
    from sqlalchemy import create_engine


def load_params_():
    json_path = os.path.join(args.rundir, "settings.json")
    with open(json_path, "r") as f:
        params = json.load(f)
    return params


def save_params(params):
    json_path = os.path.join(args.rundir, "settings.json")
    with open(json_path, "w") as f:
        json.dump(params, f, indent=4)


def db_get_measurements_mariadb(minutes):
    engine = create_engine(f"mariadb+mariadbconnector://{args.db_user}:{args.db_password}@{args.db_host}:{args.db_port}/{args.db_database}")
    # engine = create_engine(f"mariadb:///?User={args.db_user}&;Password={args.db_password}&Database={args.db_database}&Server={args.db_host}&Port={args.db_port}")
    dt_start = (datetime.now() - timedelta(minutes=minutes)).strftime('%Y-%m-%d %H:%M:%S')
    dt_end = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    output_data = pd.read_sql(f"SELECT * FROM temperature_measurements WHERE time BETWEEN '{dt_start}' and '{dt_end}'", engine)
    return output_data


def db_get_measurements_sqlite3(minutes):
    connection = sqlite3.connect(os.path.join(args.rundir, "winec_db_v1.db"), timeout=10)
    cursor = connection.cursor()
    colnames = ["time", "event",
                "left_temperature", "left_target", "left_limithi", "left_limitlo", "left_heatsink_temperature", "left_tec_status", "left_tec_on_cd",
                "right_temperature", "right_target", "right_limithi", "right_limitlo", "right_heatsink_temperature", "right_tec_status", "right_tec_on_cd", ]
    # cursor.execute(f"SELECT {', '.join(colnames)} FROM temperature_measurements WHERE time > DATETIME('now', '-{minutes} minute')")  # execute a simple SQL select query
    dt_start = (datetime.now() - timedelta(minutes=minutes)).strftime('%Y-%m-%d %H:%M:%S')
    dt_end = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    cursor.execute(f"SELECT {', '.join(colnames)} FROM temperature_measurements WHERE time BETWEEN '{dt_start}' and '{dt_end}'")  # execute a simple SQL select query
    query_results = cursor.fetchall()
    connection.commit()
    connection.close()
    output_data = pd.DataFrame(query_results, columns=colnames)
    return output_data



# get temp/tec status measurements over the last X minutes, formatted as a pandas dataframe
def fetch_db(minutes):
    # if set to debug: create fake data
    log("retrieving up-to-date db data")
    # the real function
    output_data = None
    if args.db_platform == "sqlite3":
        output_data = db_get_measurements_sqlite3(minutes=minutes)
    if args.db_platform == "mariadb":
        output_data = db_get_measurements_mariadb(minutes=minutes)
    # format correctly
    if output_data is not None:
        output_data.time = pd.to_datetime(output_data.time)
        output_data = output_data.astype({"left_temperature": float, 'left_target': float, 'left_limithi': float, 'left_limitlo': float, 'left_heatsink_temperature': float, 'left_tec_status': int, 'left_tec_on_cd': int,
                                          'right_temperature': float, 'right_target': float, 'right_limithi': float, 'right_limitlo': float, 'right_heatsink_temperature': float, 'right_tec_status': int, 'right_tec_on_cd': int})
    else:
        print(f"unable to retrieve db data: unknown {args.db_platform}")
    return output_data


def get_db_subset(db_extract: pd.DataFrame, events: list = ("entry", )):
    return db_extract[db_extract.event.isin(events)]


app = Dash(external_stylesheets=[dbc.themes.BOOTSTRAP])


def rework_onoff_with_times(time, onoff):
    time_rw, onoff_rw = [], []
    prev_onoff = None
    for new_t, new_onoff in zip(time, onoff):
        if prev_onoff is not None:
            if prev_onoff != new_onoff:
                time_rw.append(new_t)
                onoff_rw.append(prev_onoff)
        prev_onoff = new_onoff
        time_rw.append(new_t)
        onoff_rw.append(new_onoff)
    return time_rw, onoff_rw


def draw_main_grap(time, temperature, heatsink_temperature, target, limithi, limitlo, tec_status, tec_on_cd, startup_times, display_diff):
    if len(time) == 0:
        return None

    if display_diff:
        time_delta = (time.iloc[1:].copy().reset_index(drop=True) - time.iloc[:-1].copy().reset_index(drop=True)) / pd.Timedelta(seconds=60)
        temperature = temperature.copy().diff().iloc[1:].reset_index(drop=True) / time_delta.values
        heatsink_temperature = heatsink_temperature.copy().diff().iloc[1:].reset_index(drop=True) / time_delta.values
        time = time.iloc[1:].copy().reset_index(drop=True)
            
        fig = make_subplots(specs=[[{"secondary_y": True}]])
    
        # get secondary y axis height
        min_sec_y, max_sec_y = min(heatsink_temperature) - 1, max(heatsink_temperature) + 1
    
        # make tec status values in the heatsink temp range
        tec_status_filter_on = tec_status == 1
        tec_status_cp = tec_status.copy()
        tec_status_cp[tec_status_filter_on] = max_sec_y
        tec_status_cp[~tec_status_filter_on] = min_sec_y
    
        # rework data for tec display
        # tec_status_time_rw, tec_status_onoff_rw = rework_onoff_with_times(time, tec_status_cp)
        # tec_cd_time_rw, tec_cd_onoff_rw = rework_onoff_with_times(time, tec_on_cd)
    
        # TEC status
        fig.add_trace(
        #    go.Scatter(x=tec_status_time_rw, y=tec_status_onoff_rw, name="TEC status", line=dict(width=.5, color='rgb(255,200,200)'),
        #               fill='tozeroy'),
            go.Scatter(x=time, y=tec_status_cp, name="TEC status", line=dict(width=.5, color='rgb(255,200,200)'),
                       fill='tozeroy'),
            secondary_y=True,
        )
        # & tec on cd
        fig.add_trace(
        #    go.Scatter(x=tec_cd_time_rw, y=tec_cd_onoff_rw, name="TEC on CD", line=dict(width=.5, color='rgb(255,219,187)'),
        #               fill='tozeroy'),
            go.Scatter(x=time, y=tec_on_cd, name="TEC on CD", line=dict(width=.5, color='rgb(255,219,187)'),
                       fill='tozeroy'),
            secondary_y=True,
        )
    
        # Temperature measures
        fig.add_trace(
            go.Scatter(x=time, y=temperature, name="Measured", line=dict(color='blue')),
            secondary_y=False,
        )
    
        # Heatsink temperature measures
        fig.add_trace(
            go.Scatter(x=time, y=heatsink_temperature, name="Heatsink", line=dict(color='red')),
            secondary_y=True,
        )
    
        # add startup times
        for startup_time in startup_times:
            fig.add_trace(
                go.Scatter(x=[startup_time, startup_time], y=[min_sec_y, max_sec_y], mode="lines", name="Startup",
                           line=dict(width=3, color='rgb(0,180,0)')),
                secondary_y=True,
            )
    
        # Set x-axis title
        fig.update_xaxes(title_text="Time")
    
        # get first y axis range
        upper_temp_limit = max(temperature) + 1
        lower_temp_limit = min(temperature) - 1
    
        # Set y-axes titles
        fig.update_yaxes(title_text="Temperature Δ (°C/min)", range=(lower_temp_limit, upper_temp_limit), secondary_y=False)
        fig.update_yaxes(title_text="Heatsink temperature Δ (°C/min)", range=(min_sec_y, max_sec_y), secondary_y=True)
    
        fig.update_layout(template="plotly_white", margin=dict(t=50, b=50))
    
        return fig

    fig = make_subplots(specs=[[{"secondary_y": True}]])

    # get secondary y axis height
    min_sec_y, max_sec_y = min(0, min(heatsink_temperature) - 1), max(100, max(heatsink_temperature) + 1)

    # make tec status values in the heatsink temp range
    tec_status_filter_on = tec_status == 1
    tec_status_cp = tec_status.copy()
    tec_status_cp[tec_status_filter_on] = max_sec_y
    tec_status_cp[~tec_status_filter_on] = min_sec_y

    # rework data for tec display
    # tec_status_time_rw, tec_status_onoff_rw = rework_onoff_with_times(time, tec_status_cp)
    # tec_cd_time_rw, tec_cd_onoff_rw = rework_onoff_with_times(time, tec_on_cd)

    # TEC status
    fig.add_trace(
    #    go.Scatter(x=tec_status_time_rw, y=tec_status_onoff_rw, name="TEC status", line=dict(width=.5, color='rgb(255,200,200)'),
    #               fill='tozeroy'),
        go.Scatter(x=time, y=tec_status_cp, name="TEC status", line=dict(width=.5, color='rgb(255,200,200)'),
                   fill='tozeroy'),
        secondary_y=True,
    )
    # & tec on cd
    fig.add_trace(
    #    go.Scatter(x=tec_cd_time_rw, y=tec_cd_onoff_rw, name="TEC on CD", line=dict(width=.5, color='rgb(255,219,187)'),
    #               fill='tozeroy'),
        go.Scatter(x=time, y=tec_on_cd, name="TEC on CD", line=dict(width=.5, color='rgb(255,219,187)'),
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

    # Target
    fig.add_trace(
        go.Scatter(x=time, y=target, name="Target", line=dict(color='black')),
        secondary_y=False,
    )

    # Temperature measures
    fig.add_trace(
        go.Scatter(x=time, y=temperature, name="Measured", line=dict(color='blue')),
        secondary_y=False,
    )

    # Heatsink temperature measures
    fig.add_trace(
        go.Scatter(x=time, y=heatsink_temperature, name="Heatsink", line=dict(color='red')),
        secondary_y=True,
    )

    # add startup times
    for startup_time in startup_times:
        fig.add_trace(
            go.Scatter(x=[startup_time, startup_time], y=[min_sec_y, max_sec_y], mode="lines", name="Startup",
                       line=dict(width=3, color='rgb(0,180,0)')),
            secondary_y=True,
        )

    # Set x-axis title
    fig.update_xaxes(title_text="Time")

    # get first y axis range
    upper_temp_limit = max(max(temperature), max(limithi)) + 1
    lower_temp_limit = min(min(temperature), min(limitlo)) - 1

    # Set y-axes titles
    fig.update_yaxes(title_text="Temperature (°C)", range=(lower_temp_limit, upper_temp_limit), secondary_y=False)
    fig.update_yaxes(title_text="Heatsink temperature (°C)", range=(min_sec_y, max_sec_y), secondary_y=True)
    # fig.update_yaxes(title_text="TEC status", range=(-.01, 1.01), secondary_y=True)

    # fig.update_yaxes(
    #     ticktext=["Off", "On"],
    #     tickvals=[0, 1],
    #     secondary_y=True,
    # )

    fig.update_layout(template="plotly_white", margin=dict(t=50, b=50))

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

CLEN_MIN = 1
CLEN_MAX = 60
CLEN_STEP = 1
TTEMP_MIN = 2
TTEMP_MAX = 20
TTEMP_STEP = .1
TEMPDEV_MIN = .1
TEMPDEV_MAX = 5
TEMPDEV_STEP = .1
TECCD_MIN = 10
TECCD_MAX = 300
TECCD_STEP = 1

sidebar = html.Div(
    [
        html.H2("WineC", className="display-4"),
        html.Hr(),
        html.P("Settings", className="lead"),
        html.Button('Reload', id='json-load', style={"width": "50%"}, n_clicks=0),
        html.Button('Save', id='json-save', style={"width": "50%"}, n_clicks=0),
        html.Div(id='json-placeholder', style={"color": "red"}),
        html.Hr(),
        html.Div([
            html.P("Display last (min)", style={"display": "inline-block", "width": "80%"}),
            dcc.Input(min=1, max=1440, step=1, value=60, id='display-length-slider', type="number",
                      style={"display": "inline-block", "width": "20%", "text-align": "right"}),
            dbc.Switch(
                id="diff-switch",
                label="Display differences",
                value=False,
            ),
            html.Button('Refresh', id='refresh-button', style={"width": "100%"}, n_clicks=0),
        ]),
        html.Hr(),
        html.Div([
            html.P("Cycle length (seconds): ", style={"display": "inline-block", "width": "80%"}),
            dcc.Input(id="set-cycle-length", type="number", min=CLEN_MIN, max=CLEN_MAX, step=CLEN_STEP, style={"display": "inline-block", "width": "20%", "text-align": "right"})
        ]),
        html.P(id="obs-cycle-length", style={"color": "#aaaaaa"}),
        html.Hr(),
        html.P("Left", className="lead"),
        html.Hr(),
        html.Div([
            html.P("Status:", style={"display": "inline-block", "width": "60%"}),
            dcc.Dropdown(["ON", "OFF"], id="set-left-status", style={"display": "inline-block", "width": "40%", "text-align": "right"})
        ]),
        html.Div([
            html.P("Target temperature (°C): ", style={"display": "inline-block", "width": "80%"}),
            dcc.Input(id="set-left-target-temp", type="number", min=TTEMP_MIN, max=TTEMP_MAX, step=TTEMP_STEP, style={"display": "inline-block", "width": "20%", "text-align": "right"})
        ]),
        html.Div([
            html.P("Tolerance (°C): +/-", style={"display": "inline-block", "width": "80%"}),
            dcc.Input(id="set-left-temperature-deviation", type="number", min=TEMPDEV_MIN, max=TEMPDEV_MAX, step=TEMPDEV_STEP, style={"display": "inline-block", "width": "20%", "text-align": "right"})
        ]),
        html.Div([
            html.P("TEC cooldown (seconds):", style={"display": "inline-block", "width": "80%"}),
            dcc.Input(id="set-left-tec-cooldown", type="number", min=TECCD_MIN, max=TECCD_MAX, step=TECCD_STEP, style={"display": "inline-block", "width": "20%", "text-align": "right"})
        ]),
        html.Hr(),
        html.P("Right", className="lead"),
        html.Hr(),
        html.Div([
            html.P("Status:", style={"display": "inline-block", "width": "60%"}),
            dcc.Dropdown(["ON", "OFF"], id="set-right-status", style={"display": "inline-block", "width": "40%", "text-align": "right"})
        ]),
        html.Div([
            html.P("Target temperature (°C): ", style={"display": "inline-block", "width": "80%"}),
            dcc.Input(id="set-right-target-temp", type="number", min=TTEMP_MIN, max=TTEMP_MAX, step=TTEMP_STEP, style={"display": "inline-block", "width": "20%", "text-align": "right"})
        ]),
        html.Div([
            html.P("Tolerance (°C): +/-", style={"display": "inline-block", "width": "80%"}),
            dcc.Input(id="set-right-temperature-deviation", type="number", min=TEMPDEV_MIN, max=TEMPDEV_MAX, step=TEMPDEV_STEP, style={"display": "inline-block", "width": "20%", "text-align": "right"})
        ]),
        html.Div([
            html.P("TEC cooldown (seconds):", style={"display": "inline-block", "width": "80%"}),
            dcc.Input(id="set-right-tec-cooldown", type="number", min=TECCD_MIN, max=TECCD_MAX, step=TECCD_STEP, style={"display": "inline-block", "width": "20%", "text-align": "right"})
        ]),
    ],
    style=SIDEBAR_STYLE,
)

content = html.Div(
    [
        html.Div([
            html.H2(id="current-backend-status", className="lead"),
            html.H2(children='Left compartment'),
            html.Div([
                html.Div([
                    html.Div([dcc.Graph(id='live-update-graph-left')])
                ], style={'width': '60%', 'display': 'table-cell', 'vertical-align': 'middle'}),
                html.Div([
                    html.P(id="left-frac-on"),
                    html.P(id="left-watts"),
                    html.P(id="left-tempdec"),
                    html.P(id="left-tempinc"),
                    html.P(id="left-tecbased-tempdec"),
                    html.P(id="left-tecbased-tempinc"),
                ], style={'width': '40%', 'display': 'table-cell', 'vertical-align': 'middle', "padding": "0rem 2rem"}),
            ], style={"display": "table", 'width': '100%'})
        ], id='left-div', style={'width': '100%', 'display': 'inline-block'}),
        html.Div([
            html.H2(children='Right compartment'),
            html.Div([
                html.Div([
                    html.Div([dcc.Graph(id='live-update-graph-right')])
                ], style={'width': '60%', 'display': 'table-cell', 'vertical-align': 'middle'}),
                html.Div([
                    html.P(id="right-frac-on"),
                    html.P(id="right-watts"),
                    html.P(id="right-tempdec"),
                    html.P(id="right-tempinc"),
                    html.P(id="right-tecbased-tempdec"),
                    html.P(id="right-tecbased-tempinc"),
                ], style={'width': '40%', 'display': 'table-cell', 'vertical-align': 'middle', "padding": "0rem 2rem"}),
            ], style={"display": "table", 'width': '100%'})
        ], id='right-div', style={'width': '100%', 'display': 'inline-block'}),
    ], id="page-content", style=CONTENT_STYLE
)

app.layout = html.Div(
    html.Div([
        sidebar,
        content,
    ], id='main-div')
)


@callback(
    Output('set-cycle-length', 'value'),
    Output('set-left-status', 'value'),
    Output('set-left-target-temp', 'value'),
    Output('set-left-temperature-deviation', 'value'),
    Output('set-left-tec-cooldown', 'value'),
    Output('set-right-status', 'value'),
    Output('set-right-target-temp', 'value'),
    Output('set-right-temperature-deviation', 'value'),
    Output('set-right-tec-cooldown', 'value'),
    Input('json-load', 'n_clicks')
)
def set_cycle_length(n_clicks):
    params = load_params_()
    return (
        params['loop_delay_seconds'],
        'ON' if params['left']['status'] else 'OFF',
        params['left']['target_temperature'],
        params['left']['temperature_deviation'],
        params['left']['tec_cooldown_seconds'],
        'ON' if params['right']['status'] else 'OFF',
        params['right']['target_temperature'],
        params['right']['temperature_deviation'],
        params['right']['tec_cooldown_seconds'],

    )


@callback(
    Output('json-placeholder', 'children'),
    Input('json-save', 'n_clicks'),
    State('set-cycle-length', 'value'),
    State('set-left-status', 'value'),
    State('set-left-target-temp', 'value'),
    State('set-left-temperature-deviation', 'value'),
    State('set-left-tec-cooldown', 'value'),
    State('set-right-status', 'value'),
    State('set-right-target-temp', 'value'),
    State('set-right-temperature-deviation', 'value'),
    State('set-right-tec-cooldown', 'value'),
    prevent_initial_call=True
)
def update_output(n_clicks, cycle_len, left_status, left_ttemp, left_tempdev, left_teccd, right_status, right_ttemp, right_tempdev, right_teccd):
    # check values
    if (cycle_len < CLEN_MIN) or (cycle_len > CLEN_MAX) or (((1 / CLEN_STEP) * cycle_len) % 1 != 0):
        return "Invalid settings cycle length"
    if left_status not in ("ON", "OFF"):
        return "Invalid settings for left status"
    if (left_ttemp < TTEMP_MIN) or (left_ttemp > TTEMP_MAX) or (((1 / TTEMP_STEP) * left_ttemp) % 1 != 0):
        return "Invalid settings for left temp target"
    if (left_tempdev < TEMPDEV_MIN) or (left_tempdev > TEMPDEV_MAX) or (((1 / TEMPDEV_STEP) * left_tempdev) % 1 != 0):
        return "Invalid settings for left temp tolerance"
    if (left_teccd < TECCD_MIN) or (left_teccd > TECCD_MAX) or (((1 / TECCD_STEP) * left_teccd) % 1 != 0):
        return "Invalid settings for left TEC CD"
    if right_status not in ("ON", "OFF"):
        return "Invalid settings for right status"
    if (right_ttemp < TTEMP_MIN) or (right_ttemp > TTEMP_MAX) or (((1 / TTEMP_STEP) * right_ttemp) % 1 != 0):
        return "Invalid settings for right temp target"
    if (right_tempdev < TEMPDEV_MIN) or (right_tempdev > TEMPDEV_MAX) or (((1 / TEMPDEV_STEP) * right_tempdev) % 1 != 0):
        return "Invalid settings for right temp tolerance"
    if (right_teccd < TECCD_MIN) or (right_teccd > TECCD_MAX) or (((1 / TECCD_STEP) * right_teccd) % 1 != 0):
        return "Invalid settings for right TEC CD"
    # save to json
    params = {
        "loop_delay_seconds": cycle_len,
        "left": {
            "status": True if left_status == "ON" else False,
            "target_temperature": left_ttemp,
            "temperature_deviation": left_tempdev,
            "tec_cooldown_seconds": left_teccd,
        },
        "right": {
            "status": True if right_status == "ON" else False,
            "target_temperature": right_ttemp,
            "temperature_deviation": right_tempdev,
            "tec_cooldown_seconds": right_teccd,
        }
    }
    save_params(params)
    return "Saved"


def lr_timeonoffstats(total_time, times_minutes, tec_measurements):
    # how much time on
    pct_time_on = (np.trapezoid(tec_measurements[::-1], times_minutes[::-1])) / total_time
    return pct_time_on


def lr_stats_avgincdecrease(times_minutes, tec_measurements, temp_measurements, increase):
    # select only measures when tec is off
    tec_status_fetch = (1 - (increase == 1) * 1)
    times_minutes = times_minutes[tec_measurements == tec_status_fetch]
    temp_measurements = temp_measurements[tec_measurements == tec_status_fetch]
    if len(times_minutes) < 2:
        median_var = np.nan
    else:
        median_var = float(-np.mean(np.diff(temp_measurements) / np.diff(times_minutes)))
    return median_var


def side_stats_avgteconoffincreasedecrease(times_minutes, tec_measurements, temp_measurements, increase):
    # detect when tec was switched on/off
    switch_pos = np.diff(tec_measurements) != 0
    times_at_switch = times_minutes[1:][switch_pos]
    # tec_at_switch = tec_measurements[1:][switch_pos]
    temp_at_switch = temp_measurements[1:][switch_pos]
    # compute times between switch turned off and switch turned on/opposite
    temp_overt_variations = - np.diff(temp_at_switch) / np.diff(times_at_switch)
    avg_var = np.mean(temp_overt_variations[(temp_overt_variations > 0) if increase else (temp_overt_variations < 0)])
    return avg_var


@callback(
    Output('current-backend-status', 'children'),
    Output('live-update-graph-left', 'figure'),
    Output('live-update-graph-right', 'figure'),
    Output("left-frac-on", "children"),
    Output("right-frac-on", "children"),
    Output("left-watts", "children"),
    Output("right-watts", "children"),
    Output("left-tempinc", "children"),
    Output("right-tempinc", "children"),
    Output("left-tempdec", "children"),
    Output("right-tempdec", "children"),
    Output("left-tecbased-tempdec", "children"),
    Output("left-tecbased-tempinc", "children"),
    Output("right-tecbased-tempdec", "children"),
    Output("right-tecbased-tempinc", "children"),
    Output("obs-cycle-length", "children"),
    Input('display-length-slider', 'value'),
    Input('refresh-button', 'n_clicks'),
    Input('diff-switch', 'value'),
)
def callback_update_from_db(param_minutes, n, diff_switch):
    # extract db
    db_extract = fetch_db(param_minutes)
    db_extract_entries = get_db_subset(db_extract=db_extract, events=["entry",])
    db_extract_startups = get_db_subset(db_extract=db_extract, events=["startup",])

    # prepare some variables
    zero_time = db_extract_entries.time.tolist()[-1]
    times_minutes = ((zero_time - db_extract_entries.time) / timedelta(minutes=1)).values
    total_time = (zero_time - db_extract_entries.time.tolist()[0]) / timedelta(minutes=1)
    tec_measurements, temp_measurements = {}, {}
    for side in ("left", "right"):
        tec_measurements[side] = db_extract_entries[f"{side}_tec_status"].values
        temp_measurements[side] = db_extract_entries[f"{side}_temperature"].values

    # current backend stats
    seen_last_since = (datetime.now() - zero_time) / timedelta(seconds=1)
    # time out is cycle length + 5 seconds tolerance
    params = load_params_()
    timeout_time = params["loop_delay_seconds"] + 5
    backend_status = "ALIVE" if seen_last_since < timeout_time else "AWOL"
    backend_status_str = f"Backend status is currently: {backend_status} (refreshed {seen_last_since:.0f} seconds ago)"

    # left fig
    left_fig = draw_main_grap(time=db_extract_entries.time, temperature=db_extract_entries.left_temperature, heatsink_temperature=db_extract_entries.left_heatsink_temperature,
                              target=db_extract_entries.left_target, limithi=db_extract_entries.left_limithi,
                              limitlo=db_extract_entries.left_limitlo, tec_status=db_extract_entries.left_tec_status,
                              tec_on_cd=db_extract_entries.left_tec_on_cd,
                              startup_times=db_extract_startups.time,
                              display_diff=diff_switch)

    # right fig
    right_fig = draw_main_grap(time=db_extract_entries.time, temperature=db_extract_entries.right_temperature, heatsink_temperature=db_extract_entries.right_heatsink_temperature,
                               target=db_extract_entries.right_target, limithi=db_extract_entries.right_limithi,
                               limitlo=db_extract_entries.right_limitlo, tec_status=db_extract_entries.right_tec_status,
                               tec_on_cd=db_extract_entries.right_tec_on_cd,
                               startup_times=db_extract_startups.time,
                               display_diff=diff_switch)

    # pct time on
    WATTS_PER_TEC = 85
    pct_time_on = lr_timeonoffstats(total_time=total_time, times_minutes=times_minutes, tec_measurements=tec_measurements["left"])
    left_pct_time_on_str = f"Fraction time ON: {100 * pct_time_on:.1f}%"
    left_watts_str = f"Average consumption for {WATTS_PER_TEC}W TEC: {pct_time_on * WATTS_PER_TEC:.1f}W"
    pct_time_on = lr_timeonoffstats(total_time=total_time, times_minutes=times_minutes, tec_measurements=tec_measurements["right"])
    right_pct_time_on_str = f"Fraction time ON: {100 * pct_time_on:.1f}%"
    right_watts_str = f"Average consumption for {WATTS_PER_TEC}W TEC: {pct_time_on * WATTS_PER_TEC:.1f}W"

    # median var
    median_var = lr_stats_avgincdecrease(times_minutes=times_minutes, tec_measurements=tec_measurements["left"], temp_measurements=temp_measurements["left"], increase=True)
    left_temp_inc_str = f"Mean temperature increase when TEC is OFF: {median_var:+.3f}°C/min"
    median_var = lr_stats_avgincdecrease(times_minutes=times_minutes, tec_measurements=tec_measurements["right"], temp_measurements=temp_measurements["right"], increase=True)
    right_temp_inc_str = f"Mean temperature increase when TEC is OFF: {median_var:+.3f}°C/min"
    median_var = lr_stats_avgincdecrease(times_minutes=times_minutes, tec_measurements=tec_measurements["left"], temp_measurements=temp_measurements["left"], increase=False)
    left_temp_dec_str = f"Mean temperature decrease when TEC is ON: {median_var:+.3f}°C/min"
    median_var = lr_stats_avgincdecrease(times_minutes=times_minutes, tec_measurements=tec_measurements["right"], temp_measurements=temp_measurements["right"], increase=False)
    right_temp_dec_str = f"Mean temperature decrease when TEC is ON: {median_var:+.3f}°C/min"

    # tec based stats
    avg_var = side_stats_avgteconoffincreasedecrease(times_minutes=times_minutes, tec_measurements=tec_measurements["left"], temp_measurements=temp_measurements["left"], increase=False)
    left_tecb_tempdec = f"Mean temperature decrease between TEC switches: {avg_var:+.3f}°C/min"
    avg_var = side_stats_avgteconoffincreasedecrease(times_minutes=times_minutes, tec_measurements=tec_measurements["left"], temp_measurements=temp_measurements["left"], increase=True)
    left_tecb_tempinc = f"Mean temperature increase between TEC switches: {avg_var:+.3f}°C/min"
    avg_var = side_stats_avgteconoffincreasedecrease(times_minutes=times_minutes, tec_measurements=tec_measurements["right"], temp_measurements=temp_measurements["right"], increase=False)
    right_tecb_tempdec = f"Mean temperature decrease between TEC switches: {avg_var:+.3f}°C/min"
    avg_var = side_stats_avgteconoffincreasedecrease(times_minutes=times_minutes, tec_measurements=tec_measurements["right"], temp_measurements=temp_measurements["right"], increase=True)
    right_tecb_tempinc = f"Mean temperature increase between TEC switches: {avg_var:+.3f}°C/min"

    # observed cycle length
    avg_cl = float(- np.mean(np.diff(times_minutes)) * 60)
    obs_cycle_length_str = f"Observed cycle length: {avg_cl:.2f}s"

    return (
        backend_status_str,
        left_fig,
        right_fig,
        left_pct_time_on_str,
        right_pct_time_on_str,
        left_watts_str,
        right_watts_str,
        left_temp_inc_str,
        right_temp_inc_str,
        left_temp_dec_str,
        right_temp_dec_str,
        left_tecb_tempdec,
        left_tecb_tempinc,
        right_tecb_tempdec,
        right_tecb_tempinc,
        obs_cycle_length_str,
        )


if __name__ == '__main__':
    app.run(host=args.dash_ip)
