# ✝️ ChurchSaaS — Sistema de Gestão Multi-Igrejas

Sistema web completo **SaaS (Software as a Service)** para gestão de igrejas, desenvolvido com **Flask** e **Python**. Projetado para suportar **múltiplas igrejas (Multi-Tenant)** na mesma plataforma, oferecendo isolamento total de dados, personalização visual por congregação e controle hierárquico avançado.

---

## 📋 Funcionalidades Principais

### 👑 Para o Superadmin (Dono da Plataforma)
- **Gestão de Inquilinos (Churches)** — Cadastro e gerenciamento de múltiplas igrejas independentes.
- **Painel Global de Usuários** — Controle total sobre todos os usuários da plataforma, podendo transferir membros entre igrejas e delegar papéis de Pastor ou Superadmin.
- **Métricas Globais** — Acesso centralizado às informações gerais da plataforma.

### 👔 Para o Pastor (Gerente da Igreja)
- **Aprovação de Membros** — Novos membros que se cadastram precisam ser aprovados pelo Pastor para ter acesso aos módulos restritos.
- **Customização Completa de Design** — Personalize as cores (primária, fundo, cards, texto), a tipografia (fontes do Google Fonts) e o logotipo da sua igreja diretamente pelo painel.
- **Controle de Módulos** — O Pastor pode ativar ou desativar funcionalidades (Finanças, Relatórios, Famílias, Lives, etc.) de acordo com a necessidade da sua congregação.
- **Redes Sociais e API** — Configuração autônoma do WhatsApp, Instagram, MercadoPago Access Token e chaves do YouTube.
- **Gestão da Igreja** — Acesso ao painel financeiro (dízimos, entradas, gastos, contas a pagar), relatórios gráficos e controle da árvore genealógica de famílias.
- **Feed Social da Igreja** — Compartilhamento de mensagens, mídias (foto, vídeo, áudio, documentos) exclusivas para os membros da congregação.

### 👥 Para Membros
- **Carteirinha de Membro Virtual** — Perfil moderno estilo *Glassmorphism* com a logo da igreja, foto do perfil, cargo e código de barras.
- **Aplicativo PWA** — Possibilidade de instalar a plataforma como um Aplicativo no celular (Progressive Web App) gerado automaticamente com o nome e as cores da Igreja.
- **Doações (PIX)** — Ofertas e dízimos diretamente pelo aplicativo, com geração automática de QR Code via integração com o Mercado Pago.
- **Interação** — Curtidas e comentários restritos apenas ao círculo social da própria igreja.
- **Culto Online** — Visualização das Lives em andamento e agendamentos configurados pelo Pastor via YouTube API.

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
| PWA | Service Worker nativo + Manifest.json Dinâmico |
| Interface | HTML5, CSS3, FontAwesome, Google Fonts, Glassmorphism CSS |

---

## 🚀 Como Executar

### 1. Clone o repositório

```bash
git clone <url-do-repositorio>
cd ICR2
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

### 4. Configure as variáveis de ambiente base

Crie um arquivo `.env` na raiz do projeto (apenas as variáveis base globais):

```env
# Segurança
SECRET_KEY=sua-chave-secreta-aqui

# Banco de dados (deixe em branco para usar SQLite local)
MYSQL_URI=mysql+pymysql://usuario:senha@host:3306/nome_banco
```

*(Nota: Configurações de Mercado Pago, YouTube e WhatsApp agora são salvas **no banco de dados**, configuradas diretamente pelo Pastor no Painel de Configurações da Igreja, garantindo a arquitetura Multi-Tenant).*

### 5. Crie e migre o banco de dados

Para a arquitetura Multi-Tenant, certifique-se de executar o script de migração completo:

```bash
python migrate_multichurch.py
```
*(O script cuida da inicialização e atualização do banco caso existam instâncias antigas)*

### 6. Crie o primeiro Superadmin

O acesso global é feito pelo Superadmin. Para criá-lo:

```bash
python create_admin.py
```

### 7. Inicie o servidor

```bash
python app.py
```

Acesse **http://localhost:80** ou a porta configurada no seu ambiente.

---

## 🗄️ Modelos de Dados (SaaS)

```
Church         → Inquilino (Tenant). Guarda configs visuais, de API e toggles de módulos.
User           → Usuário (Superadmin global, Pastor de Igreja ou Membro de Igreja).
Post           → Publicações (Vinculadas a uma Igreja).
Comment        → Comentários (Isolados por Igreja).
Like           → Curtidas.
Transaction    → Transações financeiras (Isoladas por Igreja).
Bill           → Contas a pagar (Isoladas por Igreja).
Family         → Grupos familiares (Isolados por Igreja).
FamilyMember   → Membros da família.
```

---

## 🔒 Hierarquia de Acesso (RBAC)

| Papel | Acesso |
|---|---|
| **`Superadmin`** | Acesso global a todas as Igrejas e Usuários. Pode transferir usuários entre bancos de dados de igrejas. |
| **`Pastor`** | Acesso **apenas à sua própria Igreja**. Aprova novos membros, configura o PWA (cores/fontes), administra finanças, mídias sociais e cadastra outros pastores. |
| **`Membro`** | Acesso **apenas à sua própria Igreja**. Vê o feed, envia PIX, assiste lives e possui Carteirinha Virtual (após ser aprovado pelo Pastor). |

---

## 📝 Licença

Desenvolvido para uso comercial / SaaS como modelo de gestão **Multi-Igrejas**.
