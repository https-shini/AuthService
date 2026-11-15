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

Há uma entidade de domínio persistida, `User`, e o estado de sessão mantido pelo `TokenService`. Tudo fica em memória, por processo.

### `User` — `backend/models/user.py`

| Atributo | Tipo | Origem | Observação |
|---|---|---|---|
| `id` | `int` | gerado pelo repositório | auto-incremental a partir de 1, por processo |
| `email` | `str` | cadastro | normalizado para minúsculas (domínio e parte local) — ver [política de e-mail](#política-de-e-mail) |
| `hashed_password` | `str` | cadastro | hash bcrypt com salt aleatório; a senha em texto nunca é guardada |
| `name` | `str \| None` | cadastro (opcional) | nome de exibição; `None` para quem não informou e para usuários anteriores ao campo |

### Sessão — `backend/services/token_service.py`

Cada login abre uma sessão; uma sessão pertence a um usuário e tem vários tokens ao longo da vida.

| Elemento | Conteúdo | Guardado como |
|---|---|---|
| Sessão (`sid`) | `user_id`, prazo absoluto, `revoked` | registro em memória |
| Refresh token | valor aleatório de 256 bits, um por rotação | hash SHA-256 → `sid`, hash do CSRF, instante da rotação |
| Token CSRF | valor aleatório de 256 bits, renovado a cada refresh | hash SHA-256, junto do refresh |
| Access tokens revogados | `jti` → `exp` | removidos quando o `exp` passa |

Relacionamentos: `User 1 ── N Sessão 1 ── N refresh tokens (só o último é válido)`. Um access token aponta para a sessão pelo `sid`.

### Schemas (DTOs) — `backend/schemas/user_schemas.py`

| Schema | Uso | Campos |
|---|---|---|
| `UserCreate` | corpo de `POST /register` | `email: EmailStr` (normalizado), `password: str`, `name: str \| None` |
| `UserOut` | resposta de `/register` e `/me` | `id: int`, `email: EmailStr`, `name: str \| None` |
| `Token` | resposta de `/token` e `/refresh` | `access_token: str`, `token_type: str` (sempre `"bearer"`) |

O login recebe `OAuth2PasswordRequestForm` (form-urlencoded com `username` e `password`).

### Access token (JWT) — `backend/core/security.py`

| Claim | Conteúdo |
|---|---|
| `sub` | e-mail do usuário, como está salvo |
| `sid` | sessão à qual o token pertence |
| `jti` | identificador único (permite revogar este token) |
| `type` | sempre `"access"` |
| `iat` / `exp` | emissão e expiração (`ACCESS_TOKEN_EXPIRE_MINUTES`, limitada ao fim da sessão) |

Assinatura `HS256` (ou `HS384`/`HS512` por `ALGORITHM`) com `SECRET_KEY`. Tokens sem `sid`, `jti` ou `type` — como os emitidos por versões anteriores — são recusados.

### Repositório — `backend/repositories/user_repository.py`

`Dict[int, User]` em memória, com índice pela forma normalizada do e-mail. Instância única criada em `dependencies.py`, junto com o `TokenService` e o `LoginRateLimiter`.

---

## Regras de negócio

| # | Regra | Onde | Resultado quando violada |
|---|---|---|---|
| R1 | E-mail válido | `UserCreate.email` (`EmailStr`) | `422` |
| R2 | Senha com 8 caracteres ou mais | `min_length=8` | `422` |
| R3 | Senha com pelo menos um número | `password_strength` | `422` — "A senha deve conter pelo menos um número" |
| R4 | Senha com pelo menos uma letra | `password_strength` | `422` — "A senha deve conter pelo menos uma letra" |
| R5 | Senha com no máximo 72 bytes (limite do bcrypt) | `password_strength` | `422` — "A senha pode ter no máximo 72 bytes" |
| R6 | Nome opcional: até 100 caracteres, sem caracteres de controle; espaços são aparados e unificados; vazio vira `null` | `clean_name` | `422` |
| R7 | E-mail único, sem diferenciar maiúsculas | `AuthService.register_user` | `400` — "Email já registrado" |
| R8 | Login exige conta existente e senha correta | `AuthService.authenticate_user` | `401` — "Email ou senha incorretos" (igual para e-mail inexistente) |
| R9 | Limite de tentativas de login (IP, IP + conta, conta) | `LoginRateLimiter` | `429` + `Retry-After` |
| R10 | Rotas protegidas exigem access token válido, não expirado, não revogado, de sessão ativa e de usuário existente | `get_current_user` | `401` — "Não foi possível validar as credenciais" |
| R11 | Refresh exige cookie de refresh válido e o CSRF da mesma sessão | `TokenService.rotate` | `403` (CSRF) · `401` (sessão inválida/expirada/revogada) |
| R12 | Refresh token já trocado reaparecendo após a tolerância revoga a sessão | `TokenService.rotate` | `401` e sessão revogada |

Observações:
- R3 e R4 usam `str.isdigit()` e `str.isalpha()`, que aceitam Unicode (letras acentuadas contam).
- Maiúsculas e símbolos **não** são exigidos; o medidor de força do frontend é só indicativo.
- Para e-mail inexistente o login executa um bcrypt descartável: o tempo de resposta não revela se a conta existe.

### Política de e-mail

- **Regra:** o endereço inteiro é armazenado e comparado em minúsculas, sem espaços nas pontas (`backend/core/email.py`). Vale no cadastro, no login e no rate limiting.
- **Compatibilidade:** contas criadas antes da regra podem ter maiúsculas na parte local. Não há migração (o e-mail salvo não é reescrito). O login procura, nesta ordem:
  1. igualdade exata com o texto digitado;
  2. igualdade exata com a forma normalizada;
  3. uma única conta com a mesma forma normalizada.

  Se no passo 3 houver mais de uma candidata (duplicatas antigas que só diferem na caixa, nenhuma em minúsculas), o login é recusado com o `401` genérico; cada uma continua entrando com a forma exata.
- **Duplicatas novas** são impossíveis: o cadastro compara pela forma normalizada, inclusive contra contas antigas.

---

## Fluxos

### Cadastro

```
1. Usuário informa nome (opcional), e-mail e senha na aba "Criar conta".
2. Frontend valida no cliente as mesmas regras (R1–R6) e mostra erros por campo.
3. POST /register  (JSON { email, password, name? })
4. Pydantic normaliza e valida → 422 com a lista de erros, se houver.
5. AuthService verifica R7 → 400 se o e-mail já existe (ignorando maiúsculas).
6. bcrypt gera o hash; o repositório salva o usuário com o próximo ID.
7. 201 { id, email, name }. A senha nunca volta na resposta.
8. Frontend muda para "Entrar" com o e-mail normalizado preenchido.
```

### Login

```
1. POST /token  (form username=<e-mail>, password)
2. Rate limiting: bloqueado → 429 + Retry-After (a senha nem é verificada).
3. AuthService encontra a conta (política de e-mail) e confere o hash → 401 se falhar
   (a falha conta para o IP+conta e para a conta).
4. TokenService abre a sessão: access token (corpo) + cookies de refresh (HttpOnly) e CSRF.
5. Frontend guarda só o access token no sessionStorage e vai para o painel.
```

### Uso, renovação e encerramento

```
· GET /me com Authorization: Bearer <access>
    → valida assinatura, exp, type, jti não revogado e sessão ativa; busca o usuário pelo sub.
· Access vencido (detectado pelo exp ou por um 401):
    frontend → POST /refresh com o cookie e X-CSRF-Token (uma renovação por vez, entre abas)
    servidor → confere o CSRF da sessão, invalida o refresh usado, emite novo refresh, CSRF e access.
    Se a renovação falhar → o frontend limpa a sessão e mostra "Sessão expirada/inválida".
· Refresh já trocado reapresentado:
    dentro de REFRESH_REUSE_GRACE_SECONDS → 401, sessão mantida (corrida entre abas);
    depois disso → 401 e a sessão inteira é revogada (alguém tem uma cópia).
· "Encerrar sessão": POST /logout com o Bearer (e o CSRF, se houver)
    → revoga o jti, a sessão e todos os seus tokens; apaga os cookies.
    Só com o cookie (access vencido) → exige X-CSRF-Token válido.
· A sessão tem prazo absoluto (REFRESH_TOKEN_EXPIRE_MINUTES desde o login).
```

### Proteção de rota (backend)

```python
# backend/dependencies/dependencies.py
def get_access_payload(token = Depends(oauth2_scheme), tokens = Depends(get_token_service)) -> dict:
    payload = tokens.validate_access(token)   # assinatura, exp, type, jti revogado, sessão ativa
    if payload is None: raise 401
    return payload

def get_current_user(payload = Depends(get_access_payload), user_repo = Depends(get_user_repository)) -> User:
    return user_repo.get_by_email(payload["sub"]) or raise 401
```

---

## Frontend

O frontend é estático (HTML, CSS e JS nativos), servido pelo FastAPI na raiz. Não há build.

| Página | Responsabilidade | Endpoints usados |
|---|---|---|
| `index.html` | Entrar e criar conta (com nome opcional), avisos de sessão, indicador de disponibilidade, bloqueio após 429 | `/token`, `/register`, `/health` |
| `home.html` | Painel: identidade, conta, sessão, renovação automática, token oculto, encerrar sessão | `/me`, `/refresh`, `/logout` |
| `status.html` | Verificações reais, legenda de estados, contratos e histórico da visita | `/health`, `/me` (e `/refresh` se o token tiver vencido) |

`js/core/auth.js` concentra as chamadas autenticadas (`withSession`), a renovação serializada (uma por aba e, com Web Locks, uma entre abas) e o logout.

### Estado guardado no navegador

| Chave | Armazenamento | Conteúdo |
|---|---|---|
| `auth_token` | `sessionStorage` | o access token |
| `auth_login_at` | `sessionStorage` | horário do login neste navegador (preservado nas renovações) |
| `auth_theme` | `localStorage` | `dark` ou `light`, só quando o usuário escolhe |
| `__Host-auth_refresh` | cookie `HttpOnly` | refresh token — o JavaScript não lê |
| `__Host-auth_csrf` | cookie legível | token CSRF da sessão, enviado em `X-CSRF-Token` |

Com `COOKIE_SECURE=false` os cookies perdem o prefixo `__Host-`. As chaves `auth_pass` e `auth_email` de versões antigas são apagadas automaticamente.

### Estados da página de status

| Estado | Significado |
|---|---|
| Disponível | a rota respondeu com sucesso agora |
| Indisponível | a rota respondeu com erro HTTP (4xx/5xx, exceto 401) |
| Falha de autenticação | `/me` respondeu 401 e a renovação também falhou (o token local é removido) |
| Falha de comunicação | sem resposta (rede, servidor fora, timeout de 10 s) |
| Não verificado | a rota não foi consultada: `/register`, `/token`, `/refresh` e `/logout` nunca são chamados pela página, e `/me` precisa de sessão |

---

## Decisões arquiteturais

**FastAPI** — validação automática com Pydantic, documentação em `/docs` e injeção de dependências com pouco código.

**Camadas** — rotas → services → repository → model, com `core/` para o que é transversal (configuração, segurança, e-mail, rede, cookies, rate limit, headers). Trocar o armazenamento em memória por um banco afeta o repositório e o `TokenService`.

**Estado em memória** — usuários, sessões e contadores ficam no processo. Mantém o projeto sem dependências externas; o custo é perder tudo a cada reinício e exigir uma única instância.

**Access Bearer + refresh em cookie** — o access token continua no corpo (compatível com Swagger, cURL e outros clientes Bearer) e é curto e revogável. O refresh token, de longa duração, fica em cookie `HttpOnly; Secure; SameSite=Strict` com CSRF por sessão. Colocar também o access token em cookie exigiria CSRF em todas as rotas e dois modos de autenticação.

**Rate limiting próprio** — três contadores com janela deslizante, sem biblioteca nova, coerente com o estado em memória. O IP só vem de `X-Forwarded-For` quando há proxy confiável configurado.

**Headers no servidor** — a CSP das páginas é a mesma do `<meta>` (um teste garante), acrescida de `frame-ancestors`, que só funciona por header.

**Frontend servido pelo backend** — `StaticFiles` montado em `/` depois das rotas da API: um processo, um container, mesma origem (sem CORS) e cookies `SameSite=Strict` funcionando sem configuração extra.

**Frontend sem framework** — módulos ES nativos (`js/core/` compartilhado e `js/pages/` por página), sem build.

**Identidade do portfólio** — os tokens de cor, tipografia, raio e movimento vêm do design system de [gcruz.dev.br](https://gcruz.dev.br).

<img width=100% src="https://capsule-render.vercel.app/api?type=waving&color=gradient&customColorList=6&height=120&section=footer"/>
