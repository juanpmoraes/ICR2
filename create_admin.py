"""
Script para criar o primeiro usuário admin/pastor no banco de dados.
Execute uma vez: python create_admin.py
"""
from app import app, bcrypt
from models import db, User

with app.app_context():
    email = input("Email do admin: ").strip()
    name = input("Nome completo: ").strip()
    password = input("Senha: ").strip()
    role = input("Cargo (admin / pastor / membro) [padrão: admin]: ").strip() or "admin"

    existing = User.query.filter_by(email=email).first()
    if existing:
        print(f"❌ Já existe um usuário com o email '{email}'.")
    else:
        hashed = bcrypt.generate_password_hash(password).decode("utf-8")
        user = User(name=name, email=email, password=hashed, role=role)
        db.session.add(user)
        db.session.commit()
        print(f"✅ Usuário '{name}' criado com sucesso como '{role}'!")
