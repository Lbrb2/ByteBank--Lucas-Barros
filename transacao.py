"""Representa uma transação financeira armazenada na pilha de histórico da conta."""

from formatacao import formatar_reais, formatar_valor_moeda


class Transacao:
    def __init__(self, tipo, valor, **detalhes):
        self.tipo = tipo
        self.valor = valor
        self.detalhes = detalhes

    def obter(self, chave):
        return self.detalhes.get(chave)

    def descricao(self):
        if self.tipo == "CAMBIO":
            origem = formatar_valor_moeda(self.obter("moeda_origem"), self.obter("quantidade_origem"))
            destino = formatar_valor_moeda(self.obter("moeda_destino"), self.obter("quantidade_destino"))
            return f"{origem} -> {destino}"

        valor_formatado = formatar_reais(self.valor)
        descricao_extra = self.obter("descricao")
        if descricao_extra:
            return f"{descricao_extra} - {valor_formatado}"
        parcelas = self.obter("parcelas")
        if parcelas:
            return f"{valor_formatado} em {parcelas}x"
        return valor_formatado

    def para_dicionario(self):
        """Converte a transação em um dicionário, para gravação em arquivo."""
        return {"tipo": self.tipo, "valor": self.valor, "detalhes": self.detalhes}

    @classmethod
    def de_dicionario(cls, dados):
        """Recria uma transação a partir de um dicionário lido do arquivo."""
        return cls(dados["tipo"], dados["valor"], **dados.get("detalhes", {}))

    def __repr__(self):
        return f"Transacao({self.tipo}, {self.valor})"
