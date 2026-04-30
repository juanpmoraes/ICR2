"""
Script para criar o Superadmin inicial da plataforma.
Este usuário não está vinculado a nenhuma igreja e tem acesso a todas.
"""
from app import app
from models import db, User
from flask_bcrypt import Bcrypt

bcrypt = Bcrypt()

def create_superadmin():
    email = input("E-mail do superadmin: ")
    password = input("Senha: ")
    name = input("Nome do superadmin [Super Admin]: ") or "Super Admin"

    with app.app_context():
        user = User.query.filter_by(email=email).first()
        if user:
            print("Usuário já existe. Atualizando para superadmin...")
            user.is_superadmin = True
            user.is_approved = True
            user.password = bcrypt.generate_password_hash(password).decode('utf-8')
            db.session.commit()
            print("Atualizado com sucesso!")
        else:
            hashed = bcrypt.generate_password_hash(password).decode('utf-8')
            admin = User(
                name=name,
                email=email,
                password=hashed,
                role='membro', # role não importa muito para superadmin
                is_approved=True,
                is_superadmin=True
            )
            db.session.add(admin)
            db.session.commit()
            print("Superadmin criado com sucesso!")

if __name__ == '__main__':
    create_superadmin()
