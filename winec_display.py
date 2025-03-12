import argparse
import sqlite3
import pandas as pd

parser = argparse.ArgumentParser()
parser.add_argument("--mode")
parser.add_argument("--host")
parser.add_argument("--port")
# parser.add_argument("--rundir", default="~/Documents/winec_res")
parser.add_argument("--rundir", default=r"C:\Users\flori\OneDrive - univ-angers.fr\Documents\Home\Documents\winec\rundir")
parser.add_argument("--db", default="winec_db_v1.db")
args = parser.parse_args()

# get temp/tec status measurements over the last X minutes, formatted as a pandas dataframe
def db_store_measurements(minutes):
    connection = sqlite3.connect(args.db)
    cursor = connection.cursor()
    cursor.execute(f"SELECT time, left_temperature, right_temperature, left_tec_status, right_tec_status FROM temperature_measurements WHERE time > DATETIME('now', '-{minutes} minute')")  # execute a simple SQL select query
    query_results = cursor.fetchall()
    connection.commit()
    connection.close()
    output_data = pd.DataFrame(query_results, columns=["Time", "Temperature (left)", "Temperature (right)", "TEC status (left)", "TEC status (right)"])
    return output_data

if __name__ == "__main__":
    query_results = db_store_measurements(minutes=120)
    print(query_results.to_string())
