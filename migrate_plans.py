from app import app, db
from sqlalchemy import text

def add_column():
    with app.app_context():
        try:
            db.session.execute(text("ALTER TABLE plan ADD COLUMN duration_months INTEGER DEFAULT 1"))
            db.session.commit()
            print("Coluna duration_months adicionada com sucesso!")
        except Exception as e:
            # Se der erro de duplicidade, ignoramos
            if "duplicate column" in str(e).lower() or "exists" in str(e).lower():
                print("A coluna já existe no banco de dados.")
            else:
                print(f"Erro ao adicionar coluna: {e}")

if __name__ == "__main__":
    add_column()
