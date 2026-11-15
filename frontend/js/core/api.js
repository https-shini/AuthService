/* ==========================================================================
   core/api.js — Cliente HTTP da API do AuthService
   --------------------------------------------------------------------------
   Os contratos abaixo são exatamente os do backend (backend/api/
   auth_routes.py) e não devem mudar a partir do frontend:

     GET  /health    → 200 { status, message }
     POST /register  → JSON { email, password } → 200 { id, email }
                       400 e-mail já registrado · 422 validação
     POST /token     → form-urlencoded { username, password }
                       → 200 { access_token, token_type: "bearer" } · 401
     GET  /me        → Authorization: Bearer <token> → 200 { id, email } · 401

   `request()` nunca lança exceção: devolve { ok, status, data, durationMs,
   error }, com `error.kind` em um conjunto fechado, para que todas as
   páginas tratem falhas do mesmo jeito.
   ========================================================================== */

const DEFAULT_TIMEOUT_MS = 10_000;

export const ErrorKind = Object.freeze({
    NETWORK: "network", //       sem resposta (servidor fora, CORS, offline)
    TIMEOUT: "timeout", //       sem resposta dentro do prazo
    UNAUTHORIZED: "unauthorized", // 401
    BAD_REQUEST: "bad_request", //  400
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

function describeHttpError(status, data) {
    const { message, fields } = parseErrorDetail(data?.detail);
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
    const type = response.headers.get("content-type") ?? "";
    if (!type.includes("application/json")) return null;
    try {
        return await response.json();
    } catch {
        return null;
    }
}

export async function request(
    path,
    { method = "GET", json, form, token, timeout = DEFAULT_TIMEOUT_MS } = {},
) {
    const headers = { Accept: "application/json" };
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
            error: response.ok ? null : describeHttpError(response.status, data),
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
    register: (email, password) =>
        request("/register", { method: "POST", json: { email, password } }),
    login: (email, password) =>
        request("/token", {
            method: "POST",
            form: { username: email, password },
        }),
    me: (token) => request("/me", { token }),
};
