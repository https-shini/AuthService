<img width=100% src="https://capsule-render.vercel.app/api?type=waving&color=gradient&customColorList=6&height=120&section=header"/>

<h1 align="center">📚 Documentação Arquitetural</h1>

<p align="center">
  <a href="#decisões-arquiteturais">Decisões Arquiteturais</a>&nbsp;&nbsp;&nbsp;|&nbsp;&nbsp;&nbsp;
  <a href="#estrutura-do-projeto">Estrutura do Projeto</a>&nbsp;&nbsp;&nbsp;|&nbsp;&nbsp;&nbsp;
  <a href="#fluxo-de-funcionamento">Fluxo de Funcionamento</a>&nbsp;&nbsp;&nbsp;|&nbsp;&nbsp;&nbsp;
  <a href="./README.md">Voltar</a>
</p>

---

## Decisões Arquiteturais

O **AuthService** foi construído com separação clara de responsabilidades em camadas, seguindo os princípios de Clean Architecture de forma pragmática para o escopo do projeto.

### Por que FastAPI?
FastAPI oferece validação automática de dados via Pydantic, documentação Swagger gerada automaticamente em `/docs`, suporte nativo a async e injeção de dependências — tudo sem boilerplate excessivo. É a escolha ideal para um serviço de autenticação moderno em Python.

### Por que armazenamento in-memory?
O repositório `UserRepository` usa um dicionário Python como banco de dados. Essa decisão foi intencional para manter o projeto focado na lógica de autenticação, sem dependência externa de banco de dados. A camada de repositório está isolada — substituir por SQLAlchemy + PostgreSQL exigiria alterações apenas em `user_repository.py`, sem tocar no service ou nas rotas.

### Por que o frontend é servido pelo próprio backend?
Montar o frontend como `StaticFiles` no FastAPI elimina a necessidade de um servidor web separado (Nginx, por exemplo), simplificando o deploy para um único container. As rotas da API são registradas **antes** da montagem estática, garantindo prioridade correta.

### Por que JWT com HS256?
JWT stateless elimina a necessidade de sessões no servidor. HS256 com uma `SECRET_KEY` forte é suficiente para o escopo do projeto. O token carrega apenas o `sub` (e-mail do usuário) e o `exp` (expiração), seguindo o princípio de mínimo privilégio.

---

## Estrutura do Projeto

### Camadas do Backend

```
HTTP Request
     │
     ▼
auth_routes.py      ← Controller: valida entrada, chama service, retorna resposta HTTP
     │
     ▼
auth_service.py     ← Service: regras de negócio (registro, autenticação)
     │
     ▼
user_repository.py  ← Repository: acesso e persistência de dados
     │
     ▼
user.py             ← Model: entidade de domínio (sem dependências externas)
```

### Módulos do Core

| Módulo | Responsabilidade |
|---|---|
| `core/config.py` | Carrega variáveis de ambiente via pydantic-settings |
| `core/security.py` | Hash bcrypt e operações JWT (criar/decodificar) |
| `core/logger.py` | Logger configurado para stdout (compatível com Docker) |
| `dependencies/dependencies.py` | Singleton do repositório e `get_current_user` para proteção de rotas |
| `schemas/user_schemas.py` | DTOs de entrada e saída com validação Pydantic |

---

### Frontend (`frontend/`)

**`index.html` — Login / Cadastro**
- Toggle animado entre formulários com CSS puro (sem JavaScript para animar)
- Painel lateral deslizante no desktop usando `transform` + `z-index`
- Mobile: empilhamento vertical com transição suave
- Medidor de força de senha: 5 critérios (comprimento, maiúscula, número, especial, comprimento extra)

**`home.html` — Dashboard**
- Carrega dados do usuário via `GET /me` com Bearer Token
- Exibe token JWT completo com função de cópia para clipboard
- Estado sem sessão: tela de acesso negado com redirecionamento
- Informações de sessão: status, expiração, origem, algoritmo

**`status.html` — Monitoramento**
- Ping individual de cada endpoint com medição de latência (`performance.now()`)
- Log terminal com timestamp, codificação por cor e scroll automático
- Cards de endpoint exibem: método HTTP, path, autenticação, schema e última verificação

**`js/utils.js` — Utilitários compartilhados**
- `Session`: wrapper do `sessionStorage` para token, e-mail e senha
- `showAlert` / `showPageAlert`: sistema de alertas inline e temporários
- `toggleEye`: alternância de visibilidade de campos de senha
- `parseApiError`: extrai mensagem legível de erros FastAPI (string ou array de validação)

**`css/tokens.css` — Design System**
- Dois temas completos (`[data-theme="dark"]` e `[data-theme="light"]`)
- Grid terminal de fundo via `background-image: linear-gradient(...)` — sem imagens externas
- Variáveis semânticas: `--color-accent`, `--color-danger`, `--color-surface-raised`, etc.

---

## Fluxo de Funcionamento

### Registro de usuário

```
1. Usuário preenche nome, e-mail e senha no formulário
2. Frontend valida campos (não vazio) e envia POST /register
3. UserCreate (Pydantic) valida: EmailStr, min_length=8, dígito e letra
4. AuthService verifica se e-mail já existe no repositório
5. bcrypt gera hash da senha com salt aleatório
6. UserRepository salva o usuário com ID auto-incrementado
7. UserOut (id, email) é retornado — senha nunca exposta
```

### Autenticação e acesso a rota protegida

```
1. Usuário preenche e-mail e senha no formulário de login
2. Frontend envia POST /token com form-encoded (username + password)
3. AuthService busca usuário por e-mail e verifica hash bcrypt
4. JWT é gerado com sub=email e exp=agora+30min, assinado com SECRET_KEY
5. Frontend armazena token no sessionStorage
6. Requisição a GET /me inclui Authorization: Bearer <token>
7. get_current_user decodifica o JWT, extrai e-mail, busca usuário no repositório
8. Dados do usuário são retornados (id, email)
```

### Proteção de rotas

```python
# dependencies.py
def get_current_user(
    token: str = Depends(oauth2_scheme),      # extrai Bearer do header
    user_repo: UserRepository = Depends(...), # singleton do repositório
) -> User:
    payload = decode_access_token(token)      # decodifica e valida JWT
    email = payload.get("sub")                # extrai identidade
    user = user_repo.get_by_email(email)      # busca usuário
    return user                               # injeta na rota
```

---

## Configuração e Deploy

### Variáveis de ambiente

O `config.py` usa `pydantic-settings` com `SettingsConfigDict(env_file=".env")`. A `SECRET_KEY` não possui valor padrão — se ausente, a aplicação falha na inicialização com erro explícito, evitando deploy acidental sem configuração.

### Docker

O `Dockerfile` usa `python:3.11-slim` para imagem enxuta. O `COPY` das pastas `backend/` e `frontend/` é feito após a instalação das dependências, aproveitando o cache de layers do Docker — rebuilds sem mudanças no `requirements.txt` são mais rápidos.

O `HEALTHCHECK` do Dockerfile aponta para `GET /health`, permitindo que o Docker Compose (e orquestradores como Kubernetes) monitorem a saúde do container automaticamente.

---

> **Limitações conhecidas e próximos passos**
>
> - Armazenamento in-memory: dados perdidos ao reiniciar o container. Próximo passo natural: SQLite com SQLAlchemy.
> - Sem rate limiting no endpoint `/token`: vulnerável a força bruta. Recomendado: `slowapi` ou middleware customizado.
> - Busca de usuário por e-mail é O(n): aceitável em escala pequena. Melhoria: índice por e-mail com `Dict[str, User]`.

<img width=100% src="https://capsule-render.vercel.app/api?type=waving&color=gradient&customColorList=6&height=120&section=footer"/>
