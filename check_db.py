import pymysql

try:
    conn = pymysql.connect(
        host='square-cloud-db-6db5d784d1764b7b930ac4525d587e21.squareweb.app',
        port=7209,
        user='squarecloud',
        password='Q7DGyRKuCZBPXs1bJKIIoraJ',
        ssl={'ssl_disabled': False}
    )
    cursor = conn.cursor()
    cursor.execute('SHOW DATABASES;')
    dbs = [r[0] for r in cursor.fetchall()]
    print("Bancos de dados disponíveis:", dbs)
    conn.close()
except Exception as e:
    print("Erro:", e)
