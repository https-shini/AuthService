from typing import Optional


class User:
    """Entidade de domínio.

    `name` é opcional: usuários criados antes do campo existir (e quem não
    informar nome no cadastro) ficam com None.
    """

    def __init__(
        self,
        id: Optional[int],
        email: str,
        hashed_password: str,
        name: Optional[str] = None,
    ):
        self.id = id
        self.email = email
        self.hashed_password = hashed_password
        self.name = name
