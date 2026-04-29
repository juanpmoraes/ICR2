# ✝️ Igreja Cristã Resplandecer — Sistema de Gestão

Sistema web completo de gestão para igrejas, desenvolvido com **Flask** e **Python**. Oferece feed de notícias do pastor, transmissões ao vivo via YouTube, oferta por PIX, controle financeiro, árvore genealógica de famílias e painel administrativo.

---

## 📋 Funcionalidades

### Para Membros
- 🔐 **Autenticação** — Cadastro e login seguro com senhas criptografadas (bcrypt)
- 📰 **Feed Social** — Acompanhe postagens do pastor com texto, imagens, vídeos, áudios e links
- ❤️ **Interação** — Curta e comente as postagens
- 📺 **Lives** — Assista transmissões ao vivo, vídeos agendados e recentes do canal da igreja no YouTube
- 💸 **Oferta/Dízimo** — Realize doações via PIX integrado com Mercado Pago

### Para Administradores / Pastor
- 📝 **Gerenciamento de Posts** — Crie, edite e exclua publicações com suporte a múltiplas mídias (upload local ou URL)
- 👥 **Gestão de Membros** — Visualize, edite funções e redefina senhas de usuários
- 💰 **Financeiro** — Controle completo de entradas (dízimos, ofertas) e saídas (gastos, dívidas)
- 📑 **Contas a Pagar** — Cadastre e gerencie contas com datas de vencimento e status (pendente/pago/atrasado)
- 📊 **Relatórios** — Gráficos mensais de receitas × despesas, pizza de categorias e resumo financeiro
- 🌳 **Árvore Genealógica** — Cadastre e visualize famílias e sua estrutura hierárquica completa

---

## 🛠️ Tecnologias

| Camada | Tecnologia |
|---|---|
| Backend | Python 3, Flask 3.0 |
| ORM | Flask-SQLAlchemy |
| Autenticação | Flask-Login + Flask-Bcrypt |
| Banco de dados | SQLite (dev) / MySQL (prod) |
| Pagamentos | Mercado Pago SDK (PIX) |
| Streaming | YouTube Data API v3 |
| HTTP Client | Requests |
| Config | python-dotenv |

---

## 🚀 Como Executar

### 1. Clone o repositório

```bash
git clone <url-do-repositorio>
cd ICR
```

### 2. Crie e ative o ambiente virtual

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# Linux / macOS
source venv/bin/activate
```

### 3. Instale as dependências

```bash
pip install -r requirements.txt
```

### 4. Configure as variáveis de ambiente

Crie um arquivo `.env` na raiz do projeto com base no exemplo abaixo:

```env
# Segurança
SECRET_KEY=sua-chave-secreta-aqui

# Banco de dados (deixe em branco para usar SQLite local)
MYSQL_URI=mysql+pymysql://usuario:senha@host:3306/nome_banco

# Mercado Pago (PIX)
MERCADOPAGO_ACCESS_TOKEN=seu-token-aqui

# YouTube Data API
YOUTUBE_API_KEY=sua-chave-api-youtube
YOUTUBE_CHANNEL_ID=UCxxxxxxxxxxxxxxxxxx

# Override manual para live (opcional — útil quando a API falha)
YOUTUBE_LIVE_OVERRIDE=

# Informações de contato da igreja (exibidas no feed)
PASTOR_WHATSAPP=5511999999999
CHURCH_INSTAGRAM=@igrejaresplandecer
```

### 5. Crie o banco de dados

```bash
python -c "from app import app, db; app.app_context().__enter__(); db.create_all()"
```

### 6. Crie o primeiro administrador

```bash
python create_admin.py
```

### 7. Inicie o servidor

```bash
python app.py
```

Acesse **http://localhost:5000** no navegador.

---

## 📁 Estrutura do Projeto

```
ICR/
├── app.py                    # Aplicação principal + todas as rotas
├── models.py                 # Modelos do banco de dados (SQLAlchemy)
├── requirements.txt          # Dependências Python
├── .env                      # Variáveis de ambiente (não versionar!)
├── .gitignore
│
├── static/
│   └── uploads/
│       └── posts/            # Arquivos de mídia enviados pelo pastor
│
├── templates/                # Templates HTML (Jinja2)
│   ├── login.html
│   ├── register.html
│   ├── feed.html
│   ├── lives.html
│   ├── offerings.html
│   ├── admin.html
│   ├── members.html
│   ├── finance.html
│   ├── bills.html
│   ├── reports.html
│   ├── families.html
│   └── ...
│
├── create_admin.py           # Script para criar usuário administrador
├── check_db.py               # Script utilitário para verificar o banco
├── debug_youtube.py          # Script para testar a integração com YouTube
│
└── migrate_*.py              # Scripts de migração do banco de dados
```

---

## 🗄️ Modelos de Dados

```
User           → Membro da plataforma (admin | pastor | membro)
Post           → Publicação do pastor (texto, imagem, vídeo, áudio, link, YouTube)
Comment        → Comentário em um post
Like           → Curtida em um post
Transaction    → Transação financeira (dízimo, oferta, entrada, gasto, dívida)
Bill           → Conta a pagar da igreja
Family         → Grupo familiar cadastrado
FamilyMember   → Nó da árvore genealógica (auto-referencial)
```

---

## 🔒 Controle de Acesso

| Papel | Acesso |
|---|---|
| `membro` | Feed, Lives, Perfil, Ofertas |
| `pastor` | Tudo de membro + criar/editar/excluir posts |
| `admin` | Tudo de pastor + painel administrativo, financeiro, famílias, membros |

> Administradores podem forçar a redefinição de senha de qualquer membro. Na próxima tentativa de login, o usuário será redirecionado para criar uma nova senha.

---

## 📺 Integração YouTube

O sistema consulta a **YouTube Data API v3** para detectar automaticamente:

- 🔴 Live em andamento (exibida no feed e na página de Lives)
- 📅 Vídeos agendados (próximas transmissões)
- 🎬 Vídeos recentes do canal

Um cache em memória de **60 segundos** evita excesso de chamadas à API. É possível definir `YOUTUBE_LIVE_OVERRIDE` no `.env` para forçar manualmente um vídeo de live, caso a API retorne erro de cota.

---

## 💳 Integração Mercado Pago (PIX)

Na tela de ofertas, o membro seleciona o tipo (dízimo ou oferta) e o valor. O sistema gera um **QR Code PIX** via API do Mercado Pago. A transação é registrada com status `pending` até a confirmação.

---

## 🗃️ Migrações

Scripts disponíveis para evoluir o banco de dados sem perder dados:

| Script | Descrição |
|---|---|
| `migrate_add_reset_flag.py` | Adiciona coluna `must_reset_password` na tabela `user` |
| `migrate_families.py` | Cria tabelas `family` e `family_member` |
| `migrate_post_media.py` | Adiciona colunas de mídia na tabela `post` |

Execute conforme necessário:

```bash
python migrate_families.py
```

---

## 📝 Licença

Projeto de uso interno da **Igreja Cristã Resplandecer**. Todos os direitos reservados.
"# ICR" 
