import mariadb

mariadb_host = 'localhost'
mariadb_port = 3306
mariadb_user = 'cav'
mariadb_password = 'caveavin'

def init_db():

    try:
        conn = mariadb.connect(
            host=mariadb_host,
            port=mariadb_port,
            user=mariadb_user,
            passwd=mariadb_password,
        )
    except mariadb.Error as e:
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
