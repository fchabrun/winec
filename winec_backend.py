import sqlite3
import json
import os
import time
import argparse
import sys
from datetime import datetime
# import numpy as np  # TODO remove

parser = argparse.ArgumentParser()
parser.add_argument("--mode")
parser.add_argument("--host")
parser.add_argument("--port")
# parser.add_argument("--clean_db")
# parser.add_argument("--clean_params")
parser.add_argument("--clean_db", default=True)
parser.add_argument("--clean_params", default=True)
parser.add_argument("--rundir", default="~/Documents/winec_rundir")
# parser.add_argument("--rundir", default=r"C:\Users\flori\OneDrive - univ-angers.fr\Documents\Home\Documents\winec\rundir")
parser.add_argument("--db", default="winec_db_v1.db")
args = parser.parse_args()

# logs
def log(s):
    with open(os.path.join(args.rundir, "winec.log"), "a") as f:
        f.write(f"{datetime.now()}    {s}" + "\n")
        
os.makedirs(args.rundir, exist_ok=True)
    
root_dir = os.path.split(sys.argv[0])[0]
log(f"appending {root_dir} to sys path")
sys.path.append(root_dir)
log(f"importing bmp180 library")
from bmp180 import bmp180

# sqlite3 db
def init_db():
    log("intializing db")
    connection = sqlite3.connect(args.db)
    cursor = connection.cursor()
    cursor.execute("CREATE TABLE IF NOT EXISTS temperature_measurements (time DATETIME, left_temperature FLOAT, right_temperature FLOAT, left_tec_status BOOLEAN, right_tec_status BOOLEAN)")
    connection.commit()
    connection.close()
    log("initialized db")
    
def clear_db():
    log("cleaning db")
    connection = sqlite3.connect(args.db)
    cursor = connection.cursor()
    cursor.execute("DROP TABLE IF EXISTS temperature_measurements")
    connection.commit()
    connection.close()
    
def db_store_measurements(left_temp, right_temp, left_tec_status, right_tec_status):
    log("storing measurements into db")
    connection = sqlite3.connect(args.db)
    cursor = connection.cursor()
    cursor.execute(f"INSERT INTO temperature_measurements VALUES (DateTime('now'), {left_temp:.2f}, {right_temp:.2f}, {left_tec_status:b}, {right_tec_status:b})")
    connection.commit()
    connection.close()

# settings
def default_params():
    params = {
        "loop_delay_seconds": 1,
        "left": {
            "bmp180_bus": 1,  # bmp180 i2c bus
            "bmp180_address": 0x77,  # bmp180 i2c address
            "target_temperature": 12.0,  # target temperature
            "temperature_deviation": 2.0,  # the algorithm will tolerate values between target - dev and target + dev before switching tec on/off
            "tec_cooldown_minutes": 5.0,  # the tec won't be activated again before waiting for the end of the cooldown delay
        },
        "right": {
            "bmp180_bus": 4,  # bmp180 i2c bus
            "bmp180_address": 0x77,  # bmp180 i2c address
            "target_temperature": 12.0,  # target temperature
            "temperature_deviation": 2.0,  # the algorithm will tolerate values between target - dev and target + dev before switching tec on/off
            "tec_cooldown_minutes": 5.0,  # the tec won't be activated again before waiting for the end of the cooldown delay
        }
    }
    return params

def clear_params():
    json_path = os.path.join(args.rundir, "settings.json")
    if os.path.exists(json_path):
        os.remove(json_path)
        log("successfully removed params file")
    else:
        log("params file does not exist, no change")

def get_params():
    json_path = os.path.join(args.rundir, "settings.json")
    try:
        with open(json_path, "r") as f:
            params = json.load(f)
        log(f"loaded params from json at path {json_path}")
    except:
        log(f"no params found at path {json_path}, loading defaults")
        params = default_params()
        try:
            with open(json_path, "w") as f:
                json.dump(params, f, indent=4)
            log(f"saved params to json at path {json_path}")
        except:
            log(f"could not save params to json at path {json_path}")
    return params


# measures, etc.
def get_current_temperatures():
    left_temp = left_bmp.get_temp()
    right_temp = right_bmp.get_temp()
    return left_temp, right_temp
    # return np.random.normal(loc=12, scale=1, size=None), np.random.normal(loc=12, scale=1, size=None)

if __name__ == "__main__":
    if args.clean_db is not None:
        clear_db()
    if args.clean_params is not None:
        clear_params()

    init_db()

    # init actuators (tecs)
    left_tec_status = 0
    right_tec_status = 0

    # init sensors
    left_bmp, right_bmp = None, None

    while True:
        log("loop iteration")

        # load params at every cycle in case something changed
        params = get_params()
        if (left_bmp is None) or (left_bmp.bus != params["left"]["bmp180_bus"]) or (left_bmp.address != params["left"]["bmp180_address"]):
            log(f"initializing left bmp with bus={params['left']['bmp180_bus']} and address={params['left']['bmp180_address']}")
            left_bmp = bmp180(params["left"]["bmp180_bus"], params["left"]["bmp180_address"])
        if (right_bmp is None) or (right_bmp.bus != params["right"]["bmp180_bus"]) or (right_bmp.address != params["right"]["bmp180_address"]):
            log(f"initializing left right with bus={params['right']['bmp180_bus']} and address={params['right']['bmp180_address']}")
            right_bmp = bmp180(params["right"]["bmp180_bus"], params["right"]["bmp180_address"])

        # get temperature measurements
        log("getting sensor measurements")
        left_temp, right_temp = get_current_temperatures()
        
        # store new temperature measurements
        log("storing measurements")
        db_store_measurements(left_temp, right_temp, left_tec_status, right_tec_status)
        
        # decide if tec has to go on or off
        log("measurement-based decision")
        if (left_tec_status == 1) & (left_temp < (params["left"]["target_temperature"] - params["left"]["temperature_deviation"])):
            # turn off and store
            # TODO actually turn on
            # TODO handle cooldown
            left_tec_status = 0
        elif (left_tec_status == 0) & (left_temp > (params["left"]["target_temperature"] + params["left"]["temperature_deviation"])):
            # turn on and store
            # TODO actually turn off
            # TODO handle cooldown
            left_tec_status = 1
        # TODO also for right

        # TODO security: if aberrant temp, just set everything off and exit
        
        # wait until next cycle
        log(f"going to sleep for {params['loop_delay_seconds']} seconds")
        time.sleep(params["loop_delay_seconds"])