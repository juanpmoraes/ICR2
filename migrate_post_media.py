"""Migração: adiciona file_path, file_type, file_name ao post e torna content nullable."""
import pymysql, os
from dotenv import load_dotenv
load_dotenv()

uri = os.getenv('MYSQL_URI','').replace('mysql+pymysql://','')
user_pass, rest = uri.split('@')
user, password  = user_pass.split(':')
db_name = rest.split('/')[1]
hp = rest.split('/')[0].split(':')
host, port = hp[0], int(hp[1]) if len(hp)>1 else 3306

conn   = pymysql.connect(host=host,port=port,user=user,password=password,
                         database=db_name,ssl={'ssl_disabled':False})
cursor = conn.cursor()

changes = [
    ('file_path',  "ALTER TABLE `post` ADD COLUMN `file_path` VARCHAR(500)"),
    ('file_type',  "ALTER TABLE `post` ADD COLUMN `file_type` VARCHAR(20)"),
    ('file_name',  "ALTER TABLE `post` ADD COLUMN `file_name` VARCHAR(255)"),
]
for col, ddl in changes:
    cursor.execute("SELECT COUNT(*) FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=%s AND TABLE_NAME='post' AND COLUMN_NAME=%s",(db_name,col))
    if cursor.fetchone()[0]==0:
        cursor.execute(ddl); print(f"✅ post.{col} adicionado")
    else:
        print(f"⏭  post.{col} já existe")

# Torna content nullable
cursor.execute("ALTER TABLE `post` MODIFY COLUMN `content` TEXT")
# Aumenta media_url
cursor.execute("ALTER TABLE `post` MODIFY COLUMN `media_url` VARCHAR(500)")
print("✅ content agora é nullable, media_url expandido")

conn.commit(); cursor.close(); conn.close()
print("Migração concluída!")
