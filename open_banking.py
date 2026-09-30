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
    """Uma instituição financeira que participa do Open Banking."""

    def __init__(self, codigo, nome, contas_por_cpf=None):
        self.codigo = codigo
        self.nome = nome
        # cpf -> {"saldo": float, "investimentos": float, "produto": str}
        self.contas_por_cpf = contas_por_cpf or {}

    def dados_do_cliente(self, cpf):
        return self.contas_por_cpf.get(cpf)

    def tem_cliente(self, cpf):
        return cpf in self.contas_por_cpf

    def debitar(self, cpf, valor):
        """Retira valor da conta do cliente nesta instituição (portabilidade)."""
        dados = self.contas_por_cpf.get(cpf)
        if dados is None:
            return False, "Cliente não encontrado nesta instituição."
        if valor <= 0:
            return False, "O valor deve ser positivo."
        if valor > dados["saldo"]:
            return False, f"Saldo insuficiente na instituição {self.nome}."
        dados["saldo"] -= valor
        return True, ""

    def creditar(self, cpf, valor):
        """Devolve valor à conta do cliente (usado ao estornar portabilidade)."""
        dados = self.contas_por_cpf.get(cpf)
        if dados is not None:
            dados["saldo"] += valor

    def para_dicionario(self):
        return {
            "codigo": self.codigo,
            "nome": self.nome,
            "contas_por_cpf": {cpf: dict(d) for cpf, d in self.contas_por_cpf.items()},
        }

    @classmethod
    def de_dicionario(cls, dados):
        return cls(dados["codigo"], dados["nome"],
                   {cpf: dict(d) for cpf, d in dados.get("contas_por_cpf", {}).items()})


class Consentimento:
    """Autorização dada pelo cliente para compartilhar dados com uma instituição."""

    def __init__(self, codigo_instituicao, escopos, criado_em=None,
                 valida_ate=None, ativo=True, revogado_em=None):
        self.codigo_instituicao = codigo_instituicao
        self.escopos = list(escopos)
        self.criado_em = criado_em or datetime.now().isoformat(timespec="seconds")
        if valida_ate is None:
            validade = datetime.fromisoformat(self.criado_em) + timedelta(days=VALIDADE_PADRAO_DIAS)
            valida_ate = validade.isoformat(timespec="seconds")
        self.valida_ate = valida_ate
        self.ativo = ativo
        self.revogado_em = revogado_em

    def expirado(self, agora=None):
        agora = agora or datetime.now()
        return agora > datetime.fromisoformat(self.valida_ate)

    def esta_valido(self, agora=None):
        return self.ativo and not self.expirado(agora)

    def cobre(self, escopo):
        return escopo in self.escopos

    def revogar(self):
        self.ativo = False
        self.revogado_em = datetime.now().isoformat(timespec="seconds")

    def situacao(self):
        if not self.ativo:
            return "REVOGADO"
        if self.expirado():
            return "EXPIRADO"
        return "ATIVO"

    def para_dicionario(self):
        return {
            "codigo_instituicao": self.codigo_instituicao,
            "escopos": list(self.escopos),
            "criado_em": self.criado_em,
            "valida_ate": self.valida_ate,
            "ativo": self.ativo,
            "revogado_em": self.revogado_em,
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

    def __init__(self):
        self.instituicoes = {}

    def adicionar(self, instituicao):
        self.instituicoes[instituicao.codigo] = instituicao
        return instituicao

    def buscar(self, codigo):
        return self.instituicoes.get(codigo)

    def listar(self):
        return list(self.instituicoes.values())

    def para_dicionario(self):
        return {c: i.para_dicionario() for c, i in self.instituicoes.items()}

    @classmethod
    def de_dicionario(cls, dados):
        diretorio = cls()
        for info in (dados or {}).values():
            diretorio.adicionar(InstituicaoParceira.de_dicionario(info))
        return diretorio
