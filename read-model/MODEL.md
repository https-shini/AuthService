<img width=100% src="https://capsule-render.vercel.app/api?type=waving&color=gradient&customColorList=6&height=120&section=header"/>

<h1 align="center">📚 Modelo, Regras e Fluxos</h1>

<p align="center">
  <a href="#entidades">Entidades</a>&nbsp;&nbsp;|&nbsp;&nbsp;
  <a href="#regras-de-negócio">Regras de negócio</a>&nbsp;&nbsp;|&nbsp;&nbsp;
  <a href="#fluxos">Fluxos</a>&nbsp;&nbsp;|&nbsp;&nbsp;
  <a href="#frontend">Frontend</a>&nbsp;&nbsp;|&nbsp;&nbsp;
  <a href="#decisões-arquiteturais">Decisões</a>&nbsp;&nbsp;|&nbsp;&nbsp;
  <a href="../README.md">Voltar ao README</a>
</p>

---

Este documento descreve **o que está implementado hoje**. O que ainda é plano está na seção "Pendências / Roadmap" do [README](../README.md).

## Entidades

O domínio tem uma única entidade persistida, `User`, e nenhum relacionamento.

### `User` — `backend/models/user.py`

| Atributo | Tipo | Origem | Observação |
|---|---|---|---|
| `id` | `int` | gerado pelo repositório | auto-incremental a partir de 1, por processo |
| `email` | `str` | cadastro | validado como `EmailStr`; o domínio é normalizado para minúsculas pelo validador, a parte local não |
| `hashed_password` | `str` | cadastro | hash bcrypt com salt aleatório; a senha em texto nunca é guardada |

> **Não existe campo de nome.** Versões anteriores do frontend pediam "nome completo", mas o valor era descartado: o backend nunca o recebeu nem o persistiu. O frontend atual não coleta nome. Adicionar `name` exige mudança no modelo e no schema (ver roadmap).

### Schemas (DTOs) — `backend/schemas/user_schemas.py`

| Schema | Uso | Campos |
|---|---|---|
| `UserCreate` | corpo de `POST /register` | `email: EmailStr`, `password: str` (validado, ver regras) |
| `UserOut` | resposta de `/register` e `/me` | `id: int`, `email: EmailStr` |
| `Token` | resposta de `/token` | `access_token: str`, `token_type: str` (sempre `"bearer"`) |

O login não usa schema próprio: recebe `OAuth2PasswordRequestForm` (form-urlencoded com `username` e `password`).

### Payload do JWT — `backend/core/security.py`

| Claim | Conteúdo |
|---|---|
| `sub` | e-mail do usuário |
| `exp` | instante de expiração (agora + `ACCESS_TOKEN_EXPIRE_MINUTES`) |

Assinatura `HS256` (configurável por `ALGORITHM`) com `SECRET_KEY`. Não há `iat`, `jti`, papéis ou outros claims.

### Armazenamento — `backend/repositories/user_repository.py`

`UserRepository` guarda `Dict[int, User]` em memória, com uma instância única (singleton) criada em `dependencies.py`. A busca por e-mail percorre todos os usuários (O(n)) e compara a string exatamente. Tudo se perde quando o processo reinicia.

---

## Regras de negócio

| # | Regra | Onde | Resultado quando violada |
|---|---|---|---|
| R1 | E-mail precisa ser válido | `UserCreate.email` (`EmailStr`) | `422` |
| R2 | Senha com no mínimo 8 caracteres | `UserCreate.password` (`min_length=8`) | `422` |
| R3 | Senha com pelo menos um número | validador `password_strength` | `422` — "A senha deve conter pelo menos um número" |
| R4 | Senha com pelo menos uma letra | validador `password_strength` | `422` — "A senha deve conter pelo menos uma letra" |
| R5 | E-mail único | `AuthService.register_user` | `400` — "Email já registrado" |
| R6 | Login exige e-mail existente e senha que confere com o hash | `AuthService.authenticate_user` | `401` — "Email ou senha incorretos" |
| R7 | Rotas protegidas exigem token válido, não expirado, cujo `sub` exista | `get_current_user` | `401` — "Não foi possível validar as credenciais" |

Observações:
- R3 e R4 usam `str.isdigit()` e `str.isalpha()`, que aceitam caracteres Unicode (letras acentuadas contam como letra).
- Maiúsculas e símbolos **não** são exigidos. O medidor de força do frontend os valoriza, mas é só indicativo.
- O e-mail é comparado exatamente (R5, R6): `Usuario@x.com` e `usuario@x.com` são contas diferentes.

---

## Fluxos

### Cadastro

```
1. Usuário informa e-mail e senha na aba "Criar conta".
2. Frontend valida no cliente as mesmas regras R1–R4 e mostra os erros por campo.
3. POST /register  (JSON { email, password })
4. Pydantic valida R1–R4  → 422 com a lista de erros, se houver.
5. AuthService verifica R5 → 400 se o e-mail já existe.
6. bcrypt gera o hash; o repositório salva o usuário com o próximo ID.
7. 200 { id, email }. A senha nunca volta na resposta.
8. Frontend muda para a aba "Entrar" com o e-mail preenchido.
```

### Login e acesso à rota protegida

```
1. POST /token  (form username=<e-mail>, password)
2. AuthService busca o usuário e confere o hash (R6) → 401 se falhar.
3. JWT com sub=e-mail e exp=agora+N minutos, assinado com SECRET_KEY.
4. 200 { access_token, token_type: "bearer" }
5. Frontend guarda só o token no sessionStorage (e o horário do login) e vai para o painel.
6. GET /me com Authorization: Bearer <token>
7. get_current_user decodifica e valida o token, busca o usuário pelo sub (R7).
8. 200 { id, email }
```

### Expiração e encerramento de sessão (frontend)

```
· O painel lê exp do token apenas para exibir o prazo e agendar o encerramento.
· Quando o prazo chega, ou quando qualquer chamada a /me volta 401:
    remove o token do navegador → mostra "Sessão expirada" ou "Sessão inválida".
· "Encerrar sessão" remove os dados locais e volta à página de acesso.
· Não há logout no servidor: um token copiado continua válido até expirar.
```

### Proteção de rota (backend)

```python
# backend/dependencies/dependencies.py
def get_current_user(token = Depends(oauth2_scheme), user_repo = Depends(get_user_repository)) -> User:
    payload = decode_access_token(token)        # None se assinatura/expiração falharem
    email = payload.get("sub")                  # identidade
    user = user_repo.get_by_email(email)        # precisa existir
    return user                                 # qualquer falha acima → 401
```

---

## Frontend

O frontend é estático (HTML, CSS e JS nativos), servido pelo FastAPI na raiz. Não há build.

| Página | Responsabilidade | Endpoints usados |
|---|---|---|
| `index.html` | Entrar e criar conta, aviso de sessão ativa/expirada, indicador de disponibilidade | `/token`, `/register`, `/health` |
| `home.html` | Painel: identidade, conta, sessão, token oculto, atualizar e encerrar sessão | `/me` |
| `status.html` | Verificações reais, legenda de estados, contratos e histórico da visita | `/health`, `/me` |

### Estado guardado no navegador

| Chave | Armazenamento | Conteúdo |
|---|---|---|
| `auth_token` | `sessionStorage` | o JWT de acesso |
| `auth_login_at` | `sessionStorage` | horário do login neste navegador (milissegundos) |
| `auth_theme` | `localStorage` | `dark` ou `light`, só quando o usuário escolhe |

As chaves `auth_pass` (senha em texto) e `auth_email`, gravadas por versões anteriores, são apagadas automaticamente na carga de qualquer página.

### Estados da página de status

| Estado | Significado |
|---|---|
| Disponível | a rota respondeu com sucesso agora |
| Indisponível | a rota respondeu com erro HTTP (4xx/5xx, exceto 401) |
| Falha de autenticação | `/me` respondeu 401 (o token local é removido) |
| Falha de comunicação | sem resposta (rede, servidor fora, timeout de 10 s) |
| Não verificado | a rota não foi consultada: `/register` e `/token` nunca são chamados automaticamente, e `/me` precisa de sessão |

---

## Decisões arquiteturais

**FastAPI** — validação automática com Pydantic, documentação em `/docs` e injeção de dependências com pouco código.

**Camadas** — rotas → service → repository → model. O service não conhece HTTP além das exceções e o repositório isola o armazenamento: trocar o dicionário em memória por um banco afeta só `user_repository.py`.

**Armazenamento em memória** — escolha deliberada para manter o foco na autenticação, sem dependência externa. O custo é perder os dados a cada reinício.

**Frontend servido pelo backend** — `StaticFiles` montado em `/` depois das rotas da API: um único processo e um único container, sem Nginx e sem CORS (mesma origem).

**JWT HS256 stateless** — sem sessão no servidor. O token carrega o mínimo (`sub`, `exp`).

**Frontend sem framework** — três páginas pequenas não justificam build ou dependências. Módulos ES nativos dão organização (`js/core/` compartilhado e `js/pages/` por página) sem ferramenta extra.

**Identidade do portfólio** — os tokens de cor, tipografia, raio e movimento vêm do design system de [gcruz.dev.br](https://gcruz.dev.br), para que os projetos do autor sejam reconhecidos como parte da mesma família.

<img width=100% src="https://capsule-render.vercel.app/api?type=waving&color=gradient&customColorList=6&height=120&section=footer"/>
