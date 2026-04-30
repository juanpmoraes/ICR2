from app import app, db
from sqlalchemy import text

def add_column():
    with app.app_context():
        try:
            db.session.execute(text("ALTER TABLE support_ticket ADD COLUMN assigned_to INTEGER REFERENCES user(id)"))
            db.session.commit()
            print("Coluna assigned_to adicionada com sucesso!")
        except Exception as e:
            print(f"Erro ao adicionar coluna: {e}")

if __name__ == "__main__":
    add_column()
