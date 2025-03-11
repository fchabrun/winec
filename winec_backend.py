import sqlite3
import json
import os
import time
import argparse
import sys
    
root_dir = os.path.split(sys.argv[0])[0]
sys.path.append(root_dir)
import bmp180

# logs
def log(s, args):
    with open(os.path.join(args.rundir, "winec.log"), "a") as f:
        f.write(s)

# sqlite3 db
def init_db():
    log("intializing db", args)
    connection = sqlite3.connect(args.db)
    cursor = connection.cursor()
    cursor.execute("CREATE TABLE IF NOT EXISTS temperature_measurements (time DATETIME, left_temperature FLOAT, right_temperature FLOAT, left_tec_status BOOLEAN, right_tec_status BOOLEAN)")
    connection.commit()
    connection.close()
    log("initialized db", args)
    
def clear_db(args):
    connection = sqlite3.connect(args.db)
    cursor = connection.cursor()
    cursor.execute("DROP TABLE IF EXISTS temperature_measurements")
    connection.commit()
    connection.close()
    
def db_store_measurements(left_temp, right_temp, left_tec_status, right_tec_status, args):
    connection = sqlite3.connect(args.db)
    cursor = connection.cursor()
    cursor.execute(f"INSERT INTO temperature_measurements VALUES (DateTime('now'), {left_temp:.2f}, {right_temp:.2f}, {left_tec_status:b}, {right_tec_status:b})")
    connection.commit()
    connection.close()

# settings
def default_params():
    params = {
        "loop_delay_seconds": 5,
    }
    return params

def load_params(args):
    json_path = os.path.join(args.rundir, "settings.json")
    try:
        with open(json_path, "r") as f:
            params = json.load(f)
        log(f"loaded params from json at path {json_path}", args)
    except:
        log(f"no params found at path {json_path}, loading defaults", args)
        params = default_params()
        try:
            with open(json_path, "w") as f:
                json.dump(params, f)
            log(f"saved params to json at path {json_path}"; args)
        except:
            log(f"could not save params to json at path {json_path}", args)
    return params
    
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--clean")
    parser.add_argument("--rundir", default="~/Documents/winec_res")
    parser.add_argument("--db", default="winec_db_v1.db")
    args = parser.parse_args()
    
    if args.clean is not None:
        clean_db(args)

    while True:
        # load params at every cycle in case something changed
        params = load_params(args)
        
        # get temperature measurements
        # TODO
        left_temp, right_temp = get_current_temperatures()
        
        # store new temperature measurements
        db_store_measurements(left_temp, right_temp, left_tec_status, right_tec_status, args)
        
        # decide if tec has to go on or off
        # TODO
        if (left_temp < (left_temp_target - left_temp_dev)):
            # turn off and store
            pass
        elif (left_temp > (left_temp_target + left_temp_dev)):
            # turn on and store
            pass
        # TODO also for right
        
        # wait until next cycle
        time.sleep(params.loop_delay_seconds)