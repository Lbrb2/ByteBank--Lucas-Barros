"""Open Banking: compartilhamento de dados entre instituições.

O modelo segue a lógica do Open Finance brasileiro: nenhuma informação é
compartilhada sem um consentimento explícito do cliente, que tem escopo
definido, prazo de validade e pode ser revogado a qualquer momento.

As instituições parceiras são simuladas em memória — no mundo real seriam
consultas a APIs externas.
"""

from datetime import datetime, timedelta

# Escopos que o cliente pode autorizar
ESCOPOS = {
    "saldo": "Saldos e contas",
    "transacoes": "Histórico de transações",
    "investimentos": "Produtos de investimento",
}

VALIDADE_PADRAO_DIAS = 365  # o Open Finance usa consentimentos de até 12 meses


class InstituicaoParceira:
    """Uma instituição financeira que participa do Open Banking.

    Os dados dos clientes são privados. Saídas de dinheiro só acontecem por
    debitar() e devoluções só por devolver(), que aceita devolver apenas o
    que de fato foi retirado antes. Sem essa trava, devolver um valor
    qualquer criaria saldo do nada na parceira, e uma portabilidade em
    seguida traria esse dinheiro inventado para o ByteBank.
    """

    # Lista fechada de atributos. Sem ela, 'objeto.atributo_novo = x' não
    # daria erro: o Python criaria um atributo solto, que a classe nunca lê.
    __slots__ = ("__codigo", "__nome", "__contas_por_cpf", "__portado_por_cpf")

    def __init__(self, codigo, nome, contas_por_cpf=None, portado_por_cpf=None):
        self.__codigo = codigo
        self.__nome = nome
        # cpf -> {"saldo": float, "investimentos": float}
        self.__contas_por_cpf = {cpf: dict(d) for cpf, d in (contas_por_cpf or {}).items()}
        # cpf -> total já portado para o ByteBank e ainda não devolvido
        self.__portado_por_cpf = dict(portado_por_cpf or {})

    @property
    def codigo(self):
        return self.__codigo

    @property
    def nome(self):
        return self.__nome

    def dados_do_cliente(self, cpf):
        """Cópia dos dados: quem consulta não consegue alterá-los."""
        dados = self.__contas_por_cpf.get(cpf)
        return dict(dados) if dados is not None else None

    def tem_cliente(self, cpf):
        return cpf in self.__contas_por_cpf

    def debitar(self, cpf, valor):
        """Retira valor da conta do cliente nesta instituição (portabilidade)."""
        dados = self.__contas_por_cpf.get(cpf)
        if dados is None:
            return False, "Cliente não encontrado nesta instituição."
        if valor <= 0:
            return False, "O valor deve ser positivo."
        if valor > dados["saldo"]:
            return False, f"Saldo insuficiente na instituição {self.__nome}."
        dados["saldo"] -= valor
        self.__portado_por_cpf[cpf] = self.__portado_por_cpf.get(cpf, 0.0) + valor
        return True, ""

    def devolver(self, cpf, valor):
        """Devolve à conta do cliente um valor portado antes (estorno).

        Só aceita até o total que saiu daqui e ainda não voltou.
        """
        dados = self.__contas_por_cpf.get(cpf)
        if dados is None:
            return False, "Cliente não encontrado nesta instituição."
        if valor <= 0:
            return False, "O valor deve ser positivo."
        pendente = self.__portado_por_cpf.get(cpf, 0.0)
        if valor > pendente + 0.005:
            return False, (f"{self.__nome} só pode receber de volta valores que "
                           f"saíram dela por portabilidade.")
        dados["saldo"] += valor
        self.__portado_por_cpf[cpf] = pendente - valor
        return True, ""

    def para_dicionario(self):
        return {
            "codigo": self.__codigo,
            "nome": self.__nome,
            "contas_por_cpf": {cpf: dict(d) for cpf, d in self.__contas_por_cpf.items()},
            "portado_por_cpf": dict(self.__portado_por_cpf),
        }

    @classmethod
    def de_dicionario(cls, dados):
        return cls(dados["codigo"], dados["nome"],
                   dados.get("contas_por_cpf", {}),
                   dados.get("portado_por_cpf", {}))


class Consentimento:
    """Autorização dada pelo cliente para compartilhar dados com uma instituição.

    Atributos privados e somente leitura. A única mudança possível depois de
    criado é revogar(): um consentimento revogado não pode ser reativado
    (seria preciso conceder um novo), por isso 'ativo' não tem setter.
    """

    # Lista fechada de atributos. Sem ela, 'objeto.atributo_novo = x' não
    # daria erro: o Python criaria um atributo solto, que a classe nunca lê.
    __slots__ = ("__codigo_instituicao", "__escopos", "__criado_em", "__valida_ate",
                 "__ativo", "__revogado_em")

    def __init__(self, codigo_instituicao, escopos, criado_em=None,
                 valida_ate=None, ativo=True, revogado_em=None):
        self.__codigo_instituicao = codigo_instituicao
        self.__escopos = tuple(escopos)
        self.__criado_em = criado_em or datetime.now().isoformat(timespec="seconds")
        if valida_ate is None:
            validade = datetime.fromisoformat(self.__criado_em) + timedelta(days=VALIDADE_PADRAO_DIAS)
            valida_ate = validade.isoformat(timespec="seconds")
        self.__valida_ate = valida_ate
        self.__ativo = ativo
        self.__revogado_em = revogado_em

    @property
    def codigo_instituicao(self):
        return self.__codigo_instituicao

    @property
    def escopos(self):
        """Tupla: não aceita incluir escopos depois da autorização."""
        return self.__escopos

    @property
    def criado_em(self):
        return self.__criado_em

    @property
    def valida_ate(self):
        return self.__valida_ate

    @property
    def ativo(self):
        return self.__ativo

    @property
    def revogado_em(self):
        return self.__revogado_em

    def expirado(self, agora=None):
        agora = agora or datetime.now()
        return agora > datetime.fromisoformat(self.__valida_ate)

    def esta_valido(self, agora=None):
        return self.__ativo and not self.expirado(agora)

    def cobre(self, escopo):
        return escopo in self.__escopos

    def revogar(self):
        self.__ativo = False
        self.__revogado_em = datetime.now().isoformat(timespec="seconds")

    def situacao(self):
        if not self.__ativo:
            return "REVOGADO"
        if self.expirado():
            return "EXPIRADO"
        return "ATIVO"

    def para_dicionario(self):
        return {
            "codigo_instituicao": self.__codigo_instituicao,
            "escopos": list(self.__escopos),
            "criado_em": self.__criado_em,
            "valida_ate": self.__valida_ate,
            "ativo": self.__ativo,
            "revogado_em": self.__revogado_em,
        }

    @classmethod
    def de_dicionario(cls, dados):
        return cls(
            dados["codigo_instituicao"],
            dados.get("escopos", []),
            criado_em=dados.get("criado_em"),
            valida_ate=dados.get("valida_ate"),
            ativo=dados.get("ativo", True),
            revogado_em=dados.get("revogado_em"),
        )


class Diretorio:
    """Registro das instituições participantes do Open Banking."""

    # Lista fechada de atributos. Sem ela, 'objeto.atributo_novo = x' não
    # daria erro: o Python criaria um atributo solto, que a classe nunca lê.
    __slots__ = ("__instituicoes",)

    def __init__(self):
        self.__instituicoes = {}

    def adicionar(self, instituicao):
        if not isinstance(instituicao, InstituicaoParceira):
            raise TypeError("O diretório só aceita instâncias de InstituicaoParceira.")
        self.__instituicoes[instituicao.codigo] = instituicao
        return instituicao

    def buscar(self, codigo):
        return self.__instituicoes.get(codigo)

    def listar(self):
        return list(self.__instituicoes.values())

    def para_dicionario(self):
        return {c: i.para_dicionario() for c, i in self.__instituicoes.items()}

    @classmethod
    def de_dicionario(cls, dados):
        diretorio = cls()
        for info in (dados or {}).values():
            diretorio.adicionar(InstituicaoParceira.de_dicionario(info))
        return diretorio
