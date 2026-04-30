import sqlite3, os
from dotenv import load_dotenv

load_dotenv()
db_uri = os.getenv('MYSQL_URI', 'sqlite:///site.db')

if db_uri.startswith('sqlite:///'):
    db_path = db_uri.replace('sqlite:///', '')
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    try:
        cursor.execute("ALTER TABLE church ADD COLUMN whatsapp_group_link VARCHAR(255)")
        print("Coluna 'whatsapp_group_link' adicionada com sucesso ao SQLite.")
    except sqlite3.OperationalError:
        print("A coluna 'whatsapp_group_link' já existe ou a tabela não foi encontrada.")
    conn.commit()
    conn.close()
else:
    print("Para MySQL, execute manualmente: ALTER TABLE church ADD COLUMN whatsapp_group_link VARCHAR(255);")
