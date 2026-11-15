/* ==========================================================================
   core/api.js — Cliente HTTP da API do AuthService
   --------------------------------------------------------------------------
   Os contratos abaixo são exatamente os do backend (backend/api/
   auth_routes.py) e não devem mudar a partir do frontend:

     GET  /health    → 200 { status, message }
     POST /register  → JSON { email, password, name? } → 201 { id, email, name }
                       400 e-mail já registrado · 422 validação
     POST /token     → form-urlencoded { username, password }
                       → 200 { access_token, token_type: "bearer" } + cookies
                       de sessão (refresh HttpOnly e CSRF) · 401 · 429
     POST /refresh   → cookie de refresh + header X-CSRF-Token
                       → 200 { access_token, token_type } · 401 · 403
     POST /logout    → Bearer e/ou cookie + X-CSRF-Token → 204 · 403
     GET  /me        → Authorization: Bearer <token> → 200 { id, email, name } · 401

   Os cookies vão sozinhos (mesma origem, credentials: "same-origin"); o
   frontend nunca vê o refresh token, que é HttpOnly.

   `request()` nunca lança exceção: devolve { ok, status, data, durationMs,
   error }, com `error.kind` em um conjunto fechado, para que todas as
   páginas tratem falhas do mesmo jeito.
   ========================================================================== */

const DEFAULT_TIMEOUT_MS = 10_000;

export const ErrorKind = Object.freeze({
    NETWORK: "network", //       sem resposta (servidor fora, CORS, offline)
    TIMEOUT: "timeout", //       sem resposta dentro do prazo
    UNAUTHORIZED: "unauthorized", // 401
    FORBIDDEN: "forbidden", //       403 (CSRF)
    BAD_REQUEST: "bad_request", //  400
    RATE_LIMITED: "rate_limited", // 429 (ver retryAfter)
    VALIDATION: "validation", //   422
    SERVER: "server", //           5xx
    HTTP: "http", //               qualquer outro status de erro
});

/* Mensagens de validação do Pydantic → português. As regras de senha do
   backend já respondem em português ("Value error, A senha deve…"). */
function translateValidationError(entry, field) {
    switch (entry?.type) {
        case "string_too_short":
            return `Deve ter no mínimo ${entry.ctx?.min_length ?? 8} caracteres.`;
        case "missing":
            return "Campo obrigatório.";
        case "value_error":
            if (field === "email" || /email/i.test(entry.msg ?? "")) {
                return "Informe um e-mail válido.";
            }
            return String(entry.msg ?? "Valor inválido.").replace(
                /^Value error,\s*/i,
                "",
            );
        default:
            return String(entry?.msg ?? "Valor inválido.");
    }
}

/** Normaliza o `detail` do FastAPI (string ou lista de erros). */
export function parseErrorDetail(detail) {
    if (typeof detail === "string") return { message: detail, fields: [] };
    if (Array.isArray(detail)) {
        const fields = detail.map((entry) => {
            const loc = Array.isArray(entry?.loc) ? entry.loc : [];
            const field = String(loc[loc.length - 1] ?? "");
            return { field, message: translateValidationError(entry, field) };
        });
        return { message: fields.map((f) => f.message).join(" "), fields };
    }
    return { message: "", fields: [] };
}

function describeHttpError(status, data, headers) {
    const { message, fields } = parseErrorDetail(data?.detail);
    if (status === 429) {
        const retryAfter = Number.parseInt(headers?.get("retry-after") ?? "", 10);
        return {
            kind: ErrorKind.RATE_LIMITED,
            message: message || "Muitas tentativas. Aguarde e tente novamente.",
            retryAfter: Number.isFinite(retryAfter) && retryAfter > 0 ? retryAfter : null,
            fields,
        };
    }
    if (status === 403) {
        return { kind: ErrorKind.FORBIDDEN, message: message || "Operação recusada.", fields };
    }
    if (status === 401) {
        return {
            kind: ErrorKind.UNAUTHORIZED,
            message: message || "Credenciais inválidas ou sessão expirada.",
            fields,
        };
    }
    if (status === 422) {
        return {
            kind: ErrorKind.VALIDATION,
            message: message || "Dados inválidos.",
            fields,
        };
    }
    if (status === 400) {
        return {
            kind: ErrorKind.BAD_REQUEST,
            message: message || "Requisição recusada pelo servidor.",
            fields,
        };
    }
    if (status >= 500) {
        return {
            kind: ErrorKind.SERVER,
            message: `O servidor respondeu com erro (HTTP ${status}).`,
            fields,
        };
    }
    return {
        kind: ErrorKind.HTTP,
        message: message || `Resposta inesperada (HTTP ${status}).`,
        fields,
    };
}

async function readJson(response) {
    // O corpo é sempre lido até o fim (inclusive em 204): requisição com
    // corpo pendente fica aberta e é abortada se a página navegar em seguida.
    let text = "";
    try {
        text = await response.text();
    } catch {
        return null;
    }
    const type = response.headers.get("content-type") ?? "";
    if (!text || !type.includes("application/json")) return null;
    try {
        return JSON.parse(text);
    } catch {
        return null;
    }
}

export async function request(
    path,
    { method = "GET", json, form, token, headers: extraHeaders = {}, timeout = DEFAULT_TIMEOUT_MS } = {},
) {
    const headers = { Accept: "application/json", ...extraHeaders };
    let body;

    if (json !== undefined) {
        headers["Content-Type"] = "application/json";
        body = JSON.stringify(json);
    } else if (form !== undefined) {
        headers["Content-Type"] = "application/x-www-form-urlencoded";
        body = new URLSearchParams(form);
    }
    if (token) headers.Authorization = `Bearer ${token}`;

    const controller = new AbortController();
    const timer = window.setTimeout(() => controller.abort(), timeout);
    const started = performance.now();
    const elapsed = () => Math.round(performance.now() - started);

    try {
        const response = await fetch(path, {
            method,
            headers,
            body,
            cache: "no-store",
            credentials: "same-origin",
            signal: controller.signal,
        });
        const durationMs = elapsed();
        const data = await readJson(response);
        return {
            ok: response.ok,
            status: response.status,
            data,
            durationMs,
            error: response.ok ? null : describeHttpError(response.status, data, response.headers),
        };
    } catch (error) {
        const timedOut = error?.name === "AbortError";
        return {
            ok: false,
            status: 0,
            data: null,
            durationMs: elapsed(),
            error: timedOut
                ? {
                      kind: ErrorKind.TIMEOUT,
                      message: `Sem resposta em ${Math.round(timeout / 1000)} s.`,
                      fields: [],
                  }
                : {
                      kind: ErrorKind.NETWORK,
                      message: "Não foi possível conectar ao servidor.",
                      fields: [],
                  },
        };
    } finally {
        window.clearTimeout(timer);
    }
}

/* Endpoints ----------------------------------------------------------------- */

export const api = {
    health: () => request("/health"),
    register: (email, password, name) =>
        request("/register", {
            method: "POST",
            json: name ? { email, password, name } : { email, password },
        }),
    login: (email, password) =>
        request("/token", {
            method: "POST",
            form: { username: email, password },
        }),
    me: (token) => request("/me", { token }),
    refresh: (csrfToken) =>
        request("/refresh", { method: "POST", headers: { "X-CSRF-Token": csrfToken } }),
    logout: (token, csrfToken) =>
        request("/logout", {
            method: "POST",
            token,
            headers: csrfToken ? { "X-CSRF-Token": csrfToken } : {},
        }),
};
