"""
Migração: cria tabela family_member e adiciona description + created_at em family.
Execute: python migrate_families.py
"""
import pymysql, os
from dotenv import load_dotenv

load_dotenv()
uri = os.getenv('MYSQL_URI', '').replace('mysql+pymysql://', '')
user_pass, rest = uri.split('@')
user, password   = user_pass.split(':')
db_name          = rest.split('/')[1]
host_port        = rest.split('/')[0].split(':')
host, port       = host_port[0], int(host_port[1]) if len(host_port) > 1 else 3306

conn   = pymysql.connect(host=host, port=port, user=user, password=password,
                         database=db_name, ssl={'ssl_disabled': False})
cursor = conn.cursor()

# ── family: adiciona description e created_at ──────────────────────────────
for col, ddl in [
    ('description', "ALTER TABLE `family` ADD COLUMN `description` TEXT"),
    ('created_at',  "ALTER TABLE `family` ADD COLUMN `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP"),
]:
    cursor.execute("""SELECT COUNT(*) FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA=%s AND TABLE_NAME='family' AND COLUMN_NAME=%s""", (db_name, col))
    if cursor.fetchone()[0] == 0:
        cursor.execute(ddl); print(f"✅ family.{col} adicionado")
    else:
        print(f"⏭  family.{col} já existe")

# ── family_member: cria se não existir ────────────────────────────────────
cursor.execute("""SELECT COUNT(*) FROM information_schema.TABLES
    WHERE TABLE_SCHEMA=%s AND TABLE_NAME='family_member'""", (db_name,))
if cursor.fetchone()[0] == 0:
    cursor.execute("""
        CREATE TABLE `family_member` (
            `id`         INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
            `family_id`  INT NOT NULL,
            `user_id`    INT DEFAULT NULL,
            `name`       VARCHAR(100) NOT NULL,
            `role`       VARCHAR(30)  NOT NULL DEFAULT 'membro',
            `gender`     VARCHAR(10)  NOT NULL DEFAULT 'outro',
            `birth_date` DATE DEFAULT NULL,
            `notes`      TEXT,
            `parent_id`  INT DEFAULT NULL,
            FOREIGN KEY (`family_id`) REFERENCES `family`(`id`),
            FOREIGN KEY (`user_id`)   REFERENCES `user`(`id`),
            FOREIGN KEY (`parent_id`) REFERENCES `family_member`(`id`)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """)
    print("✅ Tabela family_member criada!")
else:
    print("⏭  Tabela family_member já existe")

conn.commit()
cursor.close()
conn.close()
print("\nMigração concluída!")
