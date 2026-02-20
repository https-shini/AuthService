<img width=100% src="https://capsule-render.vercel.app/api?type=waving&color=gradient&customColorList=6&height=120&section=header"/>

<h1 align="center">🏗️ Estrutura e Setup do Projeto</h1>

<p align="center">
  <a href="#requisitos">Requisitos</a>&nbsp;&nbsp;&nbsp;|&nbsp;&nbsp;&nbsp;
  <a href="#setup-do-ambiente">Setup do Ambiente</a>&nbsp;&nbsp;&nbsp;|&nbsp;&nbsp;&nbsp;
  <a href="#como-rodar">Como Rodar</a>&nbsp;&nbsp;&nbsp;|&nbsp;&nbsp;&nbsp;
  <a href="#decisões-arquiteturais">Decisões Arquiteturais</a>&nbsp;&nbsp;&nbsp;|&nbsp;&nbsp;&nbsp;
  <a href="./README.md">Voltar</a>
</p>

---

## Requisitos

Para rodar o projeto com Docker *(recomendado)*:

- [Docker](https://www.docker.com/) — versão 24+
- [Docker Compose](https://docs.docker.com/compose/) — versão 2+

Para rodar localmente sem Docker:

- [Python 3.11+](https://www.python.org/downloads/)
- pip — gerenciador de pacotes Python
- Navegador web moderno com suporte a ES6+

---

## Setup do Ambiente

### Com Docker *(recomendado)*

**1. Clone o repositório:**
```bash
git clone https://github.com/seu-usuario/auth-service.git
cd auth-service
```

**2. Crie o arquivo de variáveis de ambiente:**
```bash
cp .env.example .env
```

**3. Edite o `.env` com sua chave secreta:**
```env
SECRET_KEY=sua-chave-secreta-muito-longa-e-aleatoria-aqui
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
```

Para gerar uma `SECRET_KEY` segura:
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

**4. Suba o container:**
```bash
docker compose up --build -d
```

---

### Sem Docker *(execução local)*

**1. Clone o repositório:**
```bash
git clone https://github.com/seu-usuario/auth-service.git
cd auth-service
```

**2. Crie e ative o ambiente virtual:**
```bash
# Linux / Mac
python -m venv venv
source venv/bin/activate

# Windows
python -m venv venv
venv\Scripts\activate
```

**3. Instale as dependências:**
```bash
pip install -r requirements.txt
```

**4. Crie o arquivo de variáveis de ambiente:**
```bash
cp .env.example .env
# Edite o .env com sua SECRET_KEY
```

---

## Como Rodar

### Docker

| Ação | Comando |
|---|---|
| Subir o serviço | `docker compose up --build -d` |
| Parar o serviço | `docker compose down` |
| Ver logs em tempo real | `docker logs auth-service-v2 -f` |
| Verificar status do container | `docker ps` |
| Reconstruir sem cache | `docker compose build --no-cache` |

**Após subir, acesse:**
```
Frontend:  http://localhost:8000
API Docs:  http://localhost:8000/docs
Health:    http://localhost:8000/health
```

---

### Sem Docker

```bash
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

O flag `--reload` reinicia o servidor automaticamente ao detectar alterações nos arquivos — ideal para desenvolvimento.

**Após iniciar, acesse:**
```
Frontend:  http://localhost:8000
API Docs:  http://localhost:8000/docs
Health:    http://localhost:8000/health
```

---

## Estrutura de Arquivos

```
auth-service/
│
├── backend/                          → Código Python da API
│   ├── api/
│   │   └── auth_routes.py            → Endpoints HTTP (registro, login, /me, /health)
│   ├── core/
│   │   ├── config.py                 → Configurações via pydantic-settings + .env
│   │   ├── logger.py                 → Logger para stdout (compatível com Docker)
│   │   └── security.py               → bcrypt (hash de senhas) + JWT (criar/decodificar)
│   ├── dependencies/
│   │   └── dependencies.py           → Singleton do repositório + get_current_user
│   ├── models/
│   │   └── user.py                   → Entidade de domínio User (sem dependências externas)
│   ├── repositories/
│   │   └── user_repository.py        → CRUD in-memory com Dict[int, User]
│   ├── schemas/
│   │   └── user_schemas.py           → DTOs Pydantic: UserCreate, UserOut, Token
│   ├── services/
│   │   └── auth_service.py           → Regras de negócio: registro e autenticação
│   └── main.py                       → Entry point: FastAPI app + mount do frontend
│
├── frontend/                         → Interface web (HTML/CSS/JS vanilla)
│   ├── index.html                    → Login e cadastro com toggle animado
│   ├── home.html                     → Dashboard do usuário autenticado
│   ├── status.html                   → Monitoramento de endpoints em tempo real
│   ├── css/
│   │   ├── tokens.css                → Design tokens: cores, fontes, sombras, grid
│   │   ├── components.css            → Header, nav, footer, botões, inputs, cards
│   │   ├── auth.css                  → Estilos exclusivos da página de autenticação
│   │   ├── home.css                  → Estilos do dashboard (perfil, JWT, sessão)
│   │   ├── status.css                → Estilos do painel de status e log terminal
│   │   └── responsive.css            → Breakpoints: 1024px, 768px, 480px, 360px
│   └── js/
│       ├── utils.js                  → Helpers: DOM, Session, alertas, toggleEye
│       ├── theme.js                  → Alternância dark/light com persistência
│       ├── nav.js                    → Menu mobile com acessibilidade (aria, Escape)
│       ├── auth.js                   → Login, cadastro, força de senha
│       ├── home.js                   → /me, exibição JWT, logout
│       └── status.js                 → Ping endpoints, latência, log terminal
│
├── read-model/
│   └── img/                          → Screenshots para o README
│       ├── Banner.png
│       ├── Login01.png
│       ├── Login02.png
│       ├── Cadastro01.png
│       ├── Home01.png
│       ├── Home02.png
│       └── Status.png
│
├── .env                              → Variáveis reais (não commitado)
├── .env.example                      → Template de configuração (commitado)
├── .gitignore                        → Ignora .env, __pycache__, venv, etc.
├── docker-compose.yml                → Orquestração do container
├── Dockerfile                        → Build da imagem Python 3.11-slim
├── requirements.txt                  → Dependências Python
├── README.md                         → Documentação principal
├── CONTRIBUTING.md                   → Guia de contribuição (PT-BR e EN-US)
├── MODEL.md                          → Documentação arquitetural aprofundada
├── STRUCTURE.md                      → Este arquivo — setup e estrutura
└── LICENSE                           → Licença MIT
```

---

## Decisões Arquiteturais

### Camadas separadas — routes → service → repository → model

Cada camada tem responsabilidade única:

- **Routes** (`auth_routes.py`) — recebe a requisição HTTP, delega ao service, retorna a resposta
- **Service** (`auth_service.py`) — aplica regras de negócio sem conhecer HTTP
- **Repository** (`user_repository.py`) — isola o acesso a dados; trocar in-memory por banco real exige mudança apenas aqui
- **Model** (`user.py`) — entidade pura de domínio, sem dependências externas

### Injeção de dependência com FastAPI `Depends()`

O `UserRepository` é instanciado uma única vez como **singleton** em `dependencies.py` e injetado via `Depends()` em todas as rotas que precisam dele. Isso garante que os dados in-memory sejam compartilhados entre requests sem estado duplicado.

### Frontend servido pelo backend

A montagem do `StaticFiles` na raiz `/` é feita **após** o registro das rotas da API — garantindo que `/health`, `/register`, `/token` e `/me` tenham prioridade sobre os arquivos estáticos. Isso elimina a necessidade de um servidor web separado no deploy.

### Healthcheck integrado ao Docker

O `Dockerfile` declara um `HEALTHCHECK` apontando para `GET /health`. O Docker monitora automaticamente a saúde do container e o `docker ps` exibe o status `(healthy)` ou `(unhealthy)`.

---

> ⚠️ **Atenção** — O armazenamento in-memory significa que **todos os usuários são perdidos ao reiniciar o container**. Isso é esperado para o escopo atual do projeto. Para persistência real, a próxima evolução seria integrar SQLite com SQLAlchemy, alterando apenas `user_repository.py`.

<img width=100% src="https://capsule-render.vercel.app/api?type=waving&color=gradient&customColorList=6&height=120&section=footer"/>
