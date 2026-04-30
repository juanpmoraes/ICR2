import os, uuid, time
from flask import Flask, render_template, redirect, url_for, flash, request, jsonify, make_response
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from flask_bcrypt import Bcrypt
from models import db, User, Post, Comment, Like, Transaction, Family, FamilyMember, Bill, Church, Schedule, ScheduleMember, Plan, SupportTicket
from dotenv import load_dotenv
from datetime import datetime, date
from werkzeug.utils import secure_filename
from collections import defaultdict
import mercadopago
import requests
from functools import wraps

load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'default-secret-key')
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('MYSQL_URI', 'sqlite:///site.db')

_is_mysql = os.getenv('MYSQL_URI', '').startswith('mysql')
if _is_mysql:
    app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
        "connect_args": {"ssl": {"ssl_disabled": False}}
    }

db.init_app(app)
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message_category = 'info'

# Upload config
UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'static', 'uploads', 'posts')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['MAX_CONTENT_LENGTH'] = 64 * 1024 * 1024  # 64 MB

EXT_IMAGE = {'png','jpg','jpeg','gif','webp','bmp','svg'}
EXT_VIDEO = {'mp4','webm','ogg','mov','avi','mkv'}
EXT_AUDIO = {'mp3','wav','ogg','m4a','aac','flac'}

def detect_file_type(filename):
    ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''
    if ext in EXT_IMAGE: return 'image'
    if ext in EXT_VIDEO: return 'video'
    if ext in EXT_AUDIO: return 'audio'
    return 'file'

def save_upload(file):
    orig = secure_filename(file.filename)
    ext  = orig.rsplit('.', 1)[-1].lower() if '.' in orig else ''
    uid  = uuid.uuid4().hex
    stored = f"{uid}.{ext}" if ext else uid
    file.save(os.path.join(UPLOAD_FOLDER, stored))
    rel   = f'uploads/posts/{stored}'
    ftype = detect_file_type(orig)
    return rel, ftype, orig

# ── Cache YouTube ────────────────────────────────────────────────────────────
_yt_cache = {}
YT_CACHE_TTL = 60  # segundos

def _yt_api(church, params: dict):
    if not church: return {}
    cache_key = str(church.id) + "_" + str(sorted(params.items()))
    cached = _yt_cache.get(cache_key)
    if cached and time.time() - cached['ts'] < YT_CACHE_TTL:
        return cached['data']
    api_key = church.yt_api_key
    ch      = church.yt_channel_id
    if not api_key or not ch:
        return {}
    p = dict(params)
    p.update({'key': api_key, 'channelId': ch})
    try:
        resp = requests.get('https://www.googleapis.com/youtube/v3/search', params=p, timeout=8)
        data = resp.json()
        if 'error' in data:
            print(f'[YouTube] Erro da API: {data["error"].get("message")}')
            return {}
        _yt_cache[cache_key] = {'ts': time.time(), 'data': data}
        return data
    except Exception as e:
        print(f'[YouTube] Exceção: {e}')
        return {}

def get_live_video_id(church):
    if not church: return None
    override = (church.yt_live_override or '').strip()
    if override:
        return override
    r = _yt_api(church, {'part': 'snippet,id', 'eventType': 'live', 'type': 'video', 'maxResults': 1})
    items = r.get('items', [])
    if items:
        return items[0]['id']['videoId']
    return None

def get_upcoming_videos(church, max_results=4):
    r = _yt_api(church, {'part': 'snippet', 'eventType': 'upcoming', 'type': 'video', 'maxResults': max_results})
    return r.get('items', [])

def get_recent_videos(church, max_results=8):
    r = _yt_api(church, {'part': 'snippet', 'order': 'date', 'type': 'video', 'maxResults': max_results})
    return r.get('items', [])

# ── Permissões e Contextos ───────────────────────────────────────────────────

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def superadmin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_superadmin:
            flash('Acesso negado (requer superadmin).', 'danger')
            return redirect(url_for('home'))
        return f(*args, **kwargs)
    return decorated_function

def pastor_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'pastor' or current_user.is_superadmin:
            flash('Acesso negado (requer pastor).', 'danger')
            return redirect(url_for('feed'))
        return f(*args, **kwargs)
    return decorated_function

@app.before_request
def check_approval_and_reset():
    """Intercepta login se não estiver aprovado, precisar de reset, ou se a assinatura expirar."""
    allowed_endpoints = {'login', 'register', 'logout', 'static', 'set_new_password', 'pending_approval', 'payment_blocked', 'checkout_payment', 'webhook_mp', 'home', 'saas_checkout'}
    if current_user.is_authenticated:
        if request.endpoint not in allowed_endpoints:
            # Superadmin não precisa de aprovação nem igreja
            if current_user.is_superadmin:
                return
            
            c = current_user.church
            if c:
                # Checagem de assinatura SaaS
                if c.subscription_status != 'active':
                    return redirect(url_for('checkout_payment'))
                if c.subscription_expires_at and datetime.utcnow() > c.subscription_expires_at:
                    c.subscription_status = 'expired'
                    db.session.commit()
                    return redirect(url_for('checkout_payment'))
            
            if not current_user.is_approved:
                return redirect(url_for('pending_approval'))
            if getattr(current_user, 'must_reset_password', False):
                return redirect(url_for('set_new_password'))

@app.context_processor
def inject_church():
    if current_user.is_authenticated and not current_user.is_superadmin and current_user.church_id:
        return {'church': current_user.church}
    return {'church': None}

# ── Auth ──────────────────────────────────────────────────────────────────────
@app.route('/')
def home():
    if current_user.is_authenticated:
        if current_user.is_superadmin:
            return redirect(url_for('superadmin_dashboard'))
        elif not current_user.is_approved:
            return redirect(url_for('pending_approval'))
        else:
            return redirect(url_for('feed'))
    plans = Plan.query.filter_by(is_active=True).all()
    return render_template('saas_landing.html', plans=plans)

@app.route('/checkout', methods=['GET', 'POST'])
def saas_checkout():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    plan_id = request.args.get('plan_id')
    plan = Plan.query.get(plan_id) if plan_id else None
    if request.method == 'POST':
        c_name = request.form.get('church_name')
        c_slug = request.form.get('church_slug')
        p_name = request.form.get('pastor_name')
        p_email = request.form.get('pastor_email')
        p_pass = request.form.get('pastor_password')
        
        if Church.query.filter_by(slug=c_slug).first() or User.query.filter_by(email=p_email).first():
            flash('Este slug de igreja ou e-mail já estão em uso. Tente outro.', 'danger')
            return redirect(url_for('saas_checkout'))
            
        # Cria a igreja vinculada ao plano
        new_church = Church(name=c_name, slug=c_slug, plan_id=request.form.get('plan_id') or plan_id)
        db.session.add(new_church)
        db.session.flush() # Para pegar o id
        
        # Cria o pastor
        hashed = bcrypt.generate_password_hash(p_pass).decode('utf-8')
        new_pastor = User(
            name=p_name, email=p_email, password=hashed,
            role='pastor', church_id=new_church.id, is_approved=True
        )
        db.session.add(new_pastor)
        db.session.commit()
        
        # Faz login automaticamente
        login_user(new_pastor)
        flash('Conta criada! Conclua o pagamento para ativar sua Plataforma.', 'info')
        return redirect(url_for('checkout_payment'))
        
    return render_template('saas_checkout.html', plan=plan, plan_id=plan_id)

@app.route('/checkout/payment')
@login_required
def checkout_payment():
    if current_user.church.subscription_status == 'active':
        return redirect(url_for('home'))
        
    # Checa se há plano, se não, vincula o plano padrão
    plan = current_user.church.plan
    if not plan:
        plan = Plan.query.first()
        current_user.church.plan = plan
        db.session.commit()
    
    final_price = plan.promotional_price if plan.promotional_price else plan.price

    # Integração com Mercado Pago (SaaS)
    # A chave do Superadmin deve estar no .env como SAAS_MP_ACCESS_TOKEN
    mp_token = os.getenv('SAAS_MP_ACCESS_TOKEN')
    
    init_point = None
    if not mp_token:
        flash("ERRO: O Token do Mercado Pago (SAAS_MP_ACCESS_TOKEN) não foi encontrado nas variáveis de ambiente. Verifique o arquivo .env.", "danger")
        print("ERRO MP: SAAS_MP_ACCESS_TOKEN é None ou vazio")
        
    if mp_token:
        try:
            sdk = mercadopago.SDK(mp_token)
            
            host_url = request.host_url.rstrip('/')
            
            # O Mercado Pago exige URLs válidas no back_urls e costuma recusar URLs locais.
            # Se estivermos rodando em http:// (desenvolvimento), usamos o domínio de produção.
            is_local = host_url.startswith('http://')
            safe_host = "https://mychurch.squareweb.app" if is_local else host_url
            
            preference_data = {
                "items": [
                    {
                        "title": f"Assinatura ChurchSaaS - {plan.name}",
                        "quantity": 1,
                        "currency_id": "BRL",
                        "unit_price": final_price
                    }
                ],
                "payer": {
                    "email": current_user.email
                },
                "external_reference": str(current_user.church.id), # ID da Igreja
                "back_urls": {
                    "success": safe_host + url_for('home'),
                    "failure": safe_host + url_for('checkout_payment'),
                    "pending": safe_host + url_for('checkout_payment')
                },
                "auto_return": "approved"
            }
            # Mercado Pago rejeita notification_url sem https
            if not is_local and host_url.startswith('https://'):
                preference_data["notification_url"] = host_url + url_for('webhook_mp')
                
            preference_response = sdk.preference().create(preference_data)
            
            if preference_response.get("status") in [200, 201]:
                init_point = preference_response["response"]["init_point"]
            else:
                flash(f"Erro Mercado Pago: {preference_response.get('response', {}).get('message', 'Erro desconhecido')}", "danger")
                print("Erro MP:", preference_response)
        except Exception as e:
            flash(f"Erro interno ao gerar pagamento: {str(e)}", "danger")
            print("Erro ao gerar Preference SaaS MP:", e)
            
    return render_template('checkout_payment.html', init_point=init_point, plan=plan, final_price=final_price)

@app.route('/payment-blocked')
@login_required
def payment_blocked():
    return render_template('payment_blocked.html')

@app.route('/webhook/mp', methods=['POST'])
def webhook_mp():
    # O Mercado Pago enviará notificações sobre os pagamentos aqui.
    try:
        mp_token = os.getenv('SAAS_MP_ACCESS_TOKEN')
        if not mp_token:
            return jsonify({"status": "ignored"}), 200
            
        topic = request.args.get('topic') or request.args.get('type')
        payment_id = request.args.get('id') or request.args.get('data.id')
        
        if (topic == 'payment' or topic == 'payment.created') and payment_id:
            sdk = mercadopago.SDK(mp_token)
            payment_info = sdk.payment().get(payment_id)
            
            if payment_info["status"] == 200:
                payment = payment_info["response"]
                if payment["status"] == "approved":
                    # Pega o ID da Igreja que enviamos no external_reference
                    church_id_str = payment.get("external_reference")
                    if church_id_str and church_id_str.isdigit():
                        church = Church.query.get(int(church_id_str))
                        if church:
                            church.subscription_status = 'active'
                            # Calcula expiração baseada no plano
                            import datetime as dt
                            if church.plan and church.plan.duration_months > 0:
                                church.subscription_expires_at = dt.datetime.utcnow() + dt.timedelta(days=30 * church.plan.duration_months)
                            else:
                                # Se plano for 0 ou nulo, é ilimitado (colocamos 100 anos)
                                church.subscription_expires_at = dt.datetime.utcnow() + dt.timedelta(days=36500)
                                
                            church.mp_payment_id = str(payment_id)
                            db.session.commit()
    except Exception as e:
        print("Webhook Error:", e)
    
    return jsonify({"status": "ok"}), 200

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    if request.method == 'POST':
        user = User.query.filter_by(email=request.form.get('email')).first()
        if user and bcrypt.check_password_hash(user.password, request.form.get('password')):
            login_user(user, remember=True)
            next_page = request.args.get('next')
            return redirect(next_page or url_for('home'))
        flash('Login inválido. Verifique e-mail e senha.', 'danger')
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    churches = Church.query.all()
    if request.method == 'POST':
        church_id = request.form.get('church_id')
        if not church_id:
            flash('Por favor selecione uma igreja.', 'danger')
            return redirect(url_for('register'))
        hashed = bcrypt.generate_password_hash(request.form.get('password')).decode('utf-8')
        user = User(name=request.form.get('name'), email=request.form.get('email'),
                    password=hashed, role='membro', church_id=int(church_id),
                    is_approved=False)
        db.session.add(user)
        db.session.commit()
        flash('Conta criada! Faça o login para acompanhar a aprovação.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html', churches=churches)

@app.route('/pending-approval')
@login_required
def pending_approval():
    if current_user.is_superadmin or current_user.is_approved:
        return redirect(url_for('home'))
    return render_template('pending_approval.html')

@app.route('/set-new-password', methods=['GET', 'POST'])
@login_required
def set_new_password():
    if not current_user.must_reset_password:
        return redirect(url_for('home'))
    if request.method == 'POST':
        pw  = request.form.get('password')
        pw2 = request.form.get('password2')
        if pw != pw2:
            flash('As senhas não coincidem.', 'danger')
        elif len(pw) < 6:
            flash('A senha deve ter pelo menos 6 caracteres.', 'danger')
        else:
            current_user.password = bcrypt.generate_password_hash(pw).decode('utf-8')
            current_user.must_reset_password = False
            db.session.commit()
            flash('Senha atualizada com sucesso!', 'success')
            return redirect(url_for('home'))
    return render_template('set_new_password.html')

@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('login'))

# ── Superadmin ────────────────────────────────────────────────────────────────
@app.route('/superadmin')
@superadmin_required
def superadmin_dashboard():
    churches = Church.query.all()
    return render_template('superadmin_dashboard.html', churches=churches)

@app.route('/superadmin/church/add', methods=['GET', 'POST'])
@superadmin_required
def add_church():
    if request.method == 'POST':
        c = Church(
            name=request.form.get('name'),
            slug=request.form.get('slug')
        )
        db.session.add(c)
        db.session.commit()
        
        # Opcional: criar usuário pastor junto com a igreja
        pastor_email = request.form.get('pastor_email')
        pastor_name = request.form.get('pastor_name')
        pastor_pass = request.form.get('pastor_password')
        
        if pastor_email:
            u = User.query.filter_by(email=pastor_email).first()
            if u:
                # Se já existe, atualiza para ser o pastor desta igreja
                if pastor_pass:
                    u.password = bcrypt.generate_password_hash(pastor_pass).decode('utf-8')
                if pastor_name:
                    u.name = pastor_name
                u.role = 'pastor'
                u.church_id = c.id
                u.is_approved = True
            else:
                # Se não existe, cria (exige senha inicial se for criar)
                if not pastor_pass:
                    flash('A senha é obrigatória para criar um novo pastor.', 'danger')
                    db.session.delete(c) # rollback
                    db.session.commit()
                    return redirect(url_for('add_church'))
                    
                hashed = bcrypt.generate_password_hash(pastor_pass).decode('utf-8')
                u = User(name=pastor_name or 'Pastor', email=pastor_email, password=hashed,
                         role='pastor', church_id=c.id, is_approved=True)
                db.session.add(u)
                
            db.session.commit()
            c.pastor_id = u.id
            db.session.commit()
            
        flash('Igreja cadastrada com sucesso!', 'success')
        return redirect(url_for('superadmin_dashboard'))
    return render_template('church_form.html', action='Adicionar', c=None)

@app.route('/superadmin/church/<int:cid>/edit', methods=['GET', 'POST'])
@superadmin_required
def edit_church(cid):
    c = Church.query.get_or_404(cid)
    if request.method == 'POST':
        c.name = request.form.get('name')
        c.slug = request.form.get('slug')
        db.session.commit()
        flash('Igreja atualizada.', 'success')
        return redirect(url_for('superadmin_dashboard'))
    return render_template('church_form.html', action='Editar', c=c)

@app.route('/superadmin/users')
@superadmin_required
def superadmin_users():
    churches = Church.query.all()
    unassigned = User.query.filter_by(church_id=None).all()
    return render_template('superadmin_users.html', churches=churches, unassigned=unassigned)

@app.route('/superadmin/users/add', methods=['GET', 'POST'])
@superadmin_required
def superadmin_add_user():
    churches = Church.query.all()
    if request.method == 'POST':
        email = request.form.get('email')
        if User.query.filter_by(email=email).first():
            flash('E-mail já está em uso.', 'danger')
            return redirect(url_for('superadmin_add_user'))
            
        hashed = bcrypt.generate_password_hash(request.form.get('password')).decode('utf-8')
        
        church_id = request.form.get('church_id')
        church_id = int(church_id) if church_id else None
        
        u = User(
            name=request.form.get('name'),
            email=email,
            password=hashed,
            role=request.form.get('role', 'membro'),
            church_id=church_id,
            is_approved='is_approved' in request.form,
            is_superadmin='is_superadmin' in request.form
        )
        db.session.add(u)
        db.session.commit()
        flash(f'Usuário {u.name} criado com sucesso!', 'success')
        return redirect(url_for('superadmin_users'))
    return render_template('superadmin_user_add.html', churches=churches)

@app.route('/superadmin/users/<int:uid>/edit', methods=['GET', 'POST'])
@superadmin_required
def superadmin_edit_user(uid):
    u = User.query.get_or_404(uid)
    churches = Church.query.all()
    if request.method == 'POST':
        u.name = request.form.get('name')
        u.email = request.form.get('email')
        
        # Alocar igreja
        church_id = request.form.get('church_id')
        u.church_id = int(church_id) if church_id else None
        
        # Permissões
        u.role = request.form.get('role', 'membro')
        u.is_approved = 'is_approved' in request.form
        u.is_superadmin = 'is_superadmin' in request.form
        
        db.session.commit()
        flash(f'Usuário {u.name} atualizado com sucesso.', 'success')
        return redirect(url_for('superadmin_dashboard'))
    return render_template('superadmin_church_edit.html', c=c)

@app.route('/superadmin/church/<int:cid>/grant_free_access', methods=['POST'])
@superadmin_required
def grant_free_access(cid):
    c = Church.query.get_or_404(cid)
    c.subscription_status = 'active'
    import datetime as dt
    # Libera por 100 anos (Ilimitado)
    c.subscription_expires_at = dt.datetime.utcnow() + dt.timedelta(days=36500)
    db.session.commit()
    flash(f'Acesso gratuito concedido à igreja {c.name}!', 'success')
    return redirect(url_for('superadmin_dashboard'))

# ── Superadmin: Planos e Promoções ──────────────────────────────────────────
@app.route('/superadmin/plans')
@superadmin_required
def superadmin_plans():
    plans = Plan.query.all()
    return render_template('superadmin_plans.html', plans=plans)

@app.route('/superadmin/plans/add', methods=['POST'])
@superadmin_required
def add_plan():
    p = Plan(
        name=request.form.get('name'),
        price=float(request.form.get('price')),
        promotional_price=float(request.form.get('promotional_price')) if request.form.get('promotional_price') else None,
        features=request.form.get('features'),
        duration_months=int(request.form.get('duration_months', 1))
    )
    db.session.add(p)
    db.session.commit()
    flash('Plano criado!', 'success')
    return redirect(url_for('superadmin_plans'))

@app.route('/superadmin/plans/<int:pid>/edit', methods=['POST'])
@superadmin_required
def edit_plan(pid):
    p = Plan.query.get_or_404(pid)
    p.name = request.form.get('name')
    p.price = float(request.form.get('price'))
    p.promotional_price = float(request.form.get('promotional_price')) if request.form.get('promotional_price') else None
    p.features = request.form.get('features')
    p.duration_months = int(request.form.get('duration_months', 1))
    p.is_active = 'is_active' in request.form
    db.session.commit()
    flash('Plano atualizado!', 'success')
    return redirect(url_for('superadmin_plans'))

@app.route('/superadmin/plans/<int:pid>/delete', methods=['POST'])
@superadmin_required
def delete_plan(pid):
    p = Plan.query.get_or_404(pid)
    db.session.delete(p)
    db.session.commit()
    flash('Plano removido.', 'info')
    return redirect(url_for('superadmin_plans'))

# ── Igreja (Configurações) ────────────────────────────────────────────────────
@app.route('/settings', methods=['GET', 'POST'])
@pastor_required
def church_settings():
    c = current_user.church
    if request.method == 'POST':
        c.primary_color = request.form.get('primary_color')
        c.secondary_color = request.form.get('secondary_color')
        c.bg_color = request.form.get('bg_color')
        c.card_bg_color = request.form.get('card_bg_color')
        c.text_main_color = request.form.get('text_main_color')
        c.text_muted_color = request.form.get('text_muted_color')
        c.font_family = request.form.get('font_family')
        
        c.description = request.form.get('description')
        c.address = request.form.get('address')
        
        logo = request.files.get('logo_file')
        if logo and logo.filename:
            path, _, _ = save_upload(logo)
            if path: c.logo_url = path

        c.mp_access_token = request.form.get('mp_access_token')
        c.yt_api_key = request.form.get('yt_api_key')
        c.yt_channel_id = request.form.get('yt_channel_id')
        c.yt_live_override = request.form.get('yt_live_override')
        c.pastor_whatsapp = request.form.get('pastor_whatsapp')
        c.church_instagram = request.form.get('church_instagram')
        
        c.has_reports = 'has_reports' in request.form
        c.has_lives = 'has_lives' in request.form
        c.has_families = 'has_families' in request.form
        c.has_offerings = 'has_offerings' in request.form
        c.has_finance = 'has_finance' in request.form
        c.has_bills = 'has_bills' in request.form
        c.has_schedules = 'has_schedules' in request.form
        
        db.session.commit()
        flash('Configurações da igreja atualizadas.', 'success')
        return redirect(url_for('church_settings'))
    return render_template('church_settings.html', c=c)

@app.route('/members')
@pastor_required
def members():
    users = User.query.filter_by(church_id=current_user.church_id, is_approved=True).all()
    pending = User.query.filter_by(church_id=current_user.church_id, is_approved=False).all()
    return render_template('members.html', users=users, pending_count=len(pending))

@app.route('/approve-members')
@pastor_required
def approve_members():
    pending = User.query.filter_by(church_id=current_user.church_id, is_approved=False).all()
    return render_template('approve_members.html', pending=pending)

@app.route('/approve-members/<int:uid>/<action>', methods=['POST'])
@pastor_required
def process_approval(uid, action):
    u = User.query.filter_by(id=uid, church_id=current_user.church_id).first_or_404()
    if action == 'approve':
        u.is_approved = True
        flash(f'Membro {u.name} aprovado.', 'success')
    elif action == 'reject':
        db.session.delete(u)
        flash(f'Membro {u.name} rejeitado e removido.', 'info')
    db.session.commit()
    return redirect(url_for('approve_members'))

@app.route('/members/<int:uid>/edit', methods=['GET', 'POST'])
@pastor_required
def edit_user(uid):
    u = User.query.filter_by(id=uid, church_id=current_user.church_id).first_or_404()
    if request.method == 'POST':
        u.name  = request.form.get('name')
        u.email = request.form.get('email')
        u.role  = request.form.get('role')
        db.session.commit()
        flash(f'Usuário {u.name} atualizado!', 'success')
        return redirect(url_for('members'))
    return render_template('user_edit.html', u=u)

@app.route('/members/<int:uid>/reset-password', methods=['POST'])
@pastor_required
def reset_user_password(uid):
    u = User.query.filter_by(id=uid, church_id=current_user.church_id).first_or_404()
    u.must_reset_password = True
    db.session.commit()
    flash(f'Senha de {u.name} marcada para redefinição.', 'success')
    return redirect(url_for('members'))

@app.route('/members/add', methods=['GET', 'POST'])
@pastor_required
def add_member():
    if request.method == 'POST':
        email = request.form.get('email')
        if User.query.filter_by(email=email).first():
            flash('E-mail já está em uso.', 'danger')
            return redirect(url_for('add_member'))

        hashed = bcrypt.generate_password_hash(request.form.get('password')).decode('utf-8')
        u = User(name=request.form.get('name'), email=email,
                 password=hashed, role=request.form.get('role', 'membro'), church_id=current_user.church_id,
                 is_approved=True)
        db.session.add(u)
        db.session.commit()
        flash('Usuário adicionado com sucesso.', 'success')
        return redirect(url_for('members'))
    return render_template('add_pastor.html')

# ── Feed ──────────────────────────────────────────────────────────────────────
@app.route('/feed')
@login_required
def feed():
    if current_user.is_superadmin: return redirect(url_for('superadmin_dashboard'))
    posts = Post.query.filter_by(church_id=current_user.church_id).order_by(Post.created_at.desc()).all()
    live_video_id = get_live_video_id(current_user.church)
    return render_template('feed.html', posts=posts, live_video_id=live_video_id,
                           pastor_whatsapp=current_user.church.pastor_whatsapp,
                           instagram=current_user.church.church_instagram)

@app.route('/post', methods=['POST'])
@login_required
def create_post():
    if current_user.role != 'pastor':
        flash('Apenas o pastor pode criar postagens.', 'danger')
        return redirect(url_for('feed'))

    content   = request.form.get('content', '').strip() or None
    media_url = request.form.get('media_url', '').strip() or None
    file_path = file_type = file_name = None

    uploaded = request.files.get('media_file')
    if uploaded and uploaded.filename:
        file_path, file_type, file_name = save_upload(uploaded)
    elif media_url:
        if 'youtube.com' in media_url or 'youtu.be' in media_url: file_type = 'youtube'
        else: file_type = 'link'

    if not content and not file_path and not media_url:
        flash('A postagem precisa ter texto ou alguma mídia.', 'danger')
        return redirect(url_for('feed'))

    post = Post(content=content, media_url=media_url,
                file_path=file_path, file_type=file_type,
                file_name=file_name, author=current_user,
                church_id=current_user.church_id)
    db.session.add(post)
    db.session.commit()
    return redirect(url_for('feed'))

@app.route('/post/<int:post_id>/edit', methods=['POST'])
@login_required
def edit_post(post_id):
    post = Post.query.filter_by(id=post_id, church_id=current_user.church_id).first_or_404()
    if post.user_id != current_user.id and current_user.role != 'pastor':
        flash('Sem permissão.', 'danger')
        return redirect(url_for('feed'))

    post.content   = request.form.get('content', '').strip() or None
    new_url        = request.form.get('media_url', '').strip() or None
    uploaded       = request.files.get('media_file')

    if uploaded and uploaded.filename:
        if post.file_path:
            old = os.path.join(os.path.dirname(__file__), 'static', post.file_path)
            if os.path.exists(old): os.remove(old)
        post.file_path, post.file_type, post.file_name = save_upload(uploaded)
        post.media_url = None
    elif new_url != post.media_url:
        post.media_url = new_url
        if new_url:
            post.file_type = 'youtube' if ('youtube.com' in new_url or 'youtu.be' in new_url) else 'link'
        elif not post.file_path:
            post.file_type = None

    db.session.commit()
    return redirect(url_for('feed'))

@app.route('/post/<int:post_id>/delete', methods=['POST'])
@login_required
def delete_post(post_id):
    post = Post.query.filter_by(id=post_id, church_id=current_user.church_id).first_or_404()
    if post.user_id != current_user.id and current_user.role != 'pastor':
        flash('Sem permissão.', 'danger')
        return redirect(url_for('feed'))
    Like.query.filter_by(post_id=post_id).delete()
    Comment.query.filter_by(post_id=post_id).delete()
    db.session.delete(post)
    db.session.commit()
    return redirect(url_for('feed'))

@app.route('/post/<int:post_id>/comment', methods=['POST'])
@login_required
def add_comment(post_id):
    content = request.form.get('content', '').strip()
    if content:
        # Verifica se o post é da mesma igreja
        Post.query.filter_by(id=post_id, church_id=current_user.church_id).first_or_404()
        db.session.add(Comment(content=content, post_id=post_id, author=current_user))
        db.session.commit()
    return redirect(url_for('feed') + f'#post-{post_id}')

@app.route('/comment/<int:cid>/delete', methods=['POST'])
@login_required
def delete_comment(cid):
    c = Comment.query.get_or_404(cid)
    post_id = c.post_id
    if c.user_id != current_user.id and current_user.role != 'pastor':
        flash('Sem permissão.', 'danger')
        return redirect(url_for('feed'))
    db.session.delete(c)
    db.session.commit()
    return redirect(url_for('feed') + f'#post-{post_id}')

@app.route('/post/<int:post_id>/like', methods=['POST'])
@login_required
def like_post(post_id):
    Post.query.filter_by(id=post_id, church_id=current_user.church_id).first_or_404()
    like = Like.query.filter_by(user_id=current_user.id, post_id=post_id).first()
    if like:
        db.session.delete(like)
        liked = False
    else:
        db.session.add(Like(user_id=current_user.id, post_id=post_id))
        liked = True
    db.session.commit()
    total = Like.query.filter_by(post_id=post_id).count()
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify(liked=liked, total=total)
    return redirect(url_for('feed') + f'#post-{post_id}')

# ── Lives ─────────────────────────────────────────────────────────────────────
@app.route('/lives')
@login_required
def lives():
    c = current_user.church
    live_id  = get_live_video_id(c)
    upcoming = get_upcoming_videos(c, 4)
    recent   = get_recent_videos(c, 8)
    return render_template('lives.html', live_id=live_id, upcoming=upcoming, recent=recent, channel_id=c.yt_channel_id)

@app.route('/api/live-status')
@login_required
def live_status():
    live_id = get_live_video_id(current_user.church)
    return jsonify(live=bool(live_id), video_id=live_id)

# ── Offerings / PIX ──────────────────────────────────────────────────────────
@app.route('/offerings', methods=['GET', 'POST'])
@login_required
def offerings():
    qr_code = qr_code_base64 = None
    c = current_user.church
    if request.method == 'POST' and c.mp_access_token:
        amount = float(request.form.get('amount'))
        tipo   = request.form.get('type')
        try:
            sdk = mercadopago.SDK(c.mp_access_token)
            resp = sdk.payment().create({
                "transaction_amount": amount,
                "description": f"{tipo.capitalize()} de {current_user.name}",
                "payment_method_id": "pix",
                "payer": {"email": current_user.email, "first_name": current_user.name}
            })
            pay = resp["response"]
            if 'point_of_interaction' in pay:
                td = pay["point_of_interaction"]["transaction_data"]
                qr_code        = td["qr_code"]
                qr_code_base64 = td["qr_code_base64"]
                db.session.add(Transaction(type=tipo, amount=amount,
                    description=f"{tipo.capitalize()} via PIX",
                    status='pending', user=current_user, church_id=c.id))
                db.session.commit()
        except Exception as e:
            flash(f'Erro ao gerar pagamento: {e}', 'danger')
    return render_template('offerings.html', qr_code=qr_code, qr_code_base64=qr_code_base64)

# ── Admin (Dashboard da Igreja) ───────────────────────────────────────────────
@app.route('/admin')
@pastor_required
def admin_dashboard():
    total_members = User.query.filter_by(church_id=current_user.church_id, is_approved=True).count()
    total_bills   = Bill.query.filter_by(church_id=current_user.church_id, status='pendente').count()
    return render_template('admin.html', total_members=total_members, total_bills=total_bills)

# ── Finance ───────────────────────────────────────────────────────────────────
@app.route('/finance')
@pastor_required
def finance():
    transactions = Transaction.query.filter_by(church_id=current_user.church_id).order_by(Transaction.created_at.desc()).all()
    total_dizimos = sum(t.amount for t in transactions if t.type == 'dizimo'  and t.status == 'completed')
    total_ofertas = sum(t.amount for t in transactions if t.type == 'oferta'  and t.status == 'completed')
    total_entradas = sum(t.amount for t in transactions if t.type == 'entrada' and t.status == 'completed')
    total_dividas = sum(t.amount for t in transactions if t.type == 'divida')
    total_gastos  = sum(t.amount for t in transactions if t.type == 'gasto')
    saldo = (total_dizimos + total_ofertas + total_entradas) - (total_dividas + total_gastos)
    return render_template('finance.html', transactions=transactions,
                           total_dizimos=total_dizimos, total_ofertas=total_ofertas,
                           total_entradas=total_entradas,
                           total_dividas=total_dividas, total_gastos=total_gastos,
                           saldo=saldo)

@app.route('/finance/add', methods=['GET', 'POST'])
@pastor_required
def add_transaction():
    if request.method == 'POST':
        t = Transaction(
            type=request.form.get('type'),
            amount=float(request.form.get('amount')),
            description=request.form.get('description'),
            status=request.form.get('status', 'completed'),
            church_id=current_user.church_id
        )
        db.session.add(t)
        db.session.commit()
        flash('Transação adicionada!', 'success')
        return redirect(url_for('finance'))
    return render_template('transaction_form.html', action='Adicionar', t=None)

@app.route('/finance/<int:tid>/edit', methods=['GET', 'POST'])
@pastor_required
def edit_transaction(tid):
    t = Transaction.query.filter_by(id=tid, church_id=current_user.church_id).first_or_404()
    if request.method == 'POST':
        t.type        = request.form.get('type')
        t.amount      = float(request.form.get('amount'))
        t.description = request.form.get('description')
        t.status      = request.form.get('status', 'completed')
        db.session.commit()
        flash('Transação atualizada!', 'success')
        return redirect(url_for('finance'))
    return render_template('transaction_form.html', action='Editar', t=t)

@app.route('/finance/<int:tid>/delete', methods=['POST'])
@pastor_required
def delete_transaction(tid):
    t = Transaction.query.filter_by(id=tid, church_id=current_user.church_id).first_or_404()
    db.session.delete(t)
    db.session.commit()
    flash('Transação removida.', 'info')
    return redirect(url_for('finance'))

# ── Contas a Pagar ────────────────────────────────────────────────────────────
@app.route('/bills')
@pastor_required
def bills():
    today = date.today()
    my_bills = Bill.query.filter_by(church_id=current_user.church_id).all()
    for b in my_bills:
        if b.status == 'pendente' and b.due_date < today:
            b.status = 'atrasado'
    db.session.commit()
    all_bills = Bill.query.filter_by(church_id=current_user.church_id).order_by(Bill.due_date.asc()).all()
    total_pendente = sum(b.amount for b in all_bills if b.status in ['pendente', 'atrasado'])
    return render_template('bills.html', bills=all_bills, total_pendente=total_pendente, today=today)

@app.route('/bills/add', methods=['GET', 'POST'])
@pastor_required
def add_bill():
    if request.method == 'POST':
        due = datetime.strptime(request.form.get('due_date'), '%Y-%m-%d').date()
        b = Bill(
            description=request.form.get('description'),
            amount=float(request.form.get('amount')),
            due_date=due,
            category=request.form.get('category', 'Outros'),
            status='pendente',
            church_id=current_user.church_id
        )
        db.session.add(b)
        db.session.commit()
        flash('Conta a pagar adicionada!', 'success')
        return redirect(url_for('bills'))
    return render_template('bill_form.html', action='Adicionar', b=None)

@app.route('/bills/<int:bid>/edit', methods=['GET', 'POST'])
@pastor_required
def edit_bill(bid):
    b = Bill.query.filter_by(id=bid, church_id=current_user.church_id).first_or_404()
    if request.method == 'POST':
        b.description = request.form.get('description')
        b.amount      = float(request.form.get('amount'))
        b.due_date    = datetime.strptime(request.form.get('due_date'), '%Y-%m-%d').date()
        b.category    = request.form.get('category', 'Outros')
        b.status      = request.form.get('status', 'pendente')
        if b.status == 'pago' and not b.paid_at:
            b.paid_at = datetime.utcnow()
        db.session.commit()
        flash('Conta atualizada!', 'success')
        return redirect(url_for('bills'))
    return render_template('bill_form.html', action='Editar', b=b)

@app.route('/bills/<int:bid>/delete', methods=['POST'])
@pastor_required
def delete_bill(bid):
    b = Bill.query.filter_by(id=bid, church_id=current_user.church_id).first_or_404()
    db.session.delete(b)
    db.session.commit()
    flash('Conta removida.', 'info')
    return redirect(url_for('bills'))

@app.route('/bills/<int:bid>/pay', methods=['POST'])
@pastor_required
def pay_bill(bid):
    b = Bill.query.filter_by(id=bid, church_id=current_user.church_id).first_or_404()
    b.status  = 'pago'
    b.paid_at = datetime.utcnow()
    db.session.commit()
    flash(f'Conta "{b.description}" marcada como paga!', 'success')
    return redirect(url_for('bills'))

# ── PWA & Landing Page ────────────────────────────────────────────────────────

@app.route('/igreja/<slug>')
def landing_page(slug):
    church = Church.query.filter_by(slug=slug).first_or_404()
    # Pega os 3 vídeos mais recentes para exibir na página caso tenha youtube
    recent_videos = []
    if church.yt_api_key and church.yt_channel_id:
        import requests
        try:
            url = f"https://www.googleapis.com/youtube/v3/search?key={church.yt_api_key}&channelId={church.yt_channel_id}&part=snippet,id&order=date&maxResults=3"
            r = requests.get(url, timeout=5)
            if r.status_code == 200:
                data = r.json()
                for item in data.get('items', []):
                    if item['id'].get('videoId'):
                        recent_videos.append({
                            'id': item['id']['videoId'],
                            'title': item['snippet']['title'],
                            'thumb': item['snippet']['thumbnails']['medium']['url']
                        })
        except:
            pass
            
    return render_template('landing.html', church=church, recent_videos=recent_videos)

@app.route('/manifest.json')
def manifest():
    c = current_user.church if current_user.is_authenticated and current_user.church else None
    name = c.name if c else 'App Igreja'
    bg = c.bg_color if c else '#0f111a'
    primary = c.primary_color if c else '#d4af37'
    
    # Se a igreja tem logo, podemos usá-lo como ícone futuramente
    return {
        "name": name,
        "short_name": name,
        "start_url": "/",
        "display": "standalone",
        "background_color": bg,
        "theme_color": primary,
        "icons": [
            {
                "src": "/static/img/icon-192.png",
                "sizes": "192x192",
                "type": "image/png"
            },
            {
                "src": "/static/img/icon-512.png",
                "sizes": "512x512",
                "type": "image/png"
            }
        ]
    }

@app.route('/sw.js')
def service_worker():
    sw = """
self.addEventListener('install', (e) => {
  e.waitUntil(
    caches.open('igreja-store').then((cache) => cache.addAll([
      '/',
      '/static/css/style.css',
      'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css'
    ])),
  );
});

self.addEventListener('fetch', (e) => {
  e.respondWith(
    fetch(e.request).catch(() => caches.match(e.request))
  );
});
"""
    response = make_response(sw)
    response.headers['Content-Type'] = 'application/javascript'
    return response



# ── Suporte (Pastores e Superadmin) ──────────────────────────────────────────
@app.route('/support', methods=['GET', 'POST'])
@login_required
def support():
    if current_user.is_superadmin:
        tickets = SupportTicket.query.order_by(SupportTicket.created_at.desc()).all()
        return render_template('superadmin_tickets.html', tickets=tickets)
    
    if current_user.role != 'pastor':
        flash('Apenas pastores podem acessar o suporte.', 'warning')
        return redirect(url_for('feed'))
        
    if request.method == 'POST':
        subject = request.form.get('subject')
        message = request.form.get('message')
        if subject and message:
            ticket = SupportTicket(
                subject=subject,
                message=message,
                user_id=current_user.id,
                church_id=current_user.church_id
            )
            db.session.add(ticket)
            db.session.commit()
            flash('Chamado aberto com sucesso! Nossa equipe responderá em breve.', 'success')
            return redirect(url_for('support'))
            
    my_tickets = SupportTicket.query.filter_by(church_id=current_user.church_id).order_by(SupportTicket.created_at.desc()).all()
    return render_template('support.html', tickets=my_tickets)

@app.route('/support/ticket/<int:tid>', methods=['GET', 'POST'])
@login_required
def view_ticket(tid):
    ticket = SupportTicket.query.get_or_404(tid)
    
    # Verifica permissão
    if not current_user.is_superadmin and ticket.church_id != current_user.church_id:
        flash('Sem permissão para ver este chamado.', 'danger')
        return redirect(url_for('support'))
        
    if request.method == 'POST' and current_user.is_superadmin:
        action = request.form.get('action')
        
        if action == 'assign':
            ticket.assigned_to = current_user.id
            ticket.status = 'em_analise'
            db.session.commit()
            flash('Você assumiu este chamado!', 'success')
            return redirect(url_for('view_ticket', tid=tid))
            
        # Para responder ou mudar status para resolvido/fechado, precisa ser o dono ou o chamado não ter dono
        if ticket.assigned_to and ticket.assigned_to != current_user.id:
            flash('Este chamado está sob os cuidados de outro administrador.', 'warning')
            return redirect(url_for('view_ticket', tid=tid))
            
        ticket.response = request.form.get('response')
        ticket.status = request.form.get('status', 'resolvido')
        
        # Ao responder, se não tiver dono, assume automaticamente
        if not ticket.assigned_to:
            ticket.assigned_to = current_user.id
            
        db.session.commit()
        flash('Resposta enviada e chamado atualizado!', 'success')
        return redirect(url_for('view_ticket', tid=tid))
        
    return render_template('view_ticket.html', ticket=ticket)

# ── Rotas Gerais ────────────────────────────────────────────────────────────────
@app.route('/reports')
@pastor_required
def reports():
    transactions = Transaction.query.filter_by(church_id=current_user.church_id).order_by(Transaction.created_at.asc()).all()
    bills = Bill.query.filter_by(church_id=current_user.church_id).all()

    total_dizimos    = sum(t.amount for t in transactions if t.type == 'dizimo'  and t.status == 'completed')
    total_ofertas    = sum(t.amount for t in transactions if t.type == 'oferta'  and t.status == 'completed')
    total_entradas   = sum(t.amount for t in transactions if t.type == 'entrada' and t.status == 'completed')
    total_gastos     = sum(t.amount for t in transactions if t.type == 'gasto')
    total_dividas    = sum(t.amount for t in transactions if t.type == 'divida')
    total_bills_pend = sum(b.amount for b in bills if b.status in ['pendente', 'atrasado'])
    saldo = (total_dizimos + total_ofertas + total_entradas) - (total_gastos + total_dividas)

    monthly = defaultdict(lambda: {'entradas': 0.0, 'saidas': 0.0})
    for t in transactions:
        key = t.created_at.strftime('%m/%Y')
        if t.type in ['dizimo', 'oferta', 'entrada'] and t.status == 'completed':
            monthly[key]['entradas'] += t.amount
        elif t.type in ['gasto', 'divida']:
            monthly[key]['saidas']   += t.amount
    months_sorted = sorted(monthly.keys(), key=lambda x: datetime.strptime(x, '%m/%Y'))[-12:]
    chart_labels  = months_sorted
    chart_entrada = [round(monthly[m]['entradas'], 2) for m in months_sorted]
    chart_saida   = [round(monthly[m]['saidas'],   2) for m in months_sorted]

    pie_data   = [total_dizimos, total_ofertas, total_entradas, total_gastos, total_dividas]
    pie_labels = ['Dizimos', 'Ofertas', 'Entradas', 'Gastos', 'Dividas']

    cat_totals = defaultdict(float)
    for b in bills:
        cat_totals[b.category] += b.amount
    cat_labels = list(cat_totals.keys())
    cat_values = [round(v, 2) for v in cat_totals.values()]

    return render_template('reports.html',
        total_dizimos=total_dizimos, total_ofertas=total_ofertas,
        total_entradas=total_entradas,
        total_gastos=total_gastos,  total_dividas=total_dividas,
        total_bills_pend=total_bills_pend, saldo=saldo,
        chart_labels=chart_labels, chart_entrada=chart_entrada, chart_saida=chart_saida,
        pie_data=pie_data, pie_labels=pie_labels,
        cat_labels=cat_labels, cat_values=cat_values,
        transactions=transactions, bills=bills)

# ── Famílias ─────────────────────────────────────────────────────────────────
@app.route('/families')
@pastor_required
def families():
    all_families = Family.query.filter_by(church_id=current_user.church_id).order_by(Family.name.asc()).all()
    return render_template('families.html', families=all_families)

@app.route('/families/add', methods=['GET', 'POST'])
@pastor_required
def add_family():
    if request.method == 'POST':
        f = Family(name=request.form.get('name'),
                   description=request.form.get('description'),
                   church_id=current_user.church_id)
        db.session.add(f)
        db.session.commit()
        flash(f'Família "{f.name}" criada!', 'success')
        return redirect(url_for('family_detail', fid=f.id))
    return render_template('family_form.html', action='Nova', f=None)

@app.route('/families/<int:fid>')
@pastor_required
def family_detail(fid):
    f = Family.query.filter_by(id=fid, church_id=current_user.church_id).first_or_404()
    roots = [m for m in f.tree if m.parent_id is None]
    all_users = User.query.filter_by(church_id=current_user.church_id).order_by(User.name.asc()).all()
    return render_template('family_detail.html', f=f, roots=roots, all_users=all_users)

@app.route('/families/<int:fid>/edit', methods=['GET', 'POST'])
@pastor_required
def edit_family(fid):
    f = Family.query.filter_by(id=fid, church_id=current_user.church_id).first_or_404()
    if request.method == 'POST':
        f.name        = request.form.get('name')
        f.description = request.form.get('description')
        db.session.commit()
        flash('Família atualizada!', 'success')
        return redirect(url_for('family_detail', fid=f.id))
    return render_template('family_form.html', action='Editar', f=f)

@app.route('/families/<int:fid>/delete', methods=['POST'])
@pastor_required
def delete_family(fid):
    f = Family.query.filter_by(id=fid, church_id=current_user.church_id).first_or_404()
    FamilyMember.query.filter_by(family_id=fid).delete()
    db.session.delete(f)
    db.session.commit()
    flash('Família removida.', 'info')
    return redirect(url_for('families'))

@app.route('/families/<int:fid>/members/add', methods=['GET', 'POST'])
@pastor_required
def add_family_member(fid):
    f = Family.query.filter_by(id=fid, church_id=current_user.church_id).first_or_404()
    if request.method == 'POST':
        bd_str = request.form.get('birth_date')
        bd = datetime.strptime(bd_str, '%Y-%m-%d').date() if bd_str else None
        uid_val = request.form.get('user_id') or None
        pid_val = request.form.get('parent_id') or None
        m = FamilyMember(
            family_id  = fid,
            user_id    = int(uid_val) if uid_val else None,
            name       = request.form.get('name'),
            role       = request.form.get('role', 'membro'),
            gender     = request.form.get('gender', 'outro'),
            birth_date = bd,
            notes      = request.form.get('notes'),
            parent_id  = int(pid_val) if pid_val else None,
        )
        db.session.add(m)
        db.session.commit()
        flash(f'{m.name} adicionado(a) à família!', 'success')
        return redirect(url_for('family_detail', fid=fid))
    existing = FamilyMember.query.filter_by(family_id=fid).all()
    all_users = User.query.filter_by(church_id=current_user.church_id).order_by(User.name.asc()).all()
    return render_template('family_member_form.html', action='Adicionar',
                           f=f, m=None, existing=existing, all_users=all_users)

@app.route('/families/<int:fid>/members/<int:mid>/edit', methods=['GET', 'POST'])
@pastor_required
def edit_family_member(fid, mid):
    f = Family.query.filter_by(id=fid, church_id=current_user.church_id).first_or_404()
    m = FamilyMember.query.get_or_404(mid)
    if request.method == 'POST':
        bd_str = request.form.get('birth_date')
        uid_val = request.form.get('user_id') or None
        pid_val = request.form.get('parent_id') or None
        m.name       = request.form.get('name')
        m.role       = request.form.get('role', 'membro')
        m.gender     = request.form.get('gender', 'outro')
        m.birth_date = datetime.strptime(bd_str, '%Y-%m-%d').date() if bd_str else None
        m.notes      = request.form.get('notes')
        m.user_id    = int(uid_val) if uid_val else None
        m.parent_id  = int(pid_val) if pid_val and int(pid_val) != mid else None
        db.session.commit()
        flash(f'{m.name} atualizado(a)!', 'success')
        return redirect(url_for('family_detail', fid=fid))
    existing = FamilyMember.query.filter_by(family_id=fid).filter(FamilyMember.id != mid).all()
    all_users = User.query.filter_by(church_id=current_user.church_id).order_by(User.name.asc()).all()
    return render_template('family_member_form.html', action='Editar',
                           f=f, m=m, existing=existing, all_users=all_users)

@app.route('/families/<int:fid>/members/<int:mid>/delete', methods=['POST'])
@pastor_required
def delete_family_member(fid, mid):
    Family.query.filter_by(id=fid, church_id=current_user.church_id).first_or_404()
    m = FamilyMember.query.get_or_404(mid)
    for child in m.children:
        child.parent_id = None
    db.session.delete(m)
    db.session.commit()
    flash('Membro removido da árvore.', 'info')
    return redirect(url_for('family_detail', fid=fid))

# ── Perfil ────────────────────────────────────────────────────────────────────
@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    if request.method == 'POST':
        current_user.name = request.form.get('name')
        db.session.commit()
        flash('Perfil atualizado!', 'success')
        return redirect(url_for('profile'))
    return render_template('profile.html')

# ── Escalas (Schedules) ───────────────────────────────────────────────────────
@app.route('/schedules')
@login_required
def schedules():
    if not current_user.church.has_schedules:
        flash('Módulo de Escalas desativado para esta igreja.', 'warning')
        return redirect(url_for('feed'))
    all_schedules = Schedule.query.filter_by(church_id=current_user.church_id).order_by(Schedule.event_date.asc()).all()
    return render_template('schedules.html', schedules=all_schedules)

@app.route('/schedules/add', methods=['POST'])
@pastor_required
def add_schedule():
    title = request.form.get('title')
    date_str = request.form.get('event_date')
    desc = request.form.get('description')
    if title and date_str:
        dt = datetime.strptime(date_str, '%Y-%m-%dT%H:%M')
        s = Schedule(church_id=current_user.church_id, title=title, event_date=dt, description=desc)
        db.session.add(s)
        db.session.commit()
        flash('Escala criada!', 'success')
    return redirect(url_for('schedules'))

@app.route('/schedules/<int:sid>/delete', methods=['POST'])
@pastor_required
def delete_schedule(sid):
    s = Schedule.query.filter_by(id=sid, church_id=current_user.church_id).first_or_404()
    db.session.delete(s)
    db.session.commit()
    flash('Escala excluída.', 'info')
    return redirect(url_for('schedules'))

@app.route('/schedules/<int:sid>/member/add', methods=['POST'])
@pastor_required
def add_schedule_member(sid):
    s = Schedule.query.filter_by(id=sid, church_id=current_user.church_id).first_or_404()
    uid = request.form.get('user_id')
    role = request.form.get('role')
    if uid and role:
        sm = ScheduleMember(schedule_id=s.id, user_id=uid, role=role)
        db.session.add(sm)
        db.session.commit()
        flash('Membro adicionado à escala!', 'success')
    return redirect(url_for('schedules'))

@app.route('/schedules/member/<int:smid>/delete', methods=['POST'])
@pastor_required
def delete_schedule_member(smid):
    sm = ScheduleMember.query.get_or_404(smid)
    # Verifica se pertence à igreja do pastor
    if sm.schedule.church_id == current_user.church_id:
        db.session.delete(sm)
        db.session.commit()
        flash('Membro removido da escala.', 'info')
    return redirect(url_for('schedules'))

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(host='0.0.0.0', port=80, debug=True)
