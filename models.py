from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime

db = SQLAlchemy()


class Church(db.Model):
    """Igreja cadastrada na plataforma."""
    id               = db.Column(db.Integer, primary_key=True)
    name             = db.Column(db.String(150), nullable=False)
    slug             = db.Column(db.String(80),  unique=True, nullable=False)
    created_at       = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    # Informações Públicas (Landing Page)
    description      = db.Column(db.Text, nullable=True)
    address          = db.Column(db.String(255), nullable=True)

    # Personalização visual
    primary_color    = db.Column(db.String(7),  nullable=False, default='#d4af37')
    secondary_color  = db.Column(db.String(7),  nullable=False, default='#b5952f')
    bg_color         = db.Column(db.String(7),  nullable=False, default='#0f111a')
    card_bg_color    = db.Column(db.String(30), nullable=False, default='rgba(255, 255, 255, 0.05)')
    text_main_color  = db.Column(db.String(30), nullable=False, default='#f0f0f0')
    text_muted_color = db.Column(db.String(30), nullable=False, default='#a0a0b0')
    font_family      = db.Column(db.String(50), nullable=False, default='Inter')
    logo_url         = db.Column(db.String(255), nullable=True)

    # Integrações específicas da igreja
    mp_access_token  = db.Column(db.String(255), nullable=True)
    yt_api_key       = db.Column(db.String(255), nullable=True)
    yt_channel_id    = db.Column(db.String(100), nullable=True)
    yt_live_override = db.Column(db.String(50),  nullable=True)
    pastor_whatsapp  = db.Column(db.String(30),  nullable=True)
    church_instagram = db.Column(db.String(200), nullable=True)

    # Módulos Ativos
    has_reports   = db.Column(db.Boolean, nullable=False, default=True)
    has_lives     = db.Column(db.Boolean, nullable=False, default=True)
    has_families  = db.Column(db.Boolean, nullable=False, default=True)
    has_offerings = db.Column(db.Boolean, nullable=False, default=True)
    has_finance   = db.Column(db.Boolean, nullable=False, default=True)
    has_bills     = db.Column(db.Boolean, nullable=False, default=True)
    has_schedules = db.Column(db.Boolean, nullable=False, default=True)

    # Assinatura SaaS
    subscription_status     = db.Column(db.String(20), nullable=False, default='pending') # pending, active, expired
    subscription_expires_at = db.Column(db.DateTime, nullable=True)
    mp_subscription_id      = db.Column(db.String(100), nullable=True)
    plan_id                 = db.Column(db.Integer, db.ForeignKey('plan.id'), nullable=True)

    # Relacionamentos
    members      = db.relationship('User',        backref='church',  lazy=True,
                                   foreign_keys='User.church_id')
    posts        = db.relationship('Post',        backref='church',  lazy=True)
    transactions = db.relationship('Transaction', backref='church',  lazy=True)
    bills        = db.relationship('Bill',        backref='church',  lazy=True)
    families     = db.relationship('Family',      backref='church',  lazy=True)


class Family(db.Model):
    id          = db.Column(db.Integer, primary_key=True)
    name        = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)
    created_at  = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    church_id   = db.Column(db.Integer, db.ForeignKey('church.id'), nullable=True)

    users = db.relationship('User', backref='family', lazy=True)
    tree  = db.relationship('FamilyMember', backref='family',
                            lazy=True, foreign_keys='FamilyMember.family_id')


class FamilyMember(db.Model):
    """Nó da árvore genealógica de uma família."""
    id         = db.Column(db.Integer, primary_key=True)
    family_id  = db.Column(db.Integer, db.ForeignKey('family.id'), nullable=False)
    user_id    = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    name       = db.Column(db.String(100), nullable=False)
    role       = db.Column(db.String(30),  nullable=False, default='membro')
    gender     = db.Column(db.String(10),  nullable=False, default='outro')
    birth_date = db.Column(db.Date, nullable=True)
    notes      = db.Column(db.Text, nullable=True)
    parent_id  = db.Column(db.Integer, db.ForeignKey('family_member.id'), nullable=True)

    children = db.relationship('FamilyMember',
                               backref=db.backref('parent', remote_side='FamilyMember.id'),
                               lazy=True)
    user     = db.relationship('User', backref='family_node', lazy=True)


class User(db.Model, UserMixin):
    id                  = db.Column(db.Integer, primary_key=True)
    name                = db.Column(db.String(100), nullable=False)
    email               = db.Column(db.String(120), unique=True, nullable=False)
    password            = db.Column(db.String(256), nullable=False)
    role                = db.Column(db.String(20),  nullable=False, default='membro')  # pastor, membro

    # Multi-tenant
    church_id           = db.Column(db.Integer, db.ForeignKey('church.id'), nullable=True)
    is_approved         = db.Column(db.Boolean, nullable=False, default=False)
    is_superadmin       = db.Column(db.Boolean, nullable=False, default=False)

    family_id           = db.Column(db.Integer, db.ForeignKey('family.id'), nullable=True)
    created_at          = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    must_reset_password = db.Column(db.Boolean, nullable=False, default=False)
    profile_pic_url     = db.Column(db.String(255), nullable=True)

    posts        = db.relationship('Post',        backref='author', lazy=True)
    comments     = db.relationship('Comment',     backref='author', lazy=True)
    likes        = db.relationship('Like',        backref='user',   lazy=True)
    transactions = db.relationship('Transaction', backref='user',   lazy=True)


class Post(db.Model):
    id         = db.Column(db.Integer, primary_key=True)
    content    = db.Column(db.Text,        nullable=True)
    media_url  = db.Column(db.String(500), nullable=True)
    file_path  = db.Column(db.String(500), nullable=True)
    file_type  = db.Column(db.String(20),  nullable=True)
    file_name  = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime,    nullable=False, default=datetime.utcnow)
    user_id    = db.Column(db.Integer, db.ForeignKey('user.id'),   nullable=False)
    church_id  = db.Column(db.Integer, db.ForeignKey('church.id'), nullable=True)

    comments = db.relationship('Comment', backref='post', lazy=True)
    likes    = db.relationship('Like',    backref='post', lazy=True)


class Comment(db.Model):
    id         = db.Column(db.Integer, primary_key=True)
    content    = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    user_id    = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    post_id    = db.Column(db.Integer, db.ForeignKey('post.id'), nullable=False)


class Like(db.Model):
    id      = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey('post.id'), nullable=False)


class Transaction(db.Model):
    id          = db.Column(db.Integer, primary_key=True)
    type        = db.Column(db.String(20),  nullable=False)
    amount      = db.Column(db.Float,       nullable=False)
    description = db.Column(db.String(255), nullable=True)
    status      = db.Column(db.String(20),  nullable=False, default='completed')
    created_at  = db.Column(db.DateTime,    nullable=False, default=datetime.utcnow)
    user_id     = db.Column(db.Integer, db.ForeignKey('user.id'),   nullable=True)
    church_id   = db.Column(db.Integer, db.ForeignKey('church.id'), nullable=True)


class Bill(db.Model):
    """Contas a pagar da igreja."""
    id          = db.Column(db.Integer, primary_key=True)
    description = db.Column(db.String(255), nullable=False)
    amount      = db.Column(db.Float,       nullable=False)
    due_date    = db.Column(db.Date,        nullable=False)
    category    = db.Column(db.String(50),  nullable=False, default='Outros')
    status      = db.Column(db.String(20),  nullable=False, default='pendente')
    created_at  = db.Column(db.DateTime,    nullable=False, default=datetime.utcnow)
    paid_at     = db.Column(db.DateTime,    nullable=True)
    church_id   = db.Column(db.Integer, db.ForeignKey('church.id'), nullable=True)

class Schedule(db.Model):
    """Escalas de eventos e ministérios da igreja."""
    id          = db.Column(db.Integer, primary_key=True)
    church_id   = db.Column(db.Integer, db.ForeignKey('church.id'), nullable=False)
    title       = db.Column(db.String(150), nullable=False)
    event_date  = db.Column(db.DateTime, nullable=False)
    description = db.Column(db.Text, nullable=True)
    created_at  = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relação com os membros escalados
    members = db.relationship('ScheduleMember', backref='schedule', lazy=True, cascade="all, delete-orphan")

class ScheduleMember(db.Model):
    """Membro escalado em um evento (com papel específico)."""
    id          = db.Column(db.Integer, primary_key=True)
    schedule_id = db.Column(db.Integer, db.ForeignKey('schedule.id'), nullable=False)
    user_id     = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    role        = db.Column(db.String(100), nullable=False) # Ex: "Louvor - Baterista", "Recepção"
    
    user = db.relationship('User', backref='schedules_assigned')

class Plan(db.Model):
    """Planos de assinatura do SaaS e Promoções"""
    id                = db.Column(db.Integer, primary_key=True)
    name              = db.Column(db.String(100), nullable=False)
    price             = db.Column(db.Float, nullable=False)
    promotional_price = db.Column(db.Float, nullable=True)
    features          = db.Column(db.Text, nullable=True) # separado por quebra de linha
    duration_months   = db.Column(db.Integer, default=1)  # 1 para mensal, 0 para ilimitado
    is_active         = db.Column(db.Boolean, default=True)
    created_at        = db.Column(db.DateTime, default=datetime.utcnow)
    
    churches = db.relationship('Church', backref='plan', lazy=True)

class SupportTicket(db.Model):
    """Chamados de suporte abertos pelos pastores."""
    id         = db.Column(db.Integer, primary_key=True)
    subject    = db.Column(db.String(200), nullable=False)
    message    = db.Column(db.Text, nullable=False)
    status     = db.Column(db.String(20), nullable=False, default='aberto') # aberto, em_analise, resolvido, fechado
    response   = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    user_id    = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    church_id  = db.Column(db.Integer, db.ForeignKey('church.id'), nullable=False)
    assigned_to = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True) # ID do Superadmin responsável
    
    user   = db.relationship('User', backref='tickets', foreign_keys=[user_id])
    church = db.relationship('Church', backref='tickets')
    admin_assigned = db.relationship('User', backref='assigned_tickets', foreign_keys=[assigned_to])

class SupportMessage(db.Model):
    """Mensagens de troca dentro de um chamado."""
    id         = db.Column(db.Integer, primary_key=True)
    ticket_id  = db.Column(db.Integer, db.ForeignKey('support_ticket.id'), nullable=False)
    user_id    = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    message    = db.Column(db.Text, nullable=False)
    image_url  = db.Column(db.String(500), nullable=True) # Caminho da imagem anexada
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    ticket = db.relationship('SupportTicket', backref='messages')
    user   = db.relationship('User', backref='support_messages')
