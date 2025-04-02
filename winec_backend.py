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
parser.add_argument("--clean_db")
parser.add_argument("--clean_params")
parser.add_argument("--rundir", default="/home/cav/winec_rundir")
parser.add_argument("--left_bmp180_bus", default=1)
parser.add_argument("--left_bmp180_address", default=0x77)
parser.add_argument("--right_bmp180_bus", default=4)
parser.add_argument("--right_bmp180_address", default=0x77)
parser.add_argument("--left_tec_gpio", default=22)
parser.add_argument("--right_tec_gpio", default=23)
parser.add_argument("--db_platform", default="mariadb")
parser.add_argument("--db_host", default="localhost")
parser.add_argument("--db_port", default=3306)
parser.add_argument("--db_user", default="cav")
parser.add_argument("--db_password", default="caveavin")
parser.add_argument("--db_database", default="winec")
args = parser.parse_args()

def now():
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')


def log(s):
    print(f"{now()}    {s}")


print(f"running at {args.rundir}")

os.makedirs(args.rundir, exist_ok=True)
log(f"running at {args.rundir}")

if args.db_platform == "sqlite3":
    log("running with sqlite3")
    import sqlite3
elif args.db_platform == "mariadb":
    log("running with mariadb")
    import mariadb

root_dir = os.path.split(sys.argv[0])[0]
log(f"appending {root_dir} to sys path")
sys.path.append(root_dir)
log(f"importing bmp180 library")
from bmp180 import bmp180


def run_db_query_mariadb(query, query_args=None):

    try:
        conn = mariadb.connect(
            host=args.db_host,
            port=args.db_port,
            user=args.db_user,
            passwd=args.db_password,
            database=args.db_database
        )
    except mariadb.Error as e:
        print(f"Error connecting to MariaDB Platform: {e}")
        return False

    cur = conn.cursor()

    try:
        if query_args is None:
            cur.execute(query)
        else:
            cur.execute(query, query_args)
    except mariadb.Error as e:
        print(f"Error executing query in MariaDB database: {e}")
        return False

    conn.close()
    return True


def run_db_query_sqlite3(query):
    try:
        connection = sqlite3.connect(os.path.join(args.rundir, "winec_db_v1.db"), timeout=10)
        cursor = connection.cursor()
        cursor.execute(query)
        connection.commit()
        connection.close()
    except:
        return False
    return True


def init_db():
    if args.db_platform == "sqlite3":
        query = "CREATE TABLE IF NOT EXISTS temperature_measurements (time TEXT, event TEXT, left_temperature FLOAT, left_target FLOAT, left_limithi FLOAT, left_limitlo FLOAT, right_temperature FLOAT, right_target FLOAT, right_limithi FLOAT, right_limitlo FLOAT, left_tec_status BOOLEAN, right_tec_status BOOLEAN, left_tec_on_cd BOOLEAN, right_tec_on_cd BOOLEAN)"
        return run_db_query_sqlite3(query)
    if args.db_platform == "mariadb":
        query = "CREATE TABLE IF NOT EXISTS temperature_measurements (time DATETIME, event TEXT, left_temperature FLOAT, left_target FLOAT, left_limithi FLOAT, left_limitlo FLOAT, right_temperature FLOAT, right_target FLOAT, right_limithi FLOAT, right_limitlo FLOAT, left_tec_status BOOLEAN, right_tec_status BOOLEAN, left_tec_on_cd BOOLEAN, right_tec_on_cd BOOLEAN)"
        return run_db_query_mariadb(query)
    assert False, f"Unknown {args.db_platform=}"


def clear_db():
    if args.db_platform == "sqlite3":
        query = "DROP TABLE IF EXISTS temperature_measurements"
        return run_db_query_sqlite3(query)
    if args.db_platform == "mariadb":
        query = "DROP TABLE IF EXISTS temperature_measurements"
        return run_db_query_mariadb(query)
    assert False, f"Unknown {args.db_platform=}"


def db_store_startup():
    if args.db_platform == "sqlite3":
        query = f"INSERT INTO temperature_measurements VALUES ('{now()}', 'startup', 0, 0, 0, 0, 0, 0, 0, 0, false, false, false, false)"
        return run_db_query_sqlite3(query)
    if args.db_platform == "mariadb":
        query = f"INSERT INTO temperature_measurements (time, event, left_temperature, left_target, left_limithi, left_limitlo, right_temperature, right_target, right_limithi, right_limitlo, left_tec_status, right_tec_status, left_tec_on_cd, right_tec_on_cd) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
        query_args = (datetime.now(), 'startup', 0, 0, 0, 0, 0, 0, 0, 0, False, False, False, False)
        return run_db_query_mariadb(query, query_args)
    assert False, f"Unknown {args.db_platform=}"


def db_store_measurements(left_temp, left_target, left_limithi, left_limitlo, right_temp, right_target, right_limithi, right_limitlo, left_tec_status, right_tec_status, left_tec_on_cd, right_tec_on_cd):
    if args.db_platform == "sqlite3":
        query = f"INSERT INTO temperature_measurements VALUES ('{now()}', 'entry', {left_temp:.2f}, {left_target:.2f}, {left_limithi:.2f}, {left_limitlo:.2f}, {right_temp:.2f}, {right_target:.2f}, {right_limithi:.2f}, {right_limitlo:.2f}, {left_tec_status:b}, {right_tec_status:b}, {left_tec_on_cd:b}, {right_tec_on_cd:b})"
        return run_db_query_sqlite3(query)
    if args.db_platform == "mariadb":
        query = f"INSERT INTO temperature_measurements (time, event, left_temperature, left_target, left_limithi, left_limitlo, right_temperature, right_target, right_limithi, right_limitlo, left_tec_status, right_tec_status, left_tec_on_cd, right_tec_on_cd) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
        query_args = (datetime.now(), 'entry', left_temp, left_target, left_limithi, left_limitlo, right_temp, right_target, right_limithi, right_limitlo, left_tec_status, right_tec_status, left_tec_on_cd, right_tec_on_cd)
        return run_db_query_mariadb(query, query_args)
    assert False, f"Unknown {args.db_platform=}"


# settings
def default_params():
    params = {
        "loop_delay_seconds": 1,
        "left": {
            "status": True,
            "target_temperature": 12.0,  # target temperature
            "temperature_deviation": 1.0,  # the algorithm will tolerate values between target - dev and target + dev before switching tec on/off
            "tec_cooldown_seconds": 60,  # the tec won't be activated again before waiting for the end of the cooldown delay
        },
        "right": {
            "status": True,
            "target_temperature": 12.0,  # target temperature
            "temperature_deviation": 1.0,  # the algorithm will tolerate values between target - dev and target + dev before switching tec on/off
            "tec_cooldown_seconds": 60,  # the tec won't be activated again before waiting for the end of the cooldown delay
        }
    }
    return params


def clear_params():
    json_path = os.path.join(args.rundir, "settings.json")
    if os.path.exists(json_path):
        os.remove(json_path)
        log("successfully removed params file")
        return True
    log("params file does not exist, no change")
    return False


def get_params():
    json_path = os.path.join(args.rundir, "settings.json")
    try:
        with open(json_path, "r") as f:
            params = json.load(f)
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
    # log("getting sensor measurements")
    left_temp, right_temp = None, None
    try:
        left_temp = left_bmp.get_temp()
    except:
        log("unable to retrieve left sensor measurement")
    try:
        right_temp = right_bmp.get_temp()
    except:
        log("unable to retrieve right sensor measurement")
    return left_temp, right_temp
    
    
def init_tec(pin):
    log(f"initializing tec at gpio {pin=}")
    tec = None
    try:
        tec = LED(pin)
        tec.off()
    except:
        log("unable to initialize tec at gpio")
    return tec


def tec_on_cd(tec_status, last_switched, tec_cooldown):
    if tec_status:
        return False
    if last_switched is None:
        return False
    return time.time() - last_switched < tec_cooldown


SECURITY_LO_TEMP = 0
SECURITY_HI_TEMP = 40


def security_shutdown(left_tec, right_tec):
    success = False
    log("running security shutdown")
    while not success:
        try:
            left_tec.off()
            right_tec.off()
            left_tec_status = False
            right_tec_status = False
            success = True
        except:
            log("unable to run security shutdown, retrying in 1 second")
            time.sleep(1)
            continue
    log("successfully executed security shutdown")


if __name__ == "__main__":
    if args.clean_db is not None:
        log("executing db clear")
        query_result = clear_db()
        if not query_result:
            log("unable to execute db clear query")
    if args.clean_params is not None:
        log("executing params clear")
        clear_params()

    # initialize db
    query_status = False
    log("initializing database")
    while not query_status:
        query_status = init_db()
        if query_status:
            break
        else:
            log("unable to initialized database, retrying in 5 seconds")
        time.sleep(5)
    log("database successfully initialized")
    # store startup event and time
    query_status = db_store_startup()
    if not query_status:
        log("unable to log startup entry into database")
    
    # init actuators (tecs)
    left_tec, right_tec = None, None
    while left_tec is None:
        left_tec = init_tec(args.left_tec_gpio)
        if left_tec is not None:
            break
        else:
            log(f"unable to initialize left tec at {args.left_tec_gpio=}, retrying in 5 seconds")
        time.sleep(5)
    log(f"successfully intialized left tec at {args.left_tec_gpio=}")
    while right_tec is None:
        right_tec = init_tec(args.right_tec_gpio)
        if right_tec is not None:
            break
        else:
            log(f"unable to initialize right tec at {args.right_tec_gpio=}, retrying in 5 seconds")
        time.sleep(5)
    log(f"successfully intialized right tec at {args.right_tec_gpio=}")
    left_tec_status = False
    right_tec_status = False
    left_last_switched, right_last_switched = None, None

    # init sensors
    left_bmp, right_bmp = None, None
    while left_bmp is None:
        left_bmp = bmp180(args.left_bmp180_bus, args.left_bmp180_address)
        if left_bmp is not None:
            break
        else:
            log(f"unable to initialize left bmp with {args.left_bmp180_bus=} and {args.left_bmp180_address=}, retrying in 5 seconds")
        time.sleep(5)
    log(f"successfully intialized left bmp with {args.left_bmp180_bus=} and {args.left_bmp180_address=}")
    while right_bmp is None:
        right_bmp = bmp180(args.right_bmp180_bus, args.right_bmp180_address)
        if right_bmp is not None:
            break
        else:
            log(f"unable to initialize left bmp with {args.right_bmp180_bus=} and {args.right_bmp180_address=}, retrying in 5 seconds")
        time.sleep(5)
    log(f"successfully intialized left bmp with {args.right_bmp180_bus=} and {args.right_bmp180_address=}")

    params = None

    while True:
        # log("loop iteration")

        # load params at every cycle in case something changed
        new_params = None
        while new_params is None:
            new_params = get_params()
            if new_params is not None:  # could retrieve new params
                params = new_params
                break
            elif params is not None:  # could not retrieve but can run on older params
                log("unable to retrieve new params, running on old params")
                break
            else:  # no params at all: waiting until params are found
                log("unable to retrieve params, retrying in 5 seconds")
                time.sleep(5)

        # get temperature measurements
        left_temp, right_temp = get_current_temperatures()
        if (left_temp is None) or (right_temp is  None):  # problem retrieving temperatures: security shutdown
            log("unable to retrieve temperatures")
            security_shutdown(left_tec, right_tec)

        if (left_temp < SECURITY_LO_TEMP) or (left_temp > SECURITY_HI_TEMP):
            log(f"inconsistent {left_temp=}")
            security_shutdown(left_tec, right_tec)

        if (right_temp < SECURITY_LO_TEMP) or (right_temp > SECURITY_HI_TEMP):
            log(f"inconsistent {right_temp=}")
            security_shutdown(left_tec, right_tec)

        # store new temperature measurements
        query_status = db_store_measurements(left_temp, params["left"]["target_temperature"], params["left"]["target_temperature"] + params["left"]["temperature_deviation"], params["left"]["target_temperature"] - params["left"]["temperature_deviation"],
                                             right_temp, params["right"]["target_temperature"], params["right"]["target_temperature"] + params["right"]["temperature_deviation"], params["right"]["target_temperature"] - params["right"]["temperature_deviation"],
                                             left_tec_status, right_tec_status,
                                             tec_on_cd(tec_status=left_tec_status, last_switched=left_last_switched, tec_cooldown=params["left"]["tec_cooldown_seconds"]),
                                             tec_on_cd(tec_status=right_tec_status, last_switched=right_last_switched, tec_cooldown=params["right"]["tec_cooldown_seconds"]))
        if not query_status:
            log("unable to store measurements in database")

        # decide if tec has to go on or off
        # log("measurement-based decision")
        try:
            if (left_tec_status) & (left_temp < (params["left"]["target_temperature"] - params["left"]["temperature_deviation"])):
                # turn off and store
                log("turning left tec off")
                left_tec.off()
                left_tec_status = False
                left_last_switched = time.time()
            elif (not left_tec_status) & (left_temp > (params["left"]["target_temperature"] + params["left"]["temperature_deviation"])):
                # before turning on, checked that the CD is off
                if (left_last_switched is None) or (time.time() - left_last_switched > params["left"]["tec_cooldown_seconds"]):
                    # turn on and store
                    log("turning left tec on")
                    left_last_switched = time.time()
                    left_tec.on()
                    left_tec_status = True
            # also for right
            if (right_tec_status) & (right_temp < (params["right"]["target_temperature"] - params["right"]["temperature_deviation"])):
                # turn off and store
                log("turning right tec off")
                right_tec.off()
                right_tec_status = False
                right_last_switched = time.time()
            elif (not right_tec_status) & (right_temp > (params["right"]["target_temperature"] + params["right"]["temperature_deviation"])):
                # before turning on, checked that the CD is off
                if (right_last_switched is None) or (time.time() - right_last_switched > params["right"]["tec_cooldown_seconds"]):
                    # turn on and store
                    log("turning right tec on")
                    right_last_switched = time.time()
                    right_tec.on()
                    right_tec_status = True
        except:
            log("error during temp-based tec decision")
            security_shutdown(left_tec=left_tec, right_tec=right_tec)

        # TODO security: measure radiators temperature and emergency shutdown if abnormal

        # wait until next cycle
        # log(f"going to sleep for {params['loop_delay_seconds']} seconds")
        time.sleep(params["loop_delay_seconds"])
