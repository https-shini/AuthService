"""Identificação do cliente atrás (ou não) de proxies reversos.

`X-Forwarded-For` é texto enviado pelo cliente: qualquer um pode escrever
o IP que quiser no início da lista. Só os itens ACRESCENTADOS pelos
proxies confiáveis (o fim da lista) são confiáveis. Com
TRUSTED_PROXY_HOPS = N, o IP do cliente é o N-ésimo item a partir do fim;
com 0 (padrão) o header é ignorado e vale o IP da conexão.

Não combine com FORWARDED_ALLOW_IPS do uvicorn: ele reescreveria o IP da
conexão antes de chegar aqui.
"""

from typing import List

from starlette.requests import Request

UNKNOWN_CLIENT = "unknown"


def _forwarded_chain(request: Request, header: str) -> List[str]:
    raw = ",".join(request.headers.getlist(header))
    return [item.strip() for item in raw.split(",") if item.strip()]


def get_client_ip(request: Request, trusted_hops: int) -> str:
    direct = request.client.host if request.client else UNKNOWN_CLIENT
    if trusted_hops <= 0:
        return direct
    chain = _forwarded_chain(request, "x-forwarded-for")
    if len(chain) < trusted_hops:
        return direct
    return chain[-trusted_hops]


def is_https(request: Request, trusted_hops: int) -> bool:
    if request.url.scheme == "https":
        return True
    if trusted_hops <= 0:
        return False
    chain = _forwarded_chain(request, "x-forwarded-proto")
    return bool(chain) and chain[-1].lower() == "https"
