from app import app, db
from sqlalchemy import text

def create_tables():
    with app.app_context():
        try:
            db.create_all()
            print("Novas tabelas criadas com sucesso (SupportTicket)!")
        except Exception as e:
            print(f"Erro ao criar tabelas: {e}")

if __name__ == "__main__":
    create_tables()
