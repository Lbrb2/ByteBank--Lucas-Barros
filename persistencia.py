"""Gravação e leitura do estado do banco em arquivo JSON.

O sistema guarda todos os dados em memória durante a execução. Este módulo
salva esse estado ao encerrar e o recupera na próxima abertura, para que
saldos, cofrinhos, extratos e pontos não se percam.
"""

import json
import os

from banco import Banco

ARQUIVO_PADRAO = "dados_bytebank.json"


def salvar(banco, caminho=ARQUIVO_PADRAO):
    """Grava o estado do banco no arquivo. Devolve (sucesso, mensagem)."""
    try:
        with open(caminho, "w", encoding="utf-8") as arquivo:
            json.dump(banco.para_dicionario(), arquivo, ensure_ascii=False, indent=2)
        return True, f"Dados salvos em '{caminho}'."
    except OSError as erro:
        return False, f"[ERRO] Não foi possível salvar os dados: {erro}"


def carregar(caminho=ARQUIVO_PADRAO):
    """Lê o banco do arquivo. Devolve (banco, mensagem) ou (None, mensagem)."""
    if not os.path.exists(caminho):
        return None, "Nenhum arquivo de dados encontrado."

    try:
        with open(caminho, "r", encoding="utf-8") as arquivo:
            dados = json.load(arquivo)
        banco = Banco.de_dicionario(dados)
        return banco, f"Dados carregados de '{caminho}' ({len(banco.contas)} conta(s))."
    except (OSError, json.JSONDecodeError, KeyError, TypeError) as erro:
        # Arquivo ausente, corrompido ou em formato antigo: o sistema segue
        # com os dados de demonstração em vez de interromper a execução.
        return None, f"[AVISO] Não foi possível ler '{caminho}': {erro}"
