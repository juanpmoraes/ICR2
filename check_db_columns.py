import os
from sqlalchemy import create_engine, inspect
from dotenv import load_dotenv

load_dotenv()
db_uri = os.getenv('MYSQL_URI', 'sqlite:///site.db')

# Configuração para MySQL que exige SSL
connect_args = {}
if db_uri.startswith('mysql'):
    connect_args = {'ssl': {'fake_flag_to_enable_ssl': True}}

engine = create_engine(db_uri, connect_args=connect_args)

def check_columns():
    inspector = inspect(engine)
    columns = [c['name'] for c in inspector.get_columns('church')]
    print(f"Colunas na tabela 'church': {columns}")
    
    missing = []
    for col in ['mp_payment_id', 'pastor_id']:
        if col not in columns:
            missing.append(col)
            
    if missing:
        print(f"❌ Faltando colunas: {missing}")
    else:
        print("✅ Todas as colunas necessárias estão presentes!")

if __name__ == "__main__":
    check_columns()
