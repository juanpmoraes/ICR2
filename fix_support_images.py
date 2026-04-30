from app import app, db
from sqlalchemy import text

def add_column():
    with app.app_context():
        try:
            # Tenta adicionar a coluna image_url caso ela não exista
            db.session.execute(text("ALTER TABLE support_message ADD COLUMN image_url VARCHAR(500) NULL"))
            db.session.commit()
            print("Coluna image_url adicionada com sucesso!")
        except Exception as e:
            # Se der erro de "Duplicate column", ignoramos
            if "Duplicate column" in str(e) or "1060" in str(e):
                print("A coluna image_url já existe.")
            else:
                print(f"Erro ao adicionar coluna: {e}")

if __name__ == "__main__":
    add_column()
