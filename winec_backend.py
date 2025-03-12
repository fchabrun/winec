import sqlite3
import json
import os
import time
import argparse
import sys
from datetime import datetime

parser = argparse.ArgumentParser()
parser.add_argument("--mode")
parser.add_argument("--host")
parser.add_argument("--port")
parser.add_argument("--clean_db")
parser.add_argument("--clean_params")
# parser.add_argument("--clean_db", default=True)
# parser.add_argument("--clean_params", default=True)
# parser.add_argument("--rundir", default="~/Documents/winec_res")
parser.add_argument("--rundir", default=r"C:\Users\flori\OneDrive - univ-angers.fr\Documents\Home\Documents\winec\rundir")
parser.add_argument("--db", default="winec_db_v1.db")
args = parser.parse_args()

# logs
def log(s):
    with open(os.path.join(args.rundir, "winec.log"), "a") as f:
        f.write(f"{datetime.now()}: {s}" + "\n")
    
root_dir = os.path.split(sys.argv[0])[0]
log(f"appending {root_dir} to sys path")
sys.path.append(root_dir)
log(f"importing bmp180 library")
# TODO remove that
try:
    import bmp180
except:
    log("Could not load bmp180 library")

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
            "bmp180_bus": 1,  # bmp180 i2c bus
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
            jsdata = json.load(f)
            params = argparse.Namespace(**jsdata)
        log(f"loaded params from json at path {json_path}")
    except:
        log(f"no params found at path {json_path}, loading defaults")
        params = argparse.Namespace(**default_params())
        try:
            with open(json_path, "w") as f:
                json.dump(vars(params), f, indent=4)
            log(f"saved params to json at path {json_path}")
        except:
            log(f"could not save params to json at path {json_path}")
    return params

# measures, etc.
def get_current_temperatures():
    # TODO
    return 0, 0

if __name__ == "__main__":
    if args.clean_db is not None:
        clear_db()
    if args.clean_params is not None:
        clear_params()

    init_db()

    # init actuators (tecs)
    left_tec_status = 0
    right_tec_status = 0

    while True:
        # load params at every cycle in case something changed
        params = get_params()
        
        # get temperature measurements
        # TODO
        log("getting sensor measurements")
        left_temp, right_temp = get_current_temperatures()
        
        # store new temperature measurements
        log("storing measurements")
        db_store_measurements(left_temp, right_temp, left_tec_status, right_tec_status)
        
        # decide if tec has to go on or off
        log("measurement-based decision")
        # TODO
        # if (left_temp < (left_temp_target - left_temp_dev)):
        #     # turn off and store
        #     pass
        # elif (left_temp > (left_temp_target + left_temp_dev)):
        #     # turn on and store
        #     pass
        # TODO also for right
        
        # wait until next cycle
        log(f"going to sleep for {params.loop_delay_seconds} seconds")
        time.sleep(params.loop_delay_seconds)