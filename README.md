# ChurchSaaS - Plataforma Multi-Igrejas ⛪🚀

Um ecossistema completo de gestão e engajamento em formato SaaS (Software as a Service), projetado para atender dezenas de igrejas simultaneamente em uma única infraestrutura. Cada congregação tem seu próprio espaço isolado, customizado com suas cores, aplicativo próprio e portal público.

## 🌟 Principais Funcionalidades

### 🔐 Arquitetura Multi-Tenant (SaaS)
*   **Isolamento Completo**: Dados, membros, escalas e finanças isolados por Igreja (Tenant).
*   **Onboarding Automático**: As igrejas se cadastram em `/checkout`, a conta do Pastor é criada na hora e a infraestrutura sobe automaticamente.
*   **Painel Superadmin**: Controle centralizado para ver todas as igrejas da rede e gerenciar assinaturas.
*   **Cobrança Automática**: Integração nativa com Mercado Pago gerando faturas recorrentes de assinatura (Pix, Cartão, Boleto).
*   **Bloqueio de Inadimplência**: Se a mensalidade expira, o acesso do Pastor e dos membros é suspenso imediatamente.

### 🎨 Motor de Personalização de Marca
O Pastor consegue montar a própria "cara" do app de sua igreja através da aba de *Configurações*:
*   Customização de Cores Hexadecimais e Fundo.
*   Logomarca Personalizada.
*   Tipografia do Google Fonts (Inter, Roboto, Poppins, etc).
*   Configuração independente de chaves API (Mercado Pago, YouTube) por igreja.

### 📱 Experiência Mobile First (PWA)
*   **Instalável via Navegador**: Tecnologia *Progressive Web App* permite que os membros instalem o app da Igreja no celular (Android/iOS) sem precisar da Play Store ou App Store.
*   O *Manifest.json* é dinâmico e assume o nome e as cores que o Pastor escolheu.
*   Layout 100% responsivo, desenhado primariamente para o celular e compatível com telas grandes.

### 💳 Ferramentas do Membro
*   **Carteirinha Digital (Glassmorphism)**: Documento de identidade do membro gerado dinamicamente com ID formatado e QR Code simbólico.
*   **Dízimos e Ofertas Seguros**: Integração com Mercado Pago dentro da aba de ofertas com processamento de pagamento na hora.
*   **Feed Social e Lives**: Portal onde o membro consome atualizações da igreja e assiste às Lives do YouTube sem sair do sistema.

### 🛡️ Administração Pastoral
*   **Controle de Módulos (Toggles)**: O pastor pode ligar/desligar partes do sistema (ex: desativar Módulo Financeiro, Relatórios ou Escalas) deixando a barra lateral super limpa.
*   **Escalas de Ministérios**: Agendamento de cultos e escalação de voluntários (Ex: Recepção, Bateria, Vozes) de forma inteligente.
*   **Finanças (Receitas e Contas a Pagar)**: Lançamentos de dízimos via Pix/Dinheiro e controle de passivos de água, luz, aluguel, etc., com relatórios visuais.
*   **Famílias e Genealogia**: Agrupamento de membros por família para facilitar acompanhamento de células/pequenos grupos.

---

## 🛠️ Stack Tecnológica

*   **Backend**: Python + Flask
*   **Banco de Dados**: SQLite (Desenvolvimento) / Suporte a MySQL via SQLAlchemy (Produção)
*   **Frontend**: HTML5, Vanilla CSS3 (Variáveis CSS Dinâmicas), Jinja2 Templating
*   **Integrações**: Mercado Pago SDK, YouTube Data API v3
*   **Segurança**: Flask-Login (Sessions), Bcrypt (Hashes), Proteção Multi-Tenant via Interceptadores (`@app.before_request`)

---

## 🚀 Como Executar Localmente

### 1. Clonar e Instalar Dependências
```bash
git clone https://github.com/seu-usuario/church-saas.git
cd church-saas
pip install -r requirements.txt
```

### 2. Configurar Variáveis de Ambiente
Crie um arquivo `.env` na raiz do projeto com o seguinte conteúdo:

```env
# Segurança do Flask
SECRET_KEY=uma-chave-longa-e-super-secreta

# Configuração do Banco de Dados
MYSQL_URI=sqlite:///site.db

# Credenciais do Superadmin (O Dono do SaaS)
SAAS_MP_ACCESS_TOKEN=APP_USR-seu-token-do-mercado-pago-aqui
```

### 3. Migração do Banco de Dados
Sempre que o código for atualizado (ou na primeira execução), rode o script de migração inteligente que estrutura o banco, aplica *constraints* do SaaS e popula as colunas essenciais:

```bash
python migrate_multichurch.py
```

### 4. Criar o Dono do Sistema (Superadmin)
Rode este comando apenas uma vez para criar a conta mestra:

```bash
python create_admin.py
```

### 5. Iniciar Servidor
```bash
python app.py
```
Acesse `http://localhost:80` no seu navegador. O site inicial público (página de vendas do SaaS) já estará disponível. Você pode clicar em **"Começar Agora"** para assinar uma nova igreja de teste!

---

## 📦 Webhooks e Pagamentos
Para testar a renovação automática da assinatura e liberação do acesso em ambiente local, você deve expor seu `localhost` para a internet usando o **Ngrok**:
```bash
ngrok http 80
```
Pegue o endereço HTTPS que o Ngrok gerar, vá até a plataforma de desenvolvedores do Mercado Pago (no seu painel principal de SaaS) e adicione a seguinte URL no Webhook:
`https://seu-endereco-ngrok.app/webhook/mp`

> Assim que o boleto ou PIX da nova igreja for pago, o sistema será notificado, mudará o `subscription_status` para `active` e os pastores conseguirão logar!

---
*Feito com excelência para servir ao Reino.*
