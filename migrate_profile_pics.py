import os
import sys

# Adiciona o diretório atual ao path para importar app e db
sys.path.append(os.getcwd())

from app import app, db
from sqlalchemy import text

def migrate():
    with app.app_context():
        print("Iniciando migração para adicionar profile_pic_url...")
        try:
            # Tenta adicionar a coluna profile_pic_url na tabela user
            db.session.execute(text("ALTER TABLE user ADD COLUMN profile_pic_url VARCHAR(255)"))
            db.session.commit()
            print("Coluna profile_pic_url adicionada com sucesso!")
        except Exception as e:
            db.session.rollback()
            if "Duplicate column name" in str(e) or "already exists" in str(e):
                print("A coluna profile_pic_url já existe.")
            else:
                print(f"Erro ao adicionar coluna: {e}")

if __name__ == "__main__":
    migrate()
