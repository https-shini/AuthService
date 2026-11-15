<img width=100% src="https://capsule-render.vercel.app/api?type=waving&color=gradient&customColorList=6&height=120&section=header"/>

<h1 align="center">🏗️ Estrutura e Setup do Projeto</h1>

<p align="center">
  <a href="#estrutura-de-diretórios">Estrutura</a>&nbsp;&nbsp;|&nbsp;&nbsp;
  <a href="#backend">Backend</a>&nbsp;&nbsp;|&nbsp;&nbsp;
  <a href="#frontend">Frontend</a>&nbsp;&nbsp;|&nbsp;&nbsp;
  <a href="#testes">Testes</a>&nbsp;&nbsp;|&nbsp;&nbsp;
  <a href="#setup">Setup</a>&nbsp;&nbsp;|&nbsp;&nbsp;
  <a href="../README.md">Voltar ao README</a>
</p>

---

## Estrutura de diretórios

```
AuthService/
├── backend/
│   ├── __init__.py
│   ├── main.py                       → app FastAPI, middleware de headers, router, mount do frontend em "/"
│   ├── api/
│   │   └── auth_routes.py            → /register, /token, /refresh, /logout, /health, /me (+ sanitize_log)
│   ├── core/
│   │   ├── config.py                 → Settings (pydantic-settings, .env) e validação da SECRET_KEY
│   │   ├── cookies.py                → nomes e atributos dos cookies de refresh e CSRF
│   │   ├── email.py                  → política de normalização de e-mail
│   │   ├── logger.py                 → logging para stdout
│   │   ├── network.py                → IP do cliente e HTTPS atrás de proxies confiáveis
│   │   ├── rate_limit.py             → LoginRateLimiter (IP, IP + conta, conta)
│   │   ├── security.py               → bcrypt e JWT de acesso (assinar/ler)
│   │   └── security_headers.py       → CSP, X-Frame-Options, nosniff, HSTS etc.
│   ├── dependencies/
│   │   └── dependencies.py           → singletons (repositório, tokens, limiter) e get_current_user
│   ├── models/
│   │   └── user.py                   → entidade User (id, email, hashed_password, name)
│   ├── repositories/
│   │   └── user_repository.py        → usuários em memória com índice por e-mail normalizado
│   ├── schemas/
│   │   └── user_schemas.py           → UserCreate, UserOut, Token
│   └── services/
│       ├── auth_service.py           → cadastro e autenticação
│       └── token_service.py          → sessões, refresh rotativo, CSRF e revogação
│
├── frontend/
│   ├── index.html                    → acesso: entrar / criar conta
│   ├── home.html                     → painel da conta autenticada
│   ├── status.html                   → status da API (verificações reais)
│   ├── css/
│   │   ├── tokens.css                → design system: cores, tipografia, espaço, raio, movimento
│   │   ├── base.css                  → reset, tipografia base, foco, utilidades de acessibilidade
│   │   ├── layout.css                → fundo (aurora + malha), header, navegação, rodapé
│   │   ├── components.css            → botão, card, badge, campo, alerta, status, abas, checklist…
│   │   ├── auth.css                  → página de acesso
│   │   ├── dashboard.css             → painel
│   │   └── status.css                → status
│   ├── js/
│   │   ├── theme-init.js             → aplica o tema no <head>, antes da pintura
│   │   ├── core/
│   │   │   ├── api.js                → cliente HTTP e contratos da API
│   │   │   ├── auth.js               → chamadas autenticadas, renovação serializada, logout
│   │   │   ├── session.js            → access token no sessionStorage, leitura do JWT, cookie CSRF
│   │   │   ├── dom.js                → criação segura de elementos, alertas, formatação
│   │   │   ├── theme.js              → alternância e persistência do tema
│   │   │   └── nav.js                → menu móvel acessível
│   │   └── pages/
│   │       ├── auth.js               → index.html
│   │       ├── dashboard.js          → home.html
│   │       └── status.js             → status.html
│   └── public/
│       ├── favicon.svg               → ícone da aba
│       └── icons.svg                 → sprite de ícones (traço no estilo do portfólio)
│
├── tests/
│   ├── conftest.py                   → chave aleatória, cliente HTTPS de teste, estado zerado por teste
│   ├── helpers.py                    → register, login, bearer, relógio controlável
│   ├── test_config.py                → SECRET_KEY e validação da configuração
│   ├── test_register.py              → 201, nome, regras de senha, duplicados
│   ├── test_email.py                 → maiúsculas/minúsculas e usuários antigos
│   ├── test_rate_limit.py            → limites, bloqueio, X-Forwarded-For, logs
│   ├── test_tokens.py                → expirado, adulterado, revogado, refresh, CSRF, logout, cookies
│   └── test_headers.py               → headers de segurança e CSP sincronizada com o HTML
│
├── read-model/
│   ├── MODEL.md                      → entidades, regras, fluxos e decisões
│   ├── STRUCTURE.md                  → este arquivo
│   ├── CONTRIBUTING.md               → guia de contribuição (PT-BR e EN-US)
│   ├── LICENSE                       → licença MIT
│   └── img/                          → capturas usadas no README
│
├── .github/workflows/codeql.yml      → análise CodeQL (push/PR em main e semanal)
├── .env.example                      → modelo de configuração (sem chave: gere a sua)
├── .gitignore                        → ignora .env, __pycache__, venv etc.
├── Dockerfile                        → imagem python:3.11-slim com healthcheck
├── docker-compose.yml                → serviço auth-service (container auth-service-v2)
├── requirements.txt                  → dependências de execução
├── requirements-dev.txt              → dependências de teste (pytest, httpx)
├── pytest.ini                        → configuração do pytest
└── README.md                         → documentação principal
```

O arquivo `.env` (não versionado) é criado a partir do `.env.example`. A imagem Docker copia só `backend/` e `frontend/`; os testes não entram nela.

---

## Backend

Dependências entre as camadas:

```
main.py ── middleware ──► core/security_headers.py
   │
api/auth_routes.py ──► services/auth_service.py ──► repositories/user_repository.py ──► models/user.py
   │                ├─► services/token_service.py ──► core/security.py (JWT)
   │                ├─► core/rate_limit.py
   │                └─► core/cookies.py
   ├── schemas/user_schemas.py (validação de entrada e saída) ──► core/email.py
   └── dependencies/dependencies.py (singletons, get_current_user) ──► core/network.py
core/config.py (.env) é lido por todos os módulos que precisam de configuração.
```

`main.py` registra o router **antes** de montar `frontend/` em `/`, por isso as rotas da API (e `/docs`, `/redoc`, `/openapi.json`) têm prioridade sobre os arquivos estáticos. O middleware de headers vale para todas as respostas, inclusive as estáticas. O diretório do frontend é procurado em `/code/frontend` (WORKDIR do Docker) e, se não existir, em `../frontend` relativo a `backend/`, o que cobre a execução local.

A configuração é validada na importação de `core/config.py`: com valores inválidos a aplicação não sobe e a mensagem lista o que corrigir, sem imprimir segredos.

---

## Frontend

### Organização

- **Uma folha por responsabilidade.** `tokens → base → layout → components` são carregadas em todas as páginas, nessa ordem; cada página acrescenta só a sua (`auth.css`, `dashboard.css` ou `status.css`). As media queries ficam junto do componente que ajustam.
- **Módulos ES nativos.** Cada página carrega um único `<script type="module">` de `js/pages/`, que importa o que precisa de `js/core/`. Não há variáveis globais nem `onclick` no HTML.
- **Sem dependências de runtime.** As únicas origens externas são as folhas de fonte (Fontshare e Google Fonts).

### Dependências entre módulos

| Módulo | Importa | Usado por |
|---|---|---|
| `core/api.js` | — | `core/auth.js` e as três páginas |
| `core/session.js` | — | `core/auth.js` e as três páginas |
| `core/auth.js` | `api.js`, `session.js` | `pages/dashboard.js`, `pages/status.js` |
| `core/dom.js` | — | as três páginas |
| `core/theme.js` | — | as três páginas |
| `core/nav.js` | — | as três páginas |
| `theme-init.js` | — (script clássico, não módulo) | `<head>` das três páginas |

### Design system

Os tokens de `css/tokens.css` foram portados do design system do portfólio [gcruz.dev.br](https://gcruz.dev.br):

| Grupo | Valores |
|---|---|
| Marca / acento | crimson `#e11d48` · índigo `#6366f1` (claro: `#4f46e5`) |
| Fundo (escuro / claro) | `#070d19` / `#f2f4f8`, com superfícies na escala slate |
| Tipografia | Cabinet Grotesk (títulos), General Sans (texto), JetBrains Mono (rótulos, valores, logo) |
| Raios | 8 px (botões, campos), 16 px (cards), 4 px (badges) |
| Movimento | 150 / 250 / 400 ms, `cubic-bezier(0, 0, 0.2, 1)`; anulado com `prefers-reduced-motion` |
| Breakpoints | 480, 640 (menu vira barra), 768, 900, 1024 px |

### Segurança

- **CSP em `<meta>`** em cada página, idêntica à que o servidor envia no header (que acrescenta `frame-ancestors 'none'`). Ao mudar uma, mude a outra em `backend/core/security_headers.py`: `tests/test_headers.py` falha se divergirem.
- **Sem `innerHTML`** com dados externos: `core/dom.js` cria elementos e insere texto.
- **Só o access token é guardado** (`sessionStorage`); o refresh token fica em cookie `HttpOnly`, e a senha nunca sai do formulário e da requisição.

---

## Testes

```bash
pip install -r requirements-dev.txt
pytest
```

- Cada sessão de testes gera uma `SECRET_KEY` aleatória; não é preciso `.env`.
- O cliente de teste usa `https://testserver`, para que os cookies `Secure`/`__Host-` funcionem como no navegador.
- O estado em memória (usuários, sessões, rate limit) é zerado antes de cada teste.
- Janelas de tempo (bloqueio, expiração de sessão, reuso de refresh) são testadas com um relógio controlável, sem `sleep`.

---

## Setup

### Requisitos

- Com Docker: Docker 24+ e Docker Compose v2.
- Sem Docker: Python 3.11+ e pip.
- Um navegador atual (módulos ES, `color-mix()` e `:has()`; Web Locks é usado quando disponível).

### Chave de assinatura

A `SECRET_KEY` é obrigatória e precisa ter pelo menos 32 caracteres aleatórios. Gere uma e coloque-a no `.env` ou na variável de ambiente do serviço:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

### Com Docker

```bash
git clone https://github.com/https-shini/AuthService.git
cd AuthService
cp .env.example .env          # preencha SECRET_KEY
docker compose up --build -d
```

| Ação | Comando |
|---|---|
| Logs | `docker logs auth-service-v2 -f` |
| Estado (healthy/unhealthy) | `docker ps` |
| Reconstruir sem cache | `docker compose build --no-cache` |
| Parar | `docker compose down` |

### Sem Docker

```bash
git clone https://github.com/https-shini/AuthService.git
cd AuthService
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env          # preencha SECRET_KEY
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

### Produção (Render ou similar)

- `SECRET_KEY`: chave nova, gerada como acima.
- `TRUSTED_PROXY_HOPS=1`: o serviço fica atrás de um proxy; sem isso, todos os clientes aparecem com o mesmo IP para o rate limiting.
- `HSTS_ENABLED=true`: o serviço é publicado em HTTPS.
- Uma única instância: sessões e contadores ficam em memória.

### Endereços

```
Frontend:  http://localhost:8000
Swagger:   http://localhost:8000/docs
ReDoc:     http://localhost:8000/redoc
Health:    http://localhost:8000/health
```

> ⚠️ O estado é em memória: usuários e sessões são perdidos quando o processo ou o container reinicia.

<img width=100% src="https://capsule-render.vercel.app/api?type=waving&color=gradient&customColorList=6&height=120&section=footer"/>
