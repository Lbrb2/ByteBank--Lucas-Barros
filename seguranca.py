"""Proteção do PIN de acesso.

O PIN nunca é guardado em texto: o que fica salvo é o resultado de uma função
de hash, que transforma o PIN em uma sequência da qual não se consegue voltar
ao valor original. Na autenticação, o PIN digitado passa pela mesma função e
os resultados são comparados.

Cada conta tem um "salt" próprio — um valor aleatório misturado ao PIN antes
do hash. Ele garante que duas contas com o mesmo PIN tenham hashes diferentes
e impede o uso de tabelas de hashes pré-calculados.
"""

import hashlib
import secrets

ALGORITMO = "sha256"
ITERACOES = 100_000  # repetições do hash: tornam a força bruta mais lenta
TAMANHO_SALT = 16


def gerar_salt():
    """Gera um salt aleatório, em hexadecimal."""
    return secrets.token_hex(TAMANHO_SALT)


def calcular_hash(pin, salt):
    """Calcula o hash do PIN combinado ao salt."""
    return hashlib.pbkdf2_hmac(
        ALGORITMO,
        pin.encode("utf-8"),
        bytes.fromhex(salt),
        ITERACOES,
    ).hex()


def conferir(pin, salt, hash_guardado):
    """Confere se o PIN corresponde ao hash guardado.

    Usa compare_digest para que a comparação leve o mesmo tempo em qualquer
    caso, sem revelar quantos caracteres iniciais estavam corretos.
    """
    return secrets.compare_digest(calcular_hash(pin, salt), hash_guardado)
