"""Funções de formatação financeira no padrão brasileiro e de layout dos painéis."""

LARGURA_PAINEL = 62


def linha_separadora(caractere="="):
    """Linha horizontal com a largura padrão dos painéis."""
    return caractere * LARGURA_PAINEL


def linha_titulo(texto):
    """Título centralizado entre sinais de igual, na largura padrão.

    Exemplo: '====== Extrato de Amanda Silva (Conta 0001) ======'
    """
    return f" {texto} ".center(LARGURA_PAINEL, "=")


def formatar_numero(valor):
    """Formata um número com separador de milhar e vírgula decimal: 1250.5 -> 1.250,50"""
    texto = f"{valor:,.2f}"
    return texto.replace(",", "X").replace(".", ",").replace("X", ".")


def formatar_reais(valor):
    """Formata um valor em reais: 1250.5 -> R$ 1.250,50"""
    return f"R$ {formatar_numero(valor)}"


def formatar_valor_moeda(moeda, valor):
    """Formata um valor na moeda indicada. O real usa o símbolo R$."""
    if moeda == "real":
        return formatar_reais(valor)
    return f"{formatar_numero(valor)} {moeda}"
