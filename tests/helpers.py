"""Funções auxiliares compartilhadas pelos testes."""

PASSWORD = "Senha123"


def register(client, email, password=PASSWORD, name=None):
    body = {"email": email, "password": password}
    if name is not None:
        body["name"] = name
    return client.post("/register", json=body)


def login(client, email, password=PASSWORD, headers=None):
    return client.post("/token", data={"username": email, "password": password}, headers=headers or {})


def bearer(token):
    return {"Authorization": f"Bearer {token}"}


def csrf_header(client, names):
    return {"X-CSRF-Token": client.cookies.get(names.csrf)}


class FakeClock:
    """Relógio controlável para janelas de tempo (rate limit, expiração)."""

    def __init__(self, start):
        self.now = start

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds
