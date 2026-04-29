"""
Script de migração: adiciona a coluna must_reset_password na tabela user.
Execute uma vez: python migrate_add_reset_flag.py
"""
import pymysql
import os
from dotenv import load_dotenv

load_dotenv()

# Extrai parâmetros da URI
uri = os.getenv('MYSQL_URI', '')
# mysql+pymysql://user:pass@host:port/db
uri_clean = uri.replace('mysql+pymysql://', '')
user_pass, rest = uri_clean.split('@')
user, password = user_pass.split(':')
host_port_db = rest.split('/')
db_name = host_port_db[1]
host_port = host_port_db[0].split(':')
host = host_port[0]
port = int(host_port[1]) if len(host_port) > 1 else 3306

conn = pymysql.connect(
    host=host, port=port, user=user,
    password=password, database=db_name,
    ssl={'ssl_disabled': False}
)
cursor = conn.cursor()

# Verifica se a coluna já existe
cursor.execute("""
    SELECT COUNT(*) FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = %s AND TABLE_NAME = 'user'
    AND COLUMN_NAME = 'must_reset_password'
""", (db_name,))
exists = cursor.fetchone()[0]

if exists:
    print("✅ Coluna 'must_reset_password' já existe. Nada a fazer.")
else:
    cursor.execute("""
        ALTER TABLE `user`
        ADD COLUMN `must_reset_password` TINYINT(1) NOT NULL DEFAULT 0
    """)
    conn.commit()
    print("✅ Coluna 'must_reset_password' adicionada com sucesso!")

cursor.close()
conn.close()
