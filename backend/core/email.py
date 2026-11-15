"""Política de normalização de e-mail.

Regra única, usada no cadastro e no login: o endereço inteiro (domínio E
parte local) é comparado e armazenado em minúsculas, sem espaços nas
pontas. Na prática nenhum provedor relevante diferencia maiúsculas na parte
local, e tratar `Ana@x.com` e `ana@x.com` como contas distintas só gerava
logins recusados e contas duplicadas.

Compatibilidade: usuários cadastrados antes desta regra podem ter a parte
local com maiúsculas. Eles continuam entrando — ver
`UserRepository.find_for_login`.
"""


def normalize_email(value: str) -> str:
    return value.strip().lower()
