<img width=100% src="https://capsule-render.vercel.app/api?type=waving&color=gradient&customColorList=6&height=120&section=header"/>

<h1 align="center">🏗️ Estrutura e Setup do Projeto</h1>

<p align="center">
  <a href="#estrutura-de-diretórios">Estrutura</a>&nbsp;&nbsp;|&nbsp;&nbsp;
  <a href="#backend">Backend</a>&nbsp;&nbsp;|&nbsp;&nbsp;
  <a href="#frontend">Frontend</a>&nbsp;&nbsp;|&nbsp;&nbsp;
  <a href="#setup">Setup</a>&nbsp;&nbsp;|&nbsp;&nbsp;
  <a href="../README.md">Voltar ao README</a>
</p>

---

## Estrutura de diretórios

```
AuthService/
├── backend/
│   ├── __init__.py
│   ├── main.py                       → app FastAPI, router, mount do frontend em "/"
│   ├── api/
│   │   └── auth_routes.py            → /register, /token, /health, /me (+ sanitize_log)
│   ├── core/
│   │   ├── config.py                 → Settings (pydantic-settings, lê .env)
│   │   ├── logger.py                 → logging para stdout
│   │   └── security.py               → bcrypt (hash/verificação) e JWT (criar/decodificar)
│   ├── dependencies/
│   │   └── dependencies.py           → repositório singleton e get_current_user
│   ├── models/
│   │   └── user.py                   → entidade User (id, email, hashed_password)
│   ├── repositories/
│   │   └── user_repository.py        → armazenamento em memória (Dict[int, User])
│   ├── schemas/
│   │   └── user_schemas.py           → UserCreate, UserOut, Token
│   └── services/
│       └── auth_service.py           → cadastro e autenticação
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
│   │   │   ├── session.js            → token no sessionStorage, leitura do JWT, limpeza
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
├── read-model/
│   ├── MODEL.md                      → entidades, regras, fluxos e decisões
│   ├── STRUCTURE.md                  → este arquivo
│   ├── CONTRIBUTING.md               → guia de contribuição (PT-BR e EN-US)
│   ├── LICENSE                       → licença MIT
│   └── img/                          → capturas usadas no README
│
├── .github/workflows/codeql.yml      → análise CodeQL (push/PR em main e semanal)
├── .env.example                      → modelo de configuração
├── .gitignore                        → ignora .env, __pycache__, venv etc.
├── Dockerfile                        → imagem python:3.11-slim com healthcheck
├── docker-compose.yml                → serviço auth-service (container auth-service-v2)
├── requirements.txt                  → dependências Python
└── README.md                         → documentação principal
```

O arquivo `.env` (não versionado) é criado a partir do `.env.example`.

---

## Backend

As camadas dependem apenas da camada de baixo:

```
api/auth_routes.py ──► services/auth_service.py ──► repositories/user_repository.py ──► models/user.py
        │                         │
        ├── schemas/user_schemas.py (validação de entrada e saída)
        ├── dependencies/dependencies.py (repositório singleton, get_current_user)
        └── core/security.py ◄── core/config.py (.env)
```

`main.py` registra o router **antes** de montar `frontend/` em `/`, por isso as rotas da API (e `/docs`, `/redoc`, `/openapi.json`) têm prioridade sobre os arquivos estáticos. O diretório do frontend é procurado em `/code/frontend` (WORKDIR do Docker) e, se não existir, em `../frontend` relativo a `backend/`, o que cobre a execução local.

---

## Frontend

### Organização

- **Uma folha por responsabilidade.** `tokens → base → layout → components` são carregadas em todas as páginas, nessa ordem; cada página acrescenta só a sua (`auth.css`, `dashboard.css` ou `status.css`). As media queries ficam junto do componente que ajustam.
- **Módulos ES nativos.** Cada página carrega um único `<script type="module">` de `js/pages/`, que importa o que precisa de `js/core/`. Não há variáveis globais nem `onclick` no HTML.
- **Sem dependências de runtime.** As únicas origens externas são as folhas de fonte (Fontshare e Google Fonts).

### Dependências entre módulos

| Módulo | Importa | Usado por |
|---|---|---|
| `core/api.js` | — | `pages/auth.js`, `pages/dashboard.js`, `pages/status.js` |
| `core/session.js` | — | as três páginas |
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

- **CSP em `<meta>`** em cada página: `script-src 'self'` (nenhum script inline), `style-src 'self'` + Fontshare + Google Fonts, `font-src 'self'` + `cdn.fontshare.com` + `fonts.gstatic.com`, `connect-src 'self'`.
- **Sem `innerHTML`** com dados externos: `core/dom.js` cria elementos e insere texto.
- **Só o token é guardado** (`sessionStorage`); a senha nunca sai do formulário e da requisição.

---

## Setup

### Requisitos

- Com Docker: Docker 24+ e Docker Compose v2.
- Sem Docker: Python 3.11+ e pip.
- Um navegador atual (módulos ES, `color-mix()` e `:has()`).

### Com Docker

```bash
git clone https://github.com/https-shini/AuthService.git
cd AuthService
cp .env.example .env          # gere e coloque uma SECRET_KEY nova
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
cp .env.example .env          # gere e coloque uma SECRET_KEY nova
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

Para gerar a chave:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

### Endereços

```
Frontend:  http://localhost:8000
Swagger:   http://localhost:8000/docs
ReDoc:     http://localhost:8000/redoc
Health:    http://localhost:8000/health
```

> ⚠️ O armazenamento é em memória: todos os usuários são perdidos quando o processo ou o container reinicia.

<img width=100% src="https://capsule-render.vercel.app/api?type=waving&color=gradient&customColorList=6&height=120&section=footer"/>
