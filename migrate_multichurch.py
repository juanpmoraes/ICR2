"""
migrate_multichurch.py
Adiciona as colunas e tabelas necessárias para o sistema multi-igrejas.
Execute UMA vez após atualizar models.py.
"""
import os, sys
from sqlalchemy import text
from dotenv import load_dotenv

load_dotenv()

# Importa o app para usar o contexto correto
from app import app
from models import db, Church

def run_safe(conn, sql, label=''):
    try:
        conn.execute(text(sql))
        print(f'  ✅  {label or sql[:60]}')
    except Exception as e:
        msg = str(e).lower()
        if 'duplicate' in msg or 'already exists' in msg or 'multiple primary key' in msg:
            print(f'  ⏭️  Já existe: {label or sql[:60]}')
        else:
            print(f'  ⚠️  Erro em [{label}]: {e}')

with app.app_context():
    is_mysql = os.getenv('MYSQL_URI', '').startswith('mysql')

    # 1. Criar novas tabelas (church, etc.) — create_all ignora as existentes
    db.create_all()
    print('✅  Tabelas novas criadas (se necessário).')

    with db.engine.begin() as conn:
        if is_mysql:
            # ── User: novos campos ───────────────────────────────────────────────
            run_safe(conn,
                "ALTER TABLE user ADD COLUMN church_id INT NULL REFERENCES church(id)",
                'user.church_id')
            run_safe(conn,
                "ALTER TABLE user ADD COLUMN is_approved TINYINT(1) NOT NULL DEFAULT 0",
                'user.is_approved')
            run_safe(conn,
                "ALTER TABLE user ADD COLUMN is_superadmin TINYINT(1) NOT NULL DEFAULT 0",
                'user.is_superadmin')

            # ── Post: church_id ──────────────────────────────────────────────────
            run_safe(conn,
                "ALTER TABLE post ADD COLUMN church_id INT NULL REFERENCES church(id)",
                'post.church_id')

            # ── Transaction: church_id ───────────────────────────────────────────
            run_safe(conn,
                "ALTER TABLE transaction ADD COLUMN church_id INT NULL REFERENCES church(id)",
                'transaction.church_id')

            # ── Bill: church_id ──────────────────────────────────────────────────
            run_safe(conn,
                "ALTER TABLE bill ADD COLUMN church_id INT NULL REFERENCES church(id)",
                'bill.church_id')

            # ── Family: church_id ────────────────────────────────────────────────
            run_safe(conn,
                "ALTER TABLE family ADD COLUMN church_id INT NULL REFERENCES church(id)",
                'family.church_id')

            # ── Church: modules ──────────────────────────────────────────────────
            for col in ['has_reports', 'has_lives', 'has_families', 'has_offerings', 'has_finance', 'has_bills']:
                run_safe(conn, f"ALTER TABLE church ADD COLUMN {col} TINYINT(1) NOT NULL DEFAULT 1", f'church.{col}')

            # ── Church: appearance & public info ─────────────────────────────────
            for col, dflt in [('secondary_color', "'#b5952f'"),
                              ('card_bg_color', "'rgba(255, 255, 255, 0.05)'"),
                              ('text_main_color', "'#f0f0f0'"),
                              ('text_muted_color', "'#a0a0b0'"),
                              ('font_family', "'Inter'"),
                              ('logo_url', "NULL"),
                              ('description', "NULL"),
                              ('address', "NULL")]:
                run_safe(conn, f"ALTER TABLE church ADD COLUMN {col} VARCHAR(255) DEFAULT {dflt}", f'church.{col}')



        else:
            # SQLite — não suporta ALTER TABLE ADD COLUMN com FK, mas aceita sem FK
            run_safe(conn,
                "ALTER TABLE user ADD COLUMN church_id INTEGER",
                'user.church_id')
            run_safe(conn,
                "ALTER TABLE user ADD COLUMN is_approved INTEGER NOT NULL DEFAULT 0",
                'user.is_approved')
            run_safe(conn,
                "ALTER TABLE user ADD COLUMN is_superadmin INTEGER NOT NULL DEFAULT 0",
                'user.is_superadmin')
            run_safe(conn,
                "ALTER TABLE post ADD COLUMN church_id INTEGER",
                'post.church_id')
            run_safe(conn,
                "ALTER TABLE \"transaction\" ADD COLUMN church_id INTEGER",
                'transaction.church_id')
            run_safe(conn,
                "ALTER TABLE bill ADD COLUMN church_id INTEGER",
                'bill.church_id')
            run_safe(conn,
                "ALTER TABLE family ADD COLUMN church_id INTEGER",
                'family.church_id')
            for col in ['has_reports', 'has_lives', 'has_families', 'has_offerings', 'has_finance', 'has_bills']:
                run_safe(conn, f"ALTER TABLE church ADD COLUMN {col} INTEGER NOT NULL DEFAULT 1", f'church.{col}')
            for col, dflt in [('secondary_color', "'#b5952f'"),
                              ('card_bg_color', "'rgba(255, 255, 255, 0.05)'"),
                              ('text_main_color', "'#f0f0f0'"),
                              ('text_muted_color', "'#a0a0b0'"),
                              ('font_family', "'Inter'"),
                              ('logo_url', "NULL"),
                              ('description', "NULL"),
                              ('address', "NULL")]:
                run_safe(conn, f"ALTER TABLE church ADD COLUMN {col} TEXT DEFAULT {dflt}", f'church.{col}')

    print('\n✅  Migração concluída!')
    print('👉  Próximo passo: python create_admin.py para criar o superadmin.')
