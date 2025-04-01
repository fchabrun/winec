import mariadb

mariadb_host = 'localhost'
mariadb_port = 3306
mariadb_user = 'cav'
mariadb_password = 'caveavin'
mariadb_db = 'winec'

def init_db():

    try:
        conn = mariadb.connect(
            host=mariadb_host,
            port=mariadb_port,
            user=mariadb_user,
            passwd=mariadb_password,
            database=mariadb_db
        )
    except mariadb.Error as e:
        print(f"Error connecting to MariaDB Platform: {e}")
        return False

    cur = conn.cursor()

    query = "CREATE TABLE IF NOT EXISTS temperature_measurements (time TEXT, event TEXT, left_temperature FLOAT, left_target FLOAT, left_limithi FLOAT, left_limitlo FLOAT, right_temperature FLOAT, right_target FLOAT, right_limithi FLOAT, right_limitlo FLOAT, left_tec_status BOOLEAN, right_tec_status BOOLEAN, left_tec_on_cd BOOLEAN, right_tec_on_cd BOOLEAN)"
    try:
        cur.execute(query)
    except mariadb.Error as e:
        print(f"Error executing query in MariaDB database: {e}")
        return False

    conn.close()
    return True


db_init_result = False
while not db_init_result:
    print("Attempting to init db")
    db_init_result = init_db()
    print(f"{db_init_result=}")

print("Done")
