import sqlite3
import json
import os
import time

ROOT_DIR = "~/Documents/winec"
DB_NAME = "winec_db_v1.db"

# measurements
def init_db():
    connection = sqlite3.connect(DB_NAME)
    cursor = connection.cursor()
    cursor.execute("CREATE TABLE IF NOT EXISTS temperature_measurements (time DATETIME, left_temperature FLOAT, right_temperature FLOAT, left_tec_status BOOLEAN, right_tec_status BOOLEAN)")
    connection.commit()
    connection.close()
    
def db_store_measurements(left_temp, right_temp, left_tec_status, right_tec_status):
    connection = sqlite3.connect(DB_NAME)
    cursor = connection.cursor()
    cursor.execute(f"INSERT INTO temperature_measurements VALUES (DateTime('now'), {left_temp:.2f}, {right_temp:.2f}, {left_tec_status:b}, {right_tec_status:b})")
    connection.commit()
    connection.close()

# settings
def default_params():
    params = {
        "loop_delay_seconds": 60,
    }
    return params

def load_params():
    json_path = os.path.join(ROOT_DIR, "settings.json")
    try:
        with open(json_path, "r") as f:
            params = json.load(f)
        print(f"loaded params from json at path {json_path}")
    except:
        print(f"no params found at path {json_path}, loading defaults")
        params = default_params()
        try:
            with open(json_path, "w") as f:
                json.dump(params, f)
            print(f"saved params to json at path {json_path}")
        except:
            print(f"could not save params to json at path {json_path}")
    return params
    
if __name__ == "__main__":
    while True:
        # load params at every cycle in case something changed
        params = load_params()
        
        # get temperature measurements
        # TODO
        left_temp, right_temp = get_current_temperatures()
        
        # store new temperature measurements
        db_store_measurements(left_temp, right_temp, left_tec_status, right_tec_status)
        
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