from typing import Dict, List, Optional

from backend.core.email import normalize_email
from backend.models.user import User


class UserRepository:
    """Armazenamento em memória, com índice pela forma normalizada do e-mail.

    Novos usuários já chegam com o e-mail normalizado (minúsculas). O índice
    também cobre usuários antigos, gravados com maiúsculas na parte local,
    para que a normalização não os deixe de fora.
    """

    def __init__(self):
        self.users: Dict[int, User] = {}
        self.next_id = 1
        self._ids_by_normalized_email: Dict[str, List[int]] = {}

    def save(self, user: User) -> User:
        if user.id is None:
            user.id = self.next_id
            self.next_id += 1
        else:
            self._unindex(user.id)
        self.users[user.id] = user
        self._ids_by_normalized_email.setdefault(normalize_email(user.email), []).append(user.id)
        return user

    def _unindex(self, user_id: int) -> None:
        previous = self.users.get(user_id)
        if previous is None:
            return
        ids = self._ids_by_normalized_email.get(normalize_email(previous.email), [])
        if user_id in ids:
            ids.remove(user_id)

    def get_by_email(self, email: str) -> Optional[User]:
        """Busca EXATA (o `sub` dos tokens guarda o e-mail como está salvo)."""
        for user_id in self._ids_by_normalized_email.get(normalize_email(email), []):
            user = self.users[user_id]
            if user.email == email:
                return user
        return None

    def find_by_normalized_email(self, email: str) -> List[User]:
        return [self.users[i] for i in self._ids_by_normalized_email.get(normalize_email(email), [])]

    def find_for_login(self, email: str) -> Optional[User]:
        """Usuário para o e-mail digitado no login.

        1. igualdade exata com o texto digitado (compatível com contas
           antigas, inclusive se duas delas só diferirem em maiúsculas);
        2. igualdade exata com a forma normalizada (contas novas);
        3. uma única conta com a mesma forma normalizada (conta antiga
           digitada com outra combinação de maiúsculas).
        Se houver mais de uma candidata no passo 3, a escolha seria um
        palpite: retorna None (login recusado, sem revelar o motivo).
        """
        typed = email.strip()
        exact = self.get_by_email(typed) or self.get_by_email(normalize_email(typed))
        if exact is not None:
            return exact
        candidates = self.find_by_normalized_email(typed)
        return candidates[0] if len(candidates) == 1 else None

    def get_by_id(self, user_id: int) -> Optional[User]:
        return self.users.get(user_id)

    def exists_by_email(self, email: str) -> bool:
        """Verdadeiro se já existe conta com o mesmo e-mail, ignorando maiúsculas."""
        return bool(self._ids_by_normalized_email.get(normalize_email(email)))

    def get_all(self) -> List[User]:
        return list(self.users.values())

    def clear(self) -> None:
        self.users.clear()
        self._ids_by_normalized_email.clear()
        self.next_id = 1
