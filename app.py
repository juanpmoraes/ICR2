import os, uuid
from flask import Flask, render_template, redirect, url_for, flash, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from flask_bcrypt import Bcrypt
from models import db, User, Post, Comment, Like, Transaction, Family, FamilyMember, Bill
from dotenv import load_dotenv
from datetime import datetime, date
from werkzeug.utils import secure_filename
import mercadopago
import requests
from collections import defaultdict

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
    """Salva o arquivo e retorna (file_path_relativo, file_type, file_name_original)."""
    orig = secure_filename(file.filename)
    ext  = orig.rsplit('.', 1)[-1].lower() if '.' in orig else ''
    uid  = uuid.uuid4().hex
    stored = f"{uid}.{ext}" if ext else uid
    file.save(os.path.join(UPLOAD_FOLDER, stored))
    rel   = f'uploads/posts/{stored}'
    ftype = detect_file_type(orig)
    return rel, ftype, orig

mp = mercadopago.SDK(os.getenv("MERCADOPAGO_ACCESS_TOKEN"))

# ── Cache YouTube (evita bater na API a cada request) ────────────────────────
_yt_cache = {}
YT_CACHE_TTL = 60  # segundos

def _yt_api(params: dict):
    """Faz request na YouTube Data API com cache simples em memória."""
    import time
    cache_key = str(sorted(params.items()))
    cached = _yt_cache.get(cache_key)
    if cached and time.time() - cached['ts'] < YT_CACHE_TTL:
        return cached['data']
    api_key = os.getenv('YOUTUBE_API_KEY')
    ch      = os.getenv('YOUTUBE_CHANNEL_ID')
    if not api_key or not ch:
        print('[YouTube] Chaves não configuradas no .env')
        return {}
    p = dict(params)  # cópia para não mutar o original
    p.update({'key': api_key, 'channelId': ch})
    try:
        resp = requests.get('https://www.googleapis.com/youtube/v3/search',
                            params=p, timeout=8)
        data = resp.json()
        if 'error' in data:
            print(f'[YouTube] Erro da API: {data["error"].get("message")} (code {data["error"].get("code")})')
            return {}
        _yt_cache[cache_key] = {'ts': time.time(), 'data': data}
        return data
    except Exception as e:
        print(f'[YouTube] Exceção: {e}')
        return {}

def get_live_video_id():
    # Permite override manual via .env (útil quando a Search API falha)
    override = os.getenv('YOUTUBE_LIVE_OVERRIDE', '').strip()
    if override:
        return override
    r = _yt_api({'part': 'snippet,id', 'eventType': 'live', 'type': 'video', 'maxResults': 1})
    items = r.get('items', [])
    if items:
        return items[0]['id']['videoId']
    return None

def get_upcoming_videos(max_results=4):
    r = _yt_api({'part': 'snippet', 'eventType': 'upcoming', 'type': 'video', 'maxResults': max_results})
    return r.get('items', [])

def get_recent_videos(max_results=8):
    r = _yt_api({'part': 'snippet', 'order': 'date', 'type': 'video', 'maxResults': max_results})
    return r.get('items', [])

def admin_required():
    if current_user.role not in ['admin', 'pastor']:
        flash('Acesso negado.', 'danger')
        return False
    return True

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# ── Auth ──────────────────────────────────────────────────────────────────────
@app.route('/')
def home():
    return redirect(url_for('feed') if current_user.is_authenticated else url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('feed'))
    if request.method == 'POST':
        user = User.query.filter_by(email=request.form.get('email')).first()
        if user and bcrypt.check_password_hash(user.password, request.form.get('password')):
            login_user(user, remember=True)
            next_page = request.args.get('next')
            return redirect(next_page or url_for('feed'))
        flash('Login inválido. Verifique e-mail e senha.', 'danger')
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('feed'))
    if request.method == 'POST':
        hashed = bcrypt.generate_password_hash(request.form.get('password')).decode('utf-8')
        user = User(name=request.form.get('name'), email=request.form.get('email'),
                    password=hashed, role='membro')
        db.session.add(user)
        db.session.commit()
        flash('Conta criada! Faça o login.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('home'))

# ── Feed ──────────────────────────────────────────────────────────────────────
@app.route('/feed')
@login_required
def feed():
    posts = Post.query.order_by(Post.created_at.desc()).all()
    live_video_id = get_live_video_id()
    return render_template('feed.html', posts=posts, live_video_id=live_video_id,
                           pastor_whatsapp=os.getenv('PASTOR_WHATSAPP'),
                           instagram=os.getenv('CHURCH_INSTAGRAM'))

# ── Lives ─────────────────────────────────────────────────────────────────────
@app.route('/lives')
@login_required
def lives():
    live_id    = get_live_video_id()
    upcoming   = get_upcoming_videos(4)
    recent     = get_recent_videos(8)
    channel_id = os.getenv('YOUTUBE_CHANNEL_ID', '')
    return render_template('lives.html',
                           live_id=live_id,
                           upcoming=upcoming,
                           recent=recent,
                           channel_id=channel_id)

# ── API: status da live (polling pelo frontend) ───────────────────────────────
@app.route('/api/live-status')
@login_required
def live_status():
    live_id = get_live_video_id()
    return jsonify(live=bool(live_id), video_id=live_id)

@app.route('/post', methods=['POST'])
@login_required
def create_post():
    if current_user.role not in ['pastor', 'admin']:
        flash('Apenas o pastor pode criar postagens.', 'danger')
        return redirect(url_for('feed'))

    content   = request.form.get('content', '').strip() or None
    media_url = request.form.get('media_url', '').strip() or None
    file_path = file_type = file_name = None

    uploaded = request.files.get('media_file')
    if uploaded and uploaded.filename:
        file_path, file_type, file_name = save_upload(uploaded)
    elif media_url:
        # Detecta se é YouTube ou link externo
        if 'youtube.com' in media_url or 'youtu.be' in media_url:
            file_type = 'youtube'
        else:
            file_type = 'link'

    if not content and not file_path and not media_url:
        flash('A postagem precisa ter texto ou alguma mídia.', 'danger')
        return redirect(url_for('feed'))

    post = Post(content=content, media_url=media_url,
                file_path=file_path, file_type=file_type,
                file_name=file_name, author=current_user)
    db.session.add(post)
    db.session.commit()
    return redirect(url_for('feed'))

@app.route('/post/<int:post_id>/edit', methods=['POST'])
@login_required
def edit_post(post_id):
    post = Post.query.get_or_404(post_id)
    if post.user_id != current_user.id and current_user.role != 'admin':
        flash('Sem permissão.', 'danger')
        return redirect(url_for('feed'))

    post.content   = request.form.get('content', '').strip() or None
    new_url        = request.form.get('media_url', '').strip() or None
    uploaded       = request.files.get('media_file')

    if uploaded and uploaded.filename:
        # Apaga arquivo antigo se houver
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
    post = Post.query.get_or_404(post_id)
    if post.user_id != current_user.id and current_user.role != 'admin':
        flash('Sem permissão.', 'danger')
        return redirect(url_for('feed'))
    # remove likes e comentários primeiro
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
        db.session.add(Comment(content=content, post_id=post_id, author=current_user))
        db.session.commit()
    return redirect(url_for('feed') + f'#post-{post_id}')

@app.route('/comment/<int:cid>/delete', methods=['POST'])
@login_required
def delete_comment(cid):
    c = Comment.query.get_or_404(cid)
    post_id = c.post_id
    if c.user_id != current_user.id and current_user.role not in ['admin', 'pastor']:
        flash('Sem permissão.', 'danger')
        return redirect(url_for('feed'))
    db.session.delete(c)
    db.session.commit()
    return redirect(url_for('feed') + f'#post-{post_id}')

@app.route('/post/<int:post_id>/like', methods=['POST'])
@login_required
def like_post(post_id):
    like = Like.query.filter_by(user_id=current_user.id, post_id=post_id).first()
    if like:
        db.session.delete(like)
        liked = False
    else:
        db.session.add(Like(user_id=current_user.id, post_id=post_id))
        liked = True
    db.session.commit()
    total = Like.query.filter_by(post_id=post_id).count()
    # Se AJAX retorna JSON, senão redireciona
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        from flask import jsonify
        return jsonify(liked=liked, total=total)
    return redirect(url_for('feed') + f'#post-{post_id}')

# ── Offerings / PIX ──────────────────────────────────────────────────────────
@app.route('/offerings', methods=['GET', 'POST'])
@login_required
def offerings():
    qr_code = qr_code_base64 = None
    if request.method == 'POST':
        amount = float(request.form.get('amount'))
        tipo   = request.form.get('type')
        try:
            resp = mp.payment().create({
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
                    status='pending', user=current_user))
                db.session.commit()
        except Exception as e:
            flash(f'Erro ao gerar pagamento: {e}', 'danger')
    return render_template('offerings.html', qr_code=qr_code, qr_code_base64=qr_code_base64)

# ── Admin ─────────────────────────────────────────────────────────────────────
@app.route('/admin')
@login_required
def admin_dashboard():
    if not admin_required(): return redirect(url_for('feed'))
    total_members = User.query.count()
    total_bills   = Bill.query.filter_by(status='pendente').count()
    return render_template('admin.html', total_members=total_members, total_bills=total_bills)

@app.route('/members')
@login_required
def members():
    if not admin_required(): return redirect(url_for('feed'))
    return render_template('members.html', users=User.query.all())

# ── Gerenciamento de Usuários (admin) ─────────────────────────────────────────
@app.route('/admin/users/<int:uid>/edit', methods=['GET', 'POST'])
@login_required
def edit_user(uid):
    if not admin_required(): return redirect(url_for('feed'))
    u = User.query.get_or_404(uid)
    if request.method == 'POST':
        u.name  = request.form.get('name')
        u.email = request.form.get('email')
        u.role  = request.form.get('role')
        db.session.commit()
        flash(f'Usuário {u.name} atualizado!', 'success')
        return redirect(url_for('members'))
    return render_template('user_edit.html', u=u)

@app.route('/admin/users/<int:uid>/reset-password', methods=['POST'])
@login_required
def reset_user_password(uid):
    if not admin_required(): return redirect(url_for('feed'))
    u = User.query.get_or_404(uid)
    u.must_reset_password = True
    db.session.commit()
    flash(f'Senha de {u.name} marcada para redefinição. Na próxima vez que entrar, será solicitada uma nova senha.', 'success')
    return redirect(url_for('members'))

# ── Redefinição de senha obrigatória ──────────────────────────────────────────
@app.before_request
def check_password_reset():
    """Intercepta qualquer request de usuário logado com reset pendente."""
    allowed = {'set_new_password', 'logout', 'static'}
    if current_user.is_authenticated and getattr(current_user, 'must_reset_password', False):
        if request.endpoint not in allowed:
            return redirect(url_for('set_new_password'))

@app.route('/set-new-password', methods=['GET', 'POST'])
@login_required
def set_new_password():
    if not current_user.must_reset_password:
        return redirect(url_for('feed'))
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
            return redirect(url_for('feed'))
    return render_template('set_new_password.html')

# ── Finance – listagem + CRUD transações ──────────────────────────────────────
@app.route('/finance')
@login_required
def finance():
    if not admin_required(): return redirect(url_for('feed'))
    transactions = Transaction.query.order_by(Transaction.created_at.desc()).all()
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
@login_required
def add_transaction():
    if not admin_required(): return redirect(url_for('feed'))
    if request.method == 'POST':
        t = Transaction(
            type=request.form.get('type'),
            amount=float(request.form.get('amount')),
            description=request.form.get('description'),
            status=request.form.get('status', 'completed'),
        )
        db.session.add(t)
        db.session.commit()
        flash('Transacao adicionada!', 'success')
        return redirect(url_for('finance'))
    return render_template('transaction_form.html', action='Adicionar', t=None)

@app.route('/finance/<int:tid>/edit', methods=['GET', 'POST'])
@login_required
def edit_transaction(tid):
    if not admin_required(): return redirect(url_for('feed'))
    t = Transaction.query.get_or_404(tid)
    if request.method == 'POST':
        t.type        = request.form.get('type')
        t.amount      = float(request.form.get('amount'))
        t.description = request.form.get('description')
        t.status      = request.form.get('status', 'completed')
        db.session.commit()
        flash('Transacao atualizada!', 'success')
        return redirect(url_for('finance'))
    return render_template('transaction_form.html', action='Editar', t=t)

@app.route('/finance/<int:tid>/delete', methods=['POST'])
@login_required
def delete_transaction(tid):
    if not admin_required(): return redirect(url_for('feed'))
    db.session.delete(Transaction.query.get_or_404(tid))
    db.session.commit()
    flash('Transacao removida.', 'info')
    return redirect(url_for('finance'))

# ── Contas a Pagar ────────────────────────────────────────────────────────────
@app.route('/bills')
@login_required
def bills():
    if not admin_required(): return redirect(url_for('feed'))
    today = date.today()
    for b in Bill.query.filter_by(status='pendente').all():
        if b.due_date < today:
            b.status = 'atrasado'
    db.session.commit()
    all_bills = Bill.query.order_by(Bill.due_date.asc()).all()
    total_pendente = sum(b.amount for b in all_bills if b.status in ['pendente', 'atrasado'])
    return render_template('bills.html', bills=all_bills, total_pendente=total_pendente, today=today)

@app.route('/bills/add', methods=['GET', 'POST'])
@login_required
def add_bill():
    if not admin_required(): return redirect(url_for('feed'))
    if request.method == 'POST':
        due = datetime.strptime(request.form.get('due_date'), '%Y-%m-%d').date()
        b = Bill(
            description=request.form.get('description'),
            amount=float(request.form.get('amount')),
            due_date=due,
            category=request.form.get('category', 'Outros'),
            status='pendente'
        )
        db.session.add(b)
        db.session.commit()
        flash('Conta a pagar adicionada!', 'success')
        return redirect(url_for('bills'))
    return render_template('bill_form.html', action='Adicionar', b=None)

@app.route('/bills/<int:bid>/edit', methods=['GET', 'POST'])
@login_required
def edit_bill(bid):
    if not admin_required(): return redirect(url_for('feed'))
    b = Bill.query.get_or_404(bid)
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
@login_required
def delete_bill(bid):
    if not admin_required(): return redirect(url_for('feed'))
    db.session.delete(Bill.query.get_or_404(bid))
    db.session.commit()
    flash('Conta removida.', 'info')
    return redirect(url_for('bills'))

@app.route('/bills/<int:bid>/pay', methods=['POST'])
@login_required
def pay_bill(bid):
    if not admin_required(): return redirect(url_for('feed'))
    b = Bill.query.get_or_404(bid)
    b.status  = 'pago'
    b.paid_at = datetime.utcnow()
    db.session.commit()
    flash(f'Conta "{b.description}" marcada como paga!', 'success')
    return redirect(url_for('bills'))

# ── Relatorios ────────────────────────────────────────────────────────────────
@app.route('/reports')
@login_required
def reports():
    if not admin_required(): return redirect(url_for('feed'))
    transactions = Transaction.query.order_by(Transaction.created_at.asc()).all()
    bills        = Bill.query.all()

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
@login_required
def families():
    if not admin_required(): return redirect(url_for('feed'))
    all_families = Family.query.order_by(Family.name.asc()).all()
    return render_template('families.html', families=all_families)

@app.route('/families/add', methods=['GET', 'POST'])
@login_required
def add_family():
    if not admin_required(): return redirect(url_for('feed'))
    if request.method == 'POST':
        f = Family(name=request.form.get('name'),
                   description=request.form.get('description'))
        db.session.add(f)
        db.session.commit()
        flash(f'Família "{f.name}" criada!', 'success')
        return redirect(url_for('family_detail', fid=f.id))
    return render_template('family_form.html', action='Nova', f=None)

@app.route('/families/<int:fid>')
@login_required
def family_detail(fid):
    if not admin_required(): return redirect(url_for('feed'))
    f = Family.query.get_or_404(fid)
    roots = [m for m in f.tree if m.parent_id is None]
    all_users = User.query.order_by(User.name.asc()).all()
    return render_template('family_detail.html', f=f, roots=roots, all_users=all_users)

@app.route('/families/<int:fid>/edit', methods=['GET', 'POST'])
@login_required
def edit_family(fid):
    if not admin_required(): return redirect(url_for('feed'))
    f = Family.query.get_or_404(fid)
    if request.method == 'POST':
        f.name        = request.form.get('name')
        f.description = request.form.get('description')
        db.session.commit()
        flash('Família atualizada!', 'success')
        return redirect(url_for('family_detail', fid=f.id))
    return render_template('family_form.html', action='Editar', f=f)

@app.route('/families/<int:fid>/delete', methods=['POST'])
@login_required
def delete_family(fid):
    if not admin_required(): return redirect(url_for('feed'))
    f = Family.query.get_or_404(fid)
    # Remove membros da árvore antes
    FamilyMember.query.filter_by(family_id=fid).delete()
    db.session.delete(f)
    db.session.commit()
    flash('Família removida.', 'info')
    return redirect(url_for('families'))

@app.route('/families/<int:fid>/members/add', methods=['GET', 'POST'])
@login_required
def add_family_member(fid):
    if not admin_required(): return redirect(url_for('feed'))
    f = Family.query.get_or_404(fid)
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
    all_users = User.query.order_by(User.name.asc()).all()
    return render_template('family_member_form.html', action='Adicionar',
                           f=f, m=None, existing=existing, all_users=all_users)

@app.route('/families/<int:fid>/members/<int:mid>/edit', methods=['GET', 'POST'])
@login_required
def edit_family_member(fid, mid):
    if not admin_required(): return redirect(url_for('feed'))
    f = Family.query.get_or_404(fid)
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
    all_users = User.query.order_by(User.name.asc()).all()
    return render_template('family_member_form.html', action='Editar',
                           f=f, m=m, existing=existing, all_users=all_users)

@app.route('/families/<int:fid>/members/<int:mid>/delete', methods=['POST'])
@login_required
def delete_family_member(fid, mid):
    if not admin_required(): return redirect(url_for('feed'))
    m = FamilyMember.query.get_or_404(mid)
    # Desvincula filhos antes de apagar
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

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(host='0.0.0.0', port=80, debug=True)
