"""Representa uma transação financeira armazenada na pilha de histórico da conta."""

from datetime import datetime

from formatacao import formatar_reais, formatar_valor_moeda


class Transacao:
    def __init__(self, tipo, valor, quando=None, **detalhes):
        self.tipo = tipo
        self.valor = valor
        # Momento em que a operação ocorreu, em ISO 8601
        self.quando = quando or datetime.now().isoformat(timespec="seconds")
        self.detalhes = detalhes

    def data_hora(self):
        """Data e hora no formato brasileiro curto: 19/09/26 15:30"""
        if not self.quando:
            return "--/--/-- --:--"
        return datetime.fromisoformat(self.quando).strftime("%d/%m/%y %H:%M")

    def data(self):
        """Apenas a data: 19/09/2026"""
        if not self.quando:
            return "--/--/----"
        return datetime.fromisoformat(self.quando).strftime("%d/%m/%Y")

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
        return {"tipo": self.tipo, "valor": self.valor,
                "quando": self.quando, "detalhes": self.detalhes}

    @classmethod
    def de_dicionario(cls, dados):
        """Recria uma transação a partir de um dicionário lido do arquivo."""
        transacao = cls(dados["tipo"], dados["valor"], **dados.get("detalhes", {}))
        # Arquivo de versão anterior não tem data: marca como desconhecida em
        # vez de atribuir a data da leitura, que seria uma informação falsa.
        transacao.quando = dados.get("quando", "")
        return transacao

    def __repr__(self):
        return f"Transacao({self.tipo}, {self.valor})"
