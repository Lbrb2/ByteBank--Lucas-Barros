"""Representa uma transação financeira armazenada na pilha de histórico da conta.

A transação é IMUTÁVEL: depois de criada, nada nela muda. Todos os atributos
são privados e só têm leitura. Um extrato cujas linhas pudessem ser editadas
não serviria de registro — e o estorno usa o valor gravado na transação para
devolver o dinheiro, então alterar 'valor' depois seria uma forma de fabricar
saldo.
"""

from datetime import datetime

from formatacao import formatar_reais, formatar_valor_moeda


class Transacao:
    # Lista fechada de atributos. Sem ela, 'objeto.atributo_novo = x' não
    # daria erro: o Python criaria um atributo solto, que a classe nunca lê.
    __slots__ = ("__tipo", "__valor", "__quando", "__detalhes")

    def __init__(self, tipo, valor, quando=None, **detalhes):
        self.__tipo = tipo
        self.__valor = valor
        # Momento em que a operação ocorreu, em ISO 8601
        self.__quando = quando or datetime.now().isoformat(timespec="seconds")
        self.__detalhes = dict(detalhes)

    @property
    def tipo(self):
        return self.__tipo

    @property
    def valor(self):
        return self.__valor

    @property
    def quando(self):
        return self.__quando

    @property
    def detalhes(self):
        """Cópia: alterar o dicionário recebido não altera a transação."""
        return dict(self.__detalhes)

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
        return self.__detalhes.get(chave)

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
                "quando": self.quando, "detalhes": dict(self.__detalhes)}

    @classmethod
    def de_dicionario(cls, dados):
        """Recria uma transação a partir de um dicionário lido do arquivo."""
        transacao = cls(dados["tipo"], dados["valor"], **dados.get("detalhes", {}))
        # Arquivo de versão anterior não tem data: marca como desconhecida em
        # vez de atribuir a data da leitura, que seria uma informação falsa.
        transacao.__quando = dados.get("quando", "")
        return transacao

    def __repr__(self):
        return f"Transacao({self.tipo}, {self.valor})"
