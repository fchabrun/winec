import mariadb

mariadb_host = '127.0.0.1'
mariadb_port = 3306
mariadb_user = 'root'
mariadb_password = ''

def init_db():

    try:
        conn = mariadb.connect(
            host=mariadb_host,
            port=mariadb_port,
            user=mariadb_user,
            passwd=mariadb_password,
        )
    except mariadb.Error as err:
        print(f"Error connecting to MariaDB Platform: {e}")
        return False

    query = "CREATE DATABASE winec;"
    cursor = conn.cursor()
    cursor.execute(query)
    print(cursor.statement)
    result = cursor.fetchall()
    cursor.close()
    return True


db_init_result = init_db()
print(f"{db_init_result=}")
