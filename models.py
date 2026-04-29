from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime

db = SQLAlchemy()

class Family(db.Model):
    id          = db.Column(db.Integer, primary_key=True)
    name        = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)
    created_at  = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    # Membros cadastrados que pertencem a esta família
    users   = db.relationship('User', backref='family', lazy=True)
    # Nós da árvore genealógica
    tree    = db.relationship('FamilyMember', backref='family',
                              lazy=True, foreign_keys='FamilyMember.family_id')

class FamilyMember(db.Model):
    """Nó da árvore genealógica de uma família."""
    id         = db.Column(db.Integer, primary_key=True)
    family_id  = db.Column(db.Integer, db.ForeignKey('family.id'), nullable=False)
    user_id    = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)   # vínculo com conta
    name       = db.Column(db.String(100), nullable=False)                         # nome livre
    role       = db.Column(db.String(30), nullable=False, default='membro')        # chefe, cônjuge, filho, filha, pai, mãe, neto, neta, outro
    gender     = db.Column(db.String(10), nullable=False, default='outro')         # masculino, feminino, outro
    birth_date = db.Column(db.Date, nullable=True)
    notes      = db.Column(db.Text, nullable=True)
    parent_id  = db.Column(db.Integer, db.ForeignKey('family_member.id'), nullable=True)

    # Auto-referência
    children = db.relationship('FamilyMember', backref=db.backref('parent', remote_side='FamilyMember.id'), lazy=True)
    # Conta vinculada
    user     = db.relationship('User', backref='family_node', lazy=True)

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='membro')  # admin, pastor, membro
    family_id = db.Column(db.Integer, db.ForeignKey('family.id'), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    must_reset_password = db.Column(db.Boolean, nullable=False, default=False)

    posts = db.relationship('Post', backref='author', lazy=True)
    comments = db.relationship('Comment', backref='author', lazy=True)
    likes = db.relationship('Like', backref='user', lazy=True)
    transactions = db.relationship('Transaction', backref='user', lazy=True)

class Post(db.Model):
    id         = db.Column(db.Integer, primary_key=True)
    content    = db.Column(db.Text, nullable=True)         # texto é opcional
    media_url  = db.Column(db.String(500), nullable=True)  # URL externa (YouTube, link)
    file_path  = db.Column(db.String(500), nullable=True)  # caminho do arquivo enviado
    file_type  = db.Column(db.String(20),  nullable=True)  # image, video, audio, file, link
    file_name  = db.Column(db.String(255), nullable=True)  # nome original do arquivo
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    user_id    = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    comments = db.relationship('Comment', backref='post', lazy=True)
    likes    = db.relationship('Like',    backref='post', lazy=True)

class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey('post.id'), nullable=False)

class Like(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey('post.id'), nullable=False)

class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    type = db.Column(db.String(20), nullable=False)  # dizimo, oferta, divida, gasto
    amount = db.Column(db.Float, nullable=False)
    description = db.Column(db.String(255), nullable=True)
    status = db.Column(db.String(20), nullable=False, default='completed')  # pending, completed
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)

class Bill(db.Model):
    """Contas a pagar da igreja."""
    id = db.Column(db.Integer, primary_key=True)
    description = db.Column(db.String(255), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    due_date = db.Column(db.Date, nullable=False)
    category = db.Column(db.String(50), nullable=False, default='Outros')  # Aluguel, Energia, Salário, Evento, Outros
    status = db.Column(db.String(20), nullable=False, default='pendente')  # pendente, pago, atrasado
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    paid_at = db.Column(db.DateTime, nullable=True)
