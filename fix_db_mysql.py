import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()
db_uri = os.getenv('MYSQL_URI', 'sqlite:///site.db')

# Configuração para MySQL que exige SSL (Transporte Seguro)
connect_args = {}
if db_uri.startswith('mysql'):
    connect_args = {'ssl': {'fake_flag_to_enable_ssl': True}} # Ativa SSL básico do PyMySQL

engine = create_engine(db_uri, connect_args=connect_args)

def run_migration():
    print(f"--- Iniciando Correção de Banco de Dados (SSL Ativado) ---")
    print(f"Banco: {db_uri.split('@')[-1] if '@' in db_uri else db_uri}")
    
    migrations = [
        ("church", "whatsapp_group_link", "VARCHAR(255)"),
        ("user", "profile_pic_url", "VARCHAR(255)")
    ]
    
    try:
        with engine.connect() as conn:
            for table, column, col_type in migrations:
                try:
                    print(f"Tentando adicionar {column} na tabela {table}...")
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}"))
                    conn.commit()
                    print(f"✅ Sucesso: {column} adicionado.")
                except Exception as e:
                    if "Duplicate column name" in str(e) or "already exists" in str(e) or "1060" in str(e):
                        print(f"ℹ️  Aviso: {column} já existe ou erro ignorado.")
                    else:
                        print(f"❌ Erro em {column}: {e}")
    except Exception as e:
        print(f"❌ Falha crítica na conexão: {e}")
        print("\nDica: Se o banco exigir SSL, verifique se o driver 'pymysql' está instalado corretamente.")
        
    print(f"--- Migração Concluída ---")

if __name__ == "__main__":
    run_migration()
