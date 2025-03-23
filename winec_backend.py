import sqlite3
import json
import os
import time
import argparse
import sys
from datetime import datetime
from gpiozero import LED

parser = argparse.ArgumentParser()
parser.add_argument("--mode")
parser.add_argument("--host")
parser.add_argument("--port")
# parser.add_argument("--clean_db")
# parser.add_argument("--clean_params")
parser.add_argument("--clean_db", default=True)
parser.add_argument("--clean_params", default=True)
parser.add_argument("--rundir", default="/home/cav/winec_rundir")
parser.add_argument("--left_bmp180_bus", default=1)
parser.add_argument("--left_bmp180_address", default=0x77)
parser.add_argument("--right_bmp180_bus", default=4)
parser.add_argument("--right_bmp180_address", default=0x77)
parser.add_argument("--left_tec_gpio", default=22)
parser.add_argument("--right_tec_gpio", default=23)
# parser.add_argument("--rundir", default=r"C:\Users\flori\OneDrive - univ-angers.fr\Documents\Home\Documents\winec\rundir")
args = parser.parse_args()

print(f"running at {args.rundir}")

# logs
def log(s):
    with open(os.path.join(args.rundir, "winec.log"), "a") as f:
        f.write(f"{datetime.now()}    {s}" + "\n")
        
os.makedirs(args.rundir, exist_ok=True)
log(f"running at {args.rundir}")
    
root_dir = os.path.split(sys.argv[0])[0]
log(f"appending {root_dir} to sys path")
sys.path.append(root_dir)
log(f"importing bmp180 library")
from bmp180 import bmp180

# sqlite3 db
def init_db():
    log("intializing db")
    connection = sqlite3.connect(os.path.join(args.rundir, "winec_db_v1.db"))
    cursor = connection.cursor()
    cursor.execute("CREATE TABLE IF NOT EXISTS temperature_measurements (time DATETIME, left_temperature FLOAT, left_target FLOAT, left_limithi FLOAT, left_limitlo FLOAT, right_temperature FLOAT, right_target FLOAT, right_limithi FLOAT, right_limitlo FLOAT, left_tec_status BOOLEAN, right_tec_status BOOLEAN)")
    connection.commit()
    connection.close()
    log("initialized db")
    
def clear_db():
    log("cleaning db")
    connection = sqlite3.connect(os.path.join(args.rundir, "winec_db_v1.db"))
    cursor = connection.cursor()
    cursor.execute("DROP TABLE IF EXISTS temperature_measurements")
    connection.commit()
    connection.close()
    
def db_store_measurements(left_temp, left_target, left_limithi, left_limitlo, right_temp, right_target, right_limithi, right_limitlo, left_tec_status, right_tec_status):
    log("storing measurements into db")
    connection = sqlite3.connect(os.path.join(args.rundir, "winec_db_v1.db"))
    cursor = connection.cursor()
    cursor.execute(f"INSERT INTO temperature_measurements VALUES (DateTime('now'), {left_temp:.2f}, {left_target:.2f}, {left_limithi:.2f}, {left_limitlo:.2f}, {right_temp:.2f}, {right_target:.2f}, {right_limithi:.2f}, {right_limitlo:.2f}, {left_tec_status:b}, {right_tec_status:b})")
    connection.commit()
    connection.close()

# settings
def default_params():
    params = {
        "loop_delay_seconds": 1,
        "left": {
            "status": True,
            "target_temperature": 12.0,  # target temperature
            "temperature_deviation": 2.0,  # the algorithm will tolerate values between target - dev and target + dev before switching tec on/off
            "tec_cooldown_minutes": 5.0,  # the tec won't be activated again before waiting for the end of the cooldown delay
        },
        "right": {
            "status": True,
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
    log("getting sensor measurements")
    left_temp = left_bmp.get_temp()
    right_temp = right_bmp.get_temp()
    return left_temp, right_temp
    
    
def init_tec(pin):
    log(f"initializing tec at gpio {pin=}")
    tec = LED(pin)
    tec.off()
    return tec


if __name__ == "__main__":
    if args.clean_db is not None:
        clear_db()
    if args.clean_params is not None:
        clear_params()

    init_db()
    
    # init actuators (tecs)
    left_tec = init_tec(args.left_tec_gpio)
    right_tec = init_tec(args.right_tec_gpio)
    left_tec_status = 0
    right_tec_status = 0

    # init sensors
    left_bmp = bmp180(args.left_bmp180_bus, args.left_bmp180_address)
    right_bmp = bmp180(args.right_bmp180_bus, args.right_bmp180_address)

    while True:
        log("loop iteration")

        # load params at every cycle in case something changed
        params = get_params()

        # get temperature measurements
        left_temp, right_temp = get_current_temperatures()
        
        # store new temperature measurements
        db_store_measurements(left_temp, params["left"]["target_temperature"], params["left"]["target_temperature"] + params["left"]["temperature_deviation"], params["left"]["target_temperature"] - params["left"]["temperature_deviation"],
                              right_temp, params["right"]["target_temperature"], params["right"]["target_temperature"] + params["right"]["temperature_deviation"], params["right"]["target_temperature"] - params["right"]["temperature_deviation"],
                              left_tec_status, right_tec_status)
        
        # decide if tec has to go on or off
        log("measurement-based decision")
        if (left_tec_status == 1) & (left_temp < (params["left"]["target_temperature"] - params["left"]["temperature_deviation"])):
            # turn off and store
            # TODO handle cooldown
            left_tec.off()
            left_tec_status = 0
        elif (left_tec_status == 0) & (left_temp > (params["left"]["target_temperature"] + params["left"]["temperature_deviation"])):
            # turn on and store
            # TODO handle cooldown
            left_tec.on()
            left_tec_status = 1
        # also for right
        if (right_tec_status == 1) & (right_temp < (params["right"]["target_temperature"] - params["right"]["temperature_deviation"])):
            # turn off and store
            # TODO handle cooldown
            right_tec.off()
            right_tec_status = 0
        elif (right_tec_status == 0) & (right_temp > (params["right"]["target_temperature"] + params["right"]["temperature_deviation"])):
            # turn on and store
            # TODO handle cooldown
            right_tec.on()
            right_tec_status = 1

        # TODO security: if aberrant temp, just set everything off and exit

        # TODO security: measure tachymeter, if abnormal (e.g. off) : set everything off and exit
        
        # wait until next cycle
        log(f"going to sleep for {params['loop_delay_seconds']} seconds")
        time.sleep(params["loop_delay_seconds"])
