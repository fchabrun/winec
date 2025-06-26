import json
import os
import time
import argparse
import sys
import socket
from datetime import datetime
from gpiozero import LED

parser = argparse.ArgumentParser()
parser.add_argument("--mode")
parser.add_argument("--host")
parser.add_argument("--port")
parser.add_argument("--clean_db")
parser.add_argument("--clean_params")
parser.add_argument("--rundir", default="/home/cav/winec_rundir")
# sensors and actuators
parser.add_argument("--left_bmp180_bus", default=1)
parser.add_argument("--left_bmp180_address", default=0x77)
parser.add_argument("--right_bmp180_bus", default=4)
parser.add_argument("--right_bmp180_address", default=0x77)
parser.add_argument("--left_tec_gpio", default=22)
parser.add_argument("--right_tec_gpio", default=23)
parser.add_argument("--w1_rootdir", default='/sys/bus/w1/devices/')
parser.add_argument("--left_heatsink_temp_address", default='000000bc51c5')
parser.add_argument("--right_heatsink_temp_address", default='000000bb35e7')
# db
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


log(f"running at {args.rundir}")

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
log(f"importing ds18b20 library")
from ds18b20 import ds18b20


def run_db_query_mariadb(query, query_args=None):
    try:
        conn = mariadb.connect(
            host=args.db_host,
            port=args.db_port,
            user=args.db_user,
            passwd=args.db_password,
            database=args.db_database
        )
    except mariadb.Error as error:
        log("Error connecting to MariaDB Platform")
        log(f"{error=}")
        return False

    cur = conn.cursor()

    try:
        if query_args is None:
            cur.execute(query)
        else:
            cur.execute(query, query_args)
    except mariadb.Error as error:
        log("Error executing query in MariaDB database")
        log(f"{error=}")
        return False

    conn.commit()
    conn.close()
    return True


def run_db_query_sqlite3(query):
    try:
        connection = sqlite3.connect(os.path.join(args.rundir, "winec_db_v1.db"), timeout=10)
        cursor = connection.cursor()
        cursor.execute(query)
        connection.commit()
        connection.close()
    except Exception as error:
        log(f"{error=}")
        return False
    return True


def init_db():
    if args.db_platform == "sqlite3":
        query = "CREATE TABLE IF NOT EXISTS temperature_measurements (time TEXT, event TEXT, left_temperature FLOAT, left_target FLOAT, left_limithi FLOAT, left_limitlo FLOAT, left_heatsink_temperature FLOAT, right_temperature FLOAT, right_target FLOAT, right_limithi FLOAT, right_limitlo FLOAT, right_heatsink_temperature FLOAT, left_tec_status BOOLEAN, right_tec_status BOOLEAN, left_tec_on_cd BOOLEAN, right_tec_on_cd BOOLEAN)"
        return run_db_query_sqlite3(query)
    if args.db_platform == "mariadb":
        query = "CREATE TABLE IF NOT EXISTS temperature_measurements (time DATETIME, event TEXT, left_temperature FLOAT, left_target FLOAT, left_limithi FLOAT, left_limitlo FLOAT, left_heatsink_temperature FLOAT, right_temperature FLOAT, right_target FLOAT, right_limithi FLOAT, right_limitlo FLOAT, right_heatsink_temperature FLOAT, left_tec_status BOOLEAN, right_tec_status BOOLEAN, left_tec_on_cd BOOLEAN, right_tec_on_cd BOOLEAN)"
        return run_db_query_mariadb(query)
    log(f"Unknown {args.db_platform=}")
    return False


def clear_db():
    if args.db_platform == "sqlite3":
        query = "DROP TABLE IF EXISTS temperature_measurements"
        return run_db_query_sqlite3(query)
    if args.db_platform == "mariadb":
        query = "DROP TABLE IF EXISTS temperature_measurements"
        return run_db_query_mariadb(query)
    log(f"Unknown {args.db_platform=}")
    return False


def db_clean(days_old_filter: int):
    if args.db_platform == "mariadb":
        dt_max_date_keep = (datetime.now() - timedelta(days=days_old_filter)).strftime('%Y-%m-%d %H:%M:%S')
        query = f"DELETE FROM temperature_measurements WHERE time < '{dt_max_date_keep}'"
        return run_db_query_mariadb(query)
    log(f"Unknown {args.db_platform=}")
    return False


def db_store_startup():
    if args.db_platform == "sqlite3":
        query = f"INSERT INTO temperature_measurements VALUES ('{now()}', 'startup', 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, false, false, false, false)"
        return run_db_query_sqlite3(query)
    if args.db_platform == "mariadb":
        query = f"INSERT INTO temperature_measurements (time, event, left_temperature, left_target, left_limithi, left_limitlo, left_heatsink_temperature, right_temperature, right_target, right_limithi, right_limitlo, right_heatsink_temperature, left_tec_status, right_tec_status, left_tec_on_cd, right_tec_on_cd) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
        query_args = (datetime.now(), 'startup', 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, False, False, False, False)
        return run_db_query_mariadb(query, query_args)
    log(f"Unknown {args.db_platform=}")
    return False


def db_store_measurements(left_temp, left_target, left_limithi, left_limitlo, left_heatsink_temp, right_temp, right_target, right_limithi, right_limitlo, right_heatsink_temp, left_tec_status, right_tec_status, left_tec_on_cd, right_tec_on_cd):
    if args.db_platform == "sqlite3":
        query = f"INSERT INTO temperature_measurements VALUES ('{now()}', 'entry', {left_temp:.2f}, {left_target:.2f}, {left_limithi:.2f}, {left_limitlo:.2f}, {left_heatsink_temp:.2f}, {right_temp:.2f}, {right_target:.2f}, {right_limithi:.2f}, {right_limitlo:.2f}, {right_heatsink_temp:.2f}, {left_tec_status:b}, {right_tec_status:b}, {left_tec_on_cd:b}, {right_tec_on_cd:b})"
        return run_db_query_sqlite3(query)
    if args.db_platform == "mariadb":
        query = f"INSERT INTO temperature_measurements (time, event, left_temperature, left_target, left_limithi, left_limitlo, left_heatsink_temperature, right_temperature, right_target, right_limithi, right_limitlo, right_heatsink_temperature, left_tec_status, right_tec_status, left_tec_on_cd, right_tec_on_cd) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
        query_args = (datetime.now(), 'entry', left_temp, left_target, left_limithi, left_limitlo, left_heatsink_temp, right_temp, right_target, right_limithi, right_limitlo, right_heatsink_temp, left_tec_status, right_tec_status, left_tec_on_cd, right_tec_on_cd)
        return run_db_query_mariadb(query, query_args)
    log(f"Unknown {args.db_platform=}")
    return False


# settings
def default_params():
    params = {
        "loop_delay_seconds": 10,
        "bmp180_security_temp_lo": 0,
        "bmp180_security_temp_hi": 40,
        "heatsink_security_temp_lo": 0,
        "heatsink_security_temp_hi": 80,
        "esp_udp_refresh_delay": 5,
        "auto_remove_older_than_days": 7,
        "left": {
            "status": True,
            "target_temperature": 12.0,  # target temperature
            "temperature_deviation": 0.5,  # the algorithm will tolerate values between target - dev and target + dev before switching tec on/off
            "tec_cooldown_seconds": 60,  # the tec won't be activated again before waiting for the end of the cooldown delay
            "esp_udp_ip": "192.168.1.2",
            "esp_udp_port": 4210
        },
        "right": {
            "status": True,
            "target_temperature": 12.0,  # target temperature
            "temperature_deviation": 0.5,  # the algorithm will tolerate values between target - dev and target + dev before switching tec on/off
            "tec_cooldown_seconds": 60,  # the tec won't be activated again before waiting for the end of the cooldown delay
            "esp_udp_ip": "192.168.1.32",
            "esp_udp_port": 4210
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
    except Exception as error:
        log(f"no params found at path {json_path}, loading defaults")
        log(f"{error=}")
        params = default_params()
        try:
            with open(json_path, "w") as f:
                json.dump(params, f, indent=4)
            log(f"saved params to json at path {json_path}")
        except Exception as error:
            log(f"could not save params to json at path {json_path}")
            log(f"{error=}")
    return params


# measures, etc.
def get_current_temperatures():
    # log("getting sensor measurements")
    left_temp, right_temp = None, None
    try:
        left_temp = left_bmp.get_temp()
    except Exception as error:
        log("unable to retrieve left sensor measurement")
        log(f"{error=}")
    try:
        right_temp = right_bmp.get_temp()
    except Exception as error:
        log("unable to retrieve right sensor measurement")
        log(f"{error=}")
    return left_temp, right_temp


class tec_instance():
    def __init__(self, pin):
        self.pin = pin
        self.tec = None
        self.status = False
        self.last_switched = None

    def initialize(self):
        log(f"initializing tec at gpio {self.pin=}")
        self.tec = None
        try:
            self.tec = LED(self.pin)
            self.tec.off()
        except Exception as error:
            self.tec = None
            log("unable to initialize tec")
            log(f"{error=}")

    def turn(self, onoff):
        if self.tec is not None:
            if onoff:
                self.tec.on()
            else:
                self.tec.off()
        else:
            log("unable to turn tec on/off: not initialized")
        self.status = onoff
        if not self.status:  # tec was turned off: run cooldown
            self.last_switched = time.time()

    def turn_on(self):
        self.turn(onoff=True)

    def turn_off(self):
        self.turn(onoff=False)

    def running(self):
        return self.tec is not None

    def on_cd(self, cooldown):
        if self.status:
            return False
        if self.last_switched is None:
            return False
        return time.time() - self.last_switched < cooldown


def security_shutdown(sd_left_tec_instance, sd_right_tec_instance):
    success = False
    log("running security shutdown")
    while not success:
        try:
            sd_left_tec_instance.turn_off()
            sd_right_tec_instance.turn_off()
            success = True
        except Exception as error:
            log("unable to run security shutdown, retrying in 1 second")
            log(f"{error=}")
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

    # initialize udp
    log("setting up udp socket")
    sock = socket.socket(socket.AF_INET, # Internet
                         socket.SOCK_DGRAM) # UDP
    log("udp initialized")

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
    left_tec_instance = tec_instance(args.left_tec_gpio)
    right_tec_instance = tec_instance(args.right_tec_gpio)
    while True:
        left_tec_instance.initialize()
        if left_tec_instance.running():
            break
        else:
            log(f"unable to initialize left tec at {args.left_tec_gpio=}, retrying in 5 seconds")
        time.sleep(5)
    log(f"successfully intialized left tec at {args.left_tec_gpio=}")
    while True:
        right_tec_instance.initialize()
        if right_tec_instance.running():
            break
        else:
            log(f"unable to initialize right tec at {args.right_tec_gpio=}, retrying in 5 seconds")
        time.sleep(5)
    log(f"successfully intialized right tec at {args.right_tec_gpio=}")

    # init heatsink tmp sensors
    left_heatsink_ds18b20 = ds18b20(address=args.left_heatsink_temp_address, rootdir=args.w1_rootdir)
    right_heatsink_ds18b20 = ds18b20(address=args.right_heatsink_temp_address, rootdir=args.w1_rootdir)

    # init sensors
    left_bmp, right_bmp = None, None
    while left_bmp is None:
        try:
            left_bmp = bmp180(args.left_bmp180_bus, args.left_bmp180_address)
        except Exception as error:
            log(f"{error=}")
        if left_bmp is not None:
            break
        else:
            log(f"unable to initialize left bmp with {args.left_bmp180_bus=} and {args.left_bmp180_address=}, retrying in 5 seconds")
        time.sleep(5)
    log(f"successfully intialized left bmp with {args.left_bmp180_bus=} and {args.left_bmp180_address=}")
    while right_bmp is None:
        try:
            right_bmp = bmp180(args.right_bmp180_bus, args.right_bmp180_address)
        except Exception as error:
            log(f"{error=}")
        if right_bmp is not None:
            break
        else:
            log(f"unable to initialize left bmp with {args.right_bmp180_bus=} and {args.right_bmp180_address=}, retrying in 5 seconds")
        time.sleep(5)
    log(f"successfully intialized left bmp with {args.right_bmp180_bus=} and {args.right_bmp180_address=}")

    params = None
    last_iteration_time = None
    last_udp_update = None
    left_temp, right_temp = None, None

    while True:
        if last_iteration_time is None or (time.time() - last_iteration_time >= params["loop_delay_seconds"]):
            last_iteration_time = time.time()
    
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
                security_shutdown(left_tec_instance, right_tec_instance)
    
            if (left_temp < params["bmp180_security_temp_lo"]) or (left_temp > params["bmp180_security_temp_hi"]):
                log(f"inconsistent {left_temp=}")
                security_shutdown(left_tec_instance, right_tec_instance)
    
            if (right_temp < params["bmp180_security_temp_lo"]) or (right_temp > params["bmp180_security_temp_hi"]):
                log(f"inconsistent {right_temp=}")
                security_shutdown(left_tec_instance, right_tec_instance)
    
            # get heatsink temperature measurements
            left_heatsink_temp, right_heatsink_temp = None, None
            try:
                left_heatsink_temp = left_heatsink_ds18b20.read_temp()
            except Exception as error:
                log("unable to read left heatsink temperature")
                log(f"{error=}")
            try:
                right_heatsink_temp = right_heatsink_ds18b20.read_temp()
            except Exception as error:
                log("unable to read right heatsink temperature")
                log(f"{error=}")
            # turn tecs off if temperatures are too low (inconsistent?) or high (too hot!)
            if (left_heatsink_temp is None) or (right_heatsink_temp is None):
                security_shutdown(left_tec_instance, right_tec_instance)
            else:
                if left_heatsink_temp < params["heatsink_security_temp_lo"]:
                    log(f"reached too low left heatsink temperature {left_heatsink_temp=}, shutting down left tec")
                    left_tec_instance.turn_off()
                elif left_heatsink_temp > params["heatsink_security_temp_hi"]:
                    log(f"reached too high left heatsink temperature {left_heatsink_temp=}, shutting down left tec")
                    left_tec_instance.turn_off()
                if right_heatsink_temp < params["heatsink_security_temp_lo"]:
                    log(f"reached too low left heatsink temperature {right_heatsink_temp=}, shutting down left tec")
                    right_tec_instance.turn_off()
                elif right_heatsink_temp > params["heatsink_security_temp_hi"]:
                    log(f"reached too high left heatsink temperature {right_heatsink_temp=}, shutting down left tec")
                    right_tec_instance.turn_off()
    
            # store new temperature measurements
            query_status = db_store_measurements(left_temp, params["left"]["target_temperature"], params["left"]["target_temperature"] + params["left"]["temperature_deviation"], params["left"]["target_temperature"] - params["left"]["temperature_deviation"],
                                                 left_heatsink_temp,
                                                 right_temp, params["right"]["target_temperature"], params["right"]["target_temperature"] + params["right"]["temperature_deviation"], params["right"]["target_temperature"] - params["right"]["temperature_deviation"],
                                                 right_heatsink_temp,
                                                 left_tec_instance.status, right_tec_instance.status,
                                                 left_tec_instance.on_cd(params["left"]["tec_cooldown_seconds"]),
                                                 right_tec_instance.on_cd(params["right"]["tec_cooldown_seconds"]))
            if not query_status:
                log("unable to store measurements in database")
    
            # decide if tec has to go on or off
            # log("measurement-based decision")
            try:
                if left_tec_instance.status & (left_temp < (params["left"]["target_temperature"] - params["left"]["temperature_deviation"])):
                    # turn off and store
                    log("turning left tec off")
                    left_tec_instance.turn_off()
                elif (not left_tec_instance.status) & (left_temp > (params["left"]["target_temperature"] + params["left"]["temperature_deviation"])):
                    # before turning on, checked that the CD is off
                    if not left_tec_instance.on_cd(params["left"]["tec_cooldown_seconds"]):
                        # turn on and store
                        log("turning left tec on")
                        left_tec_instance.turn_on()
                # also for right
                if right_tec_instance.status & (right_temp < (params["right"]["target_temperature"] - params["right"]["temperature_deviation"])):
                    # turn off and store
                    log("turning right tec off")
                    right_tec_instance.turn_off()
                elif (not right_tec_instance.status) & (right_temp > (params["right"]["target_temperature"] + params["right"]["temperature_deviation"])):
                    # before turning on, checked that the CD is off
                    if not right_tec_instance.on_cd(params["right"]["tec_cooldown_seconds"]):
                        # turn on and store
                        log("turning right tec on")
                        right_tec_instance.turn_on()
            except Exception as error:
                log("error during temp-based tec decision")
                log(f"{error=}")
                security_shutdown(left_tec_instance, right_tec_instance)

            # clean old entries
            db_clean(params["auto_remove_older_than_days"])

            # wait until next cycle
            # log(f"going to sleep for {params['loop_delay_seconds']} seconds")

        if last_udp_update is None or (time.time() - last_udp_update >= params["esp_udp_refresh_delay"]):
            last_udp_update = time.time()

            # send udp message
            UDP_MESSAGE = ""
            if (left_temp is None):
                UDP_MESSAGE += "0000"
            else:
                UDP_MESSAGE += f"{int(round(left_temp*10)):03}1"
            if (right_temp is None):
                UDP_MESSAGE += "0000"
            else:
                UDP_MESSAGE += f"{int(round(right_temp*10)):03}1"
            if len(UDP_MESSAGE ) == 8:
                try:
                    sock.sendto(bytes(UDP_MESSAGE, "utf-8"), (params["left"]["esp_udp_ip"], params["left"]["esp_udp_port"]))
                except Exception as error:
                    log("error while sending UDP packet to left esp32")
                    log(f"{error=}")
                try:
                    sock.sendto(bytes(UDP_MESSAGE, "utf-8"), (params["right"]["esp_udp_ip"], params["right"]["esp_udp_port"]))
                except Exception as error:
                    log("error while sending UDP packet to left esp32")
                    log(f"{error=}")
            else:
                log(f"invalid UDP message: {UDP_MESSAGE=}, not sent")
