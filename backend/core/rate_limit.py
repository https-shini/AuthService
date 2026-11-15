"""Rate limiting do login (POST /token), em memória.

Coerente com o resto da aplicação (um processo, estado em memória) e sem
dependência nova. Três contadores, todos com janela deslizante:

  1. por IP — qualquer tentativa. Freia quem varre muitas contas.
  2. por IP + conta — falhas. Bloqueia o ataque de força bruta clássico.
  3. por conta — falhas vindas de qualquer IP. Freia ataques distribuídos.

A conta é a forma normalizada do e-mail digitado, então trocar maiúsculas
não gera um contador novo. O IP vem de `get_client_ip`, que só confia em
X-Forwarded-For quando há proxies configurados (TRUSTED_PROXY_HOPS).

Compromisso conhecido: o contador por conta permite que alguém, errando de
propósito, bloqueie temporariamente o login de uma conta alheia. O limite
dele é alto (20 falhas em 15 min) para reduzir esse risco.

Estado em memória: zera ao reiniciar e não é compartilhado entre réplicas.
"""

import threading
import time
from collections import deque
from dataclasses import dataclass
from typing import Callable, Deque, Dict, Optional

MAX_TRACKED_KEYS = 50_000


@dataclass(frozen=True)
class LoginLimits:
    ip_max_attempts: int
    ip_window: int
    account_ip_max_failures: int
    account_max_failures: int
    failure_window: int
    lockout: int


class LoginRateLimiter:
    def __init__(self, limits: LoginLimits, clock: Callable[[], float] = time.monotonic):
        self.limits = limits
        self._clock = clock
        self._lock = threading.Lock()
        self._attempts_by_ip: Dict[str, Deque[float]] = {}
        self._failures: Dict[str, Deque[float]] = {}
        self._locked_until: Dict[str, float] = {}

    # Chaves ----------------------------------------------------------------
    @staticmethod
    def _pair_key(ip: str, account: str) -> str:
        return f"ip+acct:{ip}|{account}"

    @staticmethod
    def _account_key(account: str) -> str:
        return f"acct:{account}"

    # Utilitários -----------------------------------------------------------
    @staticmethod
    def _trim(events: Deque[float], horizon: float) -> None:
        while events and events[0] <= horizon:
            events.popleft()

    def _prune(self, now: float) -> None:
        """Remove estado vencido para a memória não crescer sem limite."""
        for store, window in ((self._attempts_by_ip, self.limits.ip_window), (self._failures, self.limits.failure_window)):
            for key in [k for k, events in store.items() if not events or events[-1] <= now - window]:
                del store[key]
        for key in [k for k, until in self._locked_until.items() if until <= now]:
            del self._locked_until[key]

    def _maybe_prune(self, now: float) -> None:
        total = len(self._attempts_by_ip) + len(self._failures) + len(self._locked_until)
        if total > MAX_TRACKED_KEYS:
            self._prune(now)

    # API -------------------------------------------------------------------
    def retry_after(self, ip: str, account: str) -> Optional[int]:
        """Segundos até poder tentar de novo, ou None se a tentativa é permitida.

        É consultado ANTES de verificar a senha: durante o bloqueio nem a
        senha correta é testada, então o bloqueio não vira oráculo.
        """
        now = self._clock()
        with self._lock:
            waits = []
            for key in (self._pair_key(ip, account), self._account_key(account)):
                until = self._locked_until.get(key)
                if until is not None and until > now:
                    waits.append(until - now)
            attempts = self._attempts_by_ip.get(ip)
            if attempts is not None:
                self._trim(attempts, now - self.limits.ip_window)
                if len(attempts) >= self.limits.ip_max_attempts:
                    waits.append(attempts[0] + self.limits.ip_window - now)
            if not waits:
                return None
            return max(1, int(max(waits) + 0.999))

    def record_attempt(self, ip: str) -> None:
        now = self._clock()
        with self._lock:
            self._maybe_prune(now)
            self._attempts_by_ip.setdefault(ip, deque()).append(now)

    def record_failure(self, ip: str, account: str) -> None:
        now = self._clock()
        horizon = now - self.limits.failure_window
        thresholds = (
            (self._pair_key(ip, account), self.limits.account_ip_max_failures),
            (self._account_key(account), self.limits.account_max_failures),
        )
        with self._lock:
            for key, threshold in thresholds:
                events = self._failures.setdefault(key, deque())
                events.append(now)
                self._trim(events, horizon)
                if len(events) >= threshold:
                    self._locked_until[key] = now + self.limits.lockout
                    events.clear()

    def record_success(self, ip: str, account: str) -> None:
        """Login certo zera as falhas daquele IP para a conta.

        O contador global da conta NÃO é zerado: senão o login legítimo do
        dono apagaria o histórico de um ataque distribuído em andamento.
        """
        with self._lock:
            self._failures.pop(self._pair_key(ip, account), None)

    def reset(self) -> None:
        with self._lock:
            self._attempts_by_ip.clear()
            self._failures.clear()
            self._locked_until.clear()
