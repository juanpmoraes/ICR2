from app import app, db
from sqlalchemy import text

def add_column():
    with app.app_context():
        try:
            db.session.execute(text("ALTER TABLE plan ADD COLUMN duration_months INTEGER DEFAULT 1"))
            db.session.commit()
            print("Coluna duration_months adicionada com sucesso!")
        except Exception as e:
            print(f"Erro ao adicionar coluna (provavelmente já existe): {e}")

if __name__ == "__main__":
    add_column()
