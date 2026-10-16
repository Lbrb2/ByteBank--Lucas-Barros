"""Classe que representa o cartão de crédito de uma conta.

Exercício 3 da Aula 8 — Classe Cartão de Crédito:

    atributos: nome, numero, validade, CVV, limite, data_pagamento, saldo, outros
    métodos:   consultar_limite(), pagar(), parcelar_saldo(), consultar_saldo()

Termos usados aqui:

    saldo           o que o cliente DEVE no cartão (a fatura em aberto)
    limite          o máximo que o saldo pode alcançar
    pagar()         paga uma compra COM o cartão: o saldo devedor aumenta
    data_pagamento  dia do mês em que a fatura vence

Como nas demais classes do ByteBank, todos os atributos são privados, a
leitura é feita por @property sem setter e o CVV é guardado apenas como hash,
do mesmo jeito que o PIN da conta.

O cartão pertence a uma ContaCorrente, que o guarda e nunca o entrega para
fora. O motivo: métodos como receber_pagamento() abatem a fatura, e só podem
ser chamados pela conta, depois de ela debitar o dinheiro do saldo. Se o
objeto fosse entregue, alguém poderia quitar a fatura sem pagar nada.
"""

import secrets
from datetime import date

import seguranca
from formatacao import formatar_reais

TAXA_JUROS_PARCELAMENTO_MENSAL = 0.04   # 4% ao mês
MINIMO_PARCELAS = 2
MAXIMO_PARCELAS = 12
ANOS_DE_VALIDADE = 5
DIA_PAGAMENTO_PADRAO = 10
# Dias 29, 30 e 31 não existem em todos os meses
MAIOR_DIA_DE_PAGAMENTO = 28
DIGITOS_DO_NUMERO = 16
DIGITOS_DO_CVV = 3
PREFIXO_DO_NUMERO = "5"


class CartaoDeCredito:
    # Lista fechada de atributos. Sem ela, 'objeto.atributo_novo = x' não
    # daria erro: o Python criaria um atributo solto, que a classe nunca lê.
    __slots__ = ("__nome", "__numero", "__validade", "__salt_cvv", "__hash_cvv",
                 "__limite", "__data_pagamento", "__saldo", "__total_pago",
                 "__parcelas", "__valor_parcela", "__plano_quitado")

    def __init__(self, nome, limite, data_pagamento=DIA_PAGAMENTO_PADRAO,
                 numero=None, validade=None, cvv=None):
        if limite < 0:
            raise ValueError("O limite do cartão não pode ser negativo.")
        if not 1 <= data_pagamento <= MAIOR_DIA_DE_PAGAMENTO:
            raise ValueError(f"O dia de pagamento deve estar entre 1 e "
                             f"{MAIOR_DIA_DE_PAGAMENTO}.")

        numero = numero or CartaoDeCredito.gerar_numero()
        if not CartaoDeCredito.numero_valido(numero):
            raise ValueError(f"Número de cartão inválido: '{numero}'.")
        cvv = cvv or "".join(secrets.choice("0123456789") for _ in range(DIGITOS_DO_CVV))
        if len(cvv) != DIGITOS_DO_CVV or not cvv.isdigit():
            raise ValueError(f"O CVV deve ter {DIGITOS_DO_CVV} dígitos.")

        # ---- atributos pedidos no exercício ----
        self.__nome = str(nome).strip().upper()   # nome impresso no cartão
        self.__numero = numero
        self.__validade = validade or CartaoDeCredito.validade_padrao()   # "MM/AA"
        self.__salt_cvv = seguranca.gerar_salt()
        self.__hash_cvv = seguranca.calcular_hash(cvv, self.__salt_cvv)
        self.__limite = float(limite)
        self.__data_pagamento = data_pagamento    # dia do mês
        self.__saldo = 0.0                        # quanto se deve no cartão

        # ---- "outros" ----
        # Total já pago na fatura. Serve de trava para o estorno de um
        # pagamento: não dá para desfazer um pagamento que não aconteceu.
        self.__total_pago = 0.0
        # Plano de parcelamento da fatura (0 = sem parcelamento)
        self.__parcelas = 0
        self.__valor_parcela = 0.0
        # Plano encerrado pelo último pagamento, caso esse pagamento seja
        # estornado: (parcelas, valor da parcela, valor pago, total pago)
        self.__plano_quitado = None

    # ---------------- Número do cartão ----------------

    @staticmethod
    def digito_luhn(corpo):
        """Calcula o dígito verificador pelo algoritmo de Luhn.

        É o mesmo cálculo usado pelos cartões reais: dobra um dígito sim,
        outro não, da direita para a esquerda, e soma tudo. Ele detecta erros
        de digitação, como um dígito trocado ou dois dígitos invertidos.
        """
        soma = 0
        for posicao, caractere in enumerate(reversed(corpo)):
            digito = int(caractere)
            if posicao % 2 == 0:    # estas posições são dobradas
                digito *= 2
                if digito > 9:
                    digito -= 9
            soma += digito
        return (10 - soma % 10) % 10

    @staticmethod
    def gerar_numero():
        """Gera um número de 16 dígitos com dígito verificador válido."""
        quantidade = DIGITOS_DO_NUMERO - len(PREFIXO_DO_NUMERO) - 1
        corpo = PREFIXO_DO_NUMERO + "".join(secrets.choice("0123456789")
                                             for _ in range(quantidade))
        return corpo + str(CartaoDeCredito.digito_luhn(corpo))

    @staticmethod
    def numero_valido(numero):
        numero = str(numero)
        return (len(numero) == DIGITOS_DO_NUMERO and numero.isdigit()
                and CartaoDeCredito.digito_luhn(numero[:-1]) == int(numero[-1]))

    @staticmethod
    def validade_padrao(hoje=None):
        hoje = hoje or date.today()
        return f"{hoje.month:02d}/{(hoje.year + ANOS_DE_VALIDADE) % 100:02d}"

    # ---------------- Atributos blindados (somente leitura) ----------------

    @property
    def nome(self):
        return self.__nome

    @property
    def numero(self):
        return self.__numero

    @property
    def numero_mascarado(self):
        """Só os 4 últimos dígitos aparecem, como numa fatura."""
        return f"**** **** **** {self.__numero[-4:]}"

    @property
    def validade(self):
        return self.__validade

    @property
    def limite(self):
        return self.__limite

    @property
    def data_pagamento(self):
        return self.__data_pagamento

    @property
    def saldo(self):
        return self.__saldo

    @property
    def limite_disponivel(self):
        return self.__limite - self.__saldo

    @property
    def parcelas(self):
        return self.__parcelas

    @property
    def valor_parcela(self):
        return self.__valor_parcela

    # O CVV não tem property: nem a conta, nem a interface conseguem lê-lo.
    def confere_cvv(self, cvv):
        return seguranca.conferir(str(cvv), self.__salt_cvv, self.__hash_cvv)

    def expirado(self, hoje=None):
        """O cartão vale até o último dia do mês da validade."""
        hoje = hoje or date.today()
        mes, ano = self.__validade.split("/")
        return (hoje.year % 100, hoje.month) > (int(ano), int(mes))

    def proximo_vencimento(self, hoje=None):
        hoje = hoje or date.today()
        if hoje.day <= self.__data_pagamento:
            return date(hoje.year, hoje.month, self.__data_pagamento)
        if hoje.month == 12:
            return date(hoje.year + 1, 1, self.__data_pagamento)
        return date(hoje.year, hoje.month + 1, self.__data_pagamento)

    # ---------------- Métodos pedidos no exercício ----------------

    def consultar_limite(self):
        return (f"Limite total: {formatar_reais(self.__limite)}\n"
                f"Limite utilizado: {formatar_reais(self.__saldo)}\n"
                f"Limite disponível: {formatar_reais(self.limite_disponivel)}")

    def consultar_saldo(self):
        vencimento = self.proximo_vencimento().strftime("%d/%m/%Y")
        linhas = [f"Fatura atual: {formatar_reais(self.__saldo)}",
                  f"Vencimento: todo dia {self.__data_pagamento} (próximo: {vencimento})"]
        if self.__parcelas:
            linhas.append(f"Parcelamento: {self.__parcelas}x de "
                          f"{formatar_reais(self.__valor_parcela)}")
        return "\n".join(linhas)

    def pagar(self, valor):
        """Paga uma compra com o cartão: o valor entra no saldo devedor.

        Devolve (sucesso, mensagem).
        """
        if valor <= 0:
            return False, "[RECUSADO] O valor da compra deve ser positivo."
        if self.expirado():
            return False, f"[RECUSADO] Cartão vencido em {self.__validade}."
        if valor > self.limite_disponivel:
            return False, (f"[RECUSADO] Limite insuficiente no cartão de crédito. "
                           f"Limite disponível: {formatar_reais(self.limite_disponivel)}")
        self.__saldo += valor
        return True, (f"[OK] Compra de {formatar_reais(valor)} aprovada no cartão "
                      f"{self.numero_mascarado}.")

    @staticmethod
    def calcular_parcelamento(valor, parcelas):
        """Devolve (total, valor da parcela) com juros compostos mensais."""
        total = valor * (1 + TAXA_JUROS_PARCELAMENTO_MENSAL) ** parcelas
        return total, total / parcelas

    def simular_parcelamento(self, parcelas):
        sucesso, erro = self.__validar_parcelamento(parcelas)
        if not sucesso:
            return False, erro
        total, valor_parcela = CartaoDeCredito.calcular_parcelamento(self.__saldo, parcelas)
        return True, (f"Simulação de parcelamento da fatura\n"
                      f"Fatura atual: {formatar_reais(self.__saldo)}\n"
                      f"Parcelas: {parcelas}x de {formatar_reais(valor_parcela)}\n"
                      f"Juros: {TAXA_JUROS_PARCELAMENTO_MENSAL * 100:.2f}% ao mês\n"
                      f"Total a pagar: {formatar_reais(total)}")

    def parcelar_saldo(self, parcelas):
        """Divide a fatura atual em parcelas, com juros.

        O saldo devedor passa a ser o total com juros, e o plano (quantidade
        e valor das parcelas) fica registrado até a fatura ser quitada.
        Devolve (sucesso, mensagem).
        """
        sucesso, erro = self.__validar_parcelamento(parcelas)
        if not sucesso:
            return False, erro
        valor_original = self.__saldo
        total, valor_parcela = CartaoDeCredito.calcular_parcelamento(valor_original, parcelas)
        self.__saldo = total
        self.__parcelas = parcelas
        self.__valor_parcela = valor_parcela
        return True, (f"[OK] Fatura de {formatar_reais(valor_original)} parcelada em "
                      f"{parcelas}x de {formatar_reais(valor_parcela)}.\n"
                      f"Total a pagar: {formatar_reais(total)}")

    def __validar_parcelamento(self, parcelas):
        if self.__saldo <= 0:
            return False, "Não há fatura em aberto para parcelar."
        if self.__parcelas:
            return False, ("[RECUSADO] A fatura já está parcelada. "
                           "Quite o parcelamento atual antes de fazer outro.")
        if not MINIMO_PARCELAS <= parcelas <= MAXIMO_PARCELAS:
            return False, (f"[RECUSADO] O parcelamento deve ter de {MINIMO_PARCELAS} "
                           f"a {MAXIMO_PARCELAS} parcelas.")
        if CartaoDeCredito.calcular_parcelamento(self.__saldo, parcelas)[0] > self.__limite:
            return False, ("[RECUSADO] Com os juros, o total parcelado ultrapassaria "
                           "o limite do cartão.")
        return True, ""

    # ---------------- Usados pela ContaCorrente ----------------

    def receber_pagamento(self, valor):
        """Abate um pagamento da fatura. Quem debita o dinheiro é a conta."""
        if valor <= 0:
            return False, "[RECUSADO] O valor do pagamento deve ser positivo."
        if self.__saldo == 0:
            return False, "Não há fatura pendente para pagar nesta conta."
        if valor > self.__saldo + 0.005:
            return False, (f"[RECUSADO] O valor informado é maior que a fatura atual. "
                           f"Fatura atual: {formatar_reais(self.__saldo)}")
        self.__saldo = max(self.__saldo - valor, 0.0)
        self.__total_pago += valor
        self.__plano_quitado = None
        if self.__saldo == 0 and self.__parcelas:
            # Parcelamento quitado. O plano é guardado para o caso de este
            # pagamento ser estornado: aí a dívida volta, e o plano também.
            self.__plano_quitado = (self.__parcelas, self.__valor_parcela,
                                    valor, self.__total_pago)
            self.__parcelas, self.__valor_parcela = 0, 0.0
        return True, ""

    def estornar_compra(self, valor):
        """Desfaz uma compra: o valor sai do saldo devedor."""
        if valor <= 0 or valor > self.__saldo + 0.005:
            return False, "[RECUSADO] Estorno maior que a fatura atual."
        self.__saldo = max(self.__saldo - valor, 0.0)
        return True, ""

    def estornar_pagamento(self, valor):
        """Desfaz um pagamento da fatura: o valor volta a ser devido.

        Só aceita até o total efetivamente pago, para não ser possível
        "desfazer" um pagamento que nunca existiu.
        """
        if valor <= 0 or valor > self.__total_pago + 0.005:
            return False, "[RECUSADO] Não há pagamento desse valor para estornar."
        plano = self.__plano_quitado
        if (plano is not None and abs(plano[2] - valor) < 0.005
                and abs(plano[3] - self.__total_pago) < 0.005):
            # É o pagamento que quitou o parcelamento: o plano volta junto
            self.__parcelas, self.__valor_parcela = plano[0], plano[1]
        self.__plano_quitado = None
        self.__saldo += valor
        self.__total_pago -= valor
        return True, ""

    # ---------------- Gravação em arquivo ----------------

    def para_dicionario(self):
        return {
            "nome": self.__nome,
            "numero": self.__numero,
            "validade": self.__validade,
            "salt_cvv": self.__salt_cvv,
            "hash_cvv": self.__hash_cvv,
            "limite": self.__limite,
            "data_pagamento": self.__data_pagamento,
            "saldo": self.__saldo,
            "total_pago": self.__total_pago,
            "parcelas": self.__parcelas,
            "valor_parcela": self.__valor_parcela,
            "plano_quitado": (list(self.__plano_quitado)
                              if self.__plano_quitado else None),
        }

    @classmethod
    def de_dicionario(cls, dados):
        cartao = cls(dados["nome"], dados.get("limite", 0.0),
                     dados.get("data_pagamento", DIA_PAGAMENTO_PADRAO),
                     numero=dados.get("numero"), validade=dados.get("validade"))
        if dados.get("salt_cvv") and dados.get("hash_cvv"):
            cartao.__salt_cvv = dados["salt_cvv"]
            cartao.__hash_cvv = dados["hash_cvv"]
        saldo = dados.get("saldo", 0.0)
        if saldo < 0:
            raise ValueError("O saldo devedor do cartão não pode ser negativo.")
        cartao.__saldo = saldo
        cartao.__total_pago = dados.get("total_pago", 0.0)
        cartao.__parcelas = dados.get("parcelas", 0)
        cartao.__valor_parcela = dados.get("valor_parcela", 0.0)
        plano = dados.get("plano_quitado")
        cartao.__plano_quitado = tuple(plano) if plano else None
        return cartao

    def __repr__(self):
        return f"CartaoDeCredito({self.numero_mascarado}, {self.__nome})"
