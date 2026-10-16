"""Classe que representa o cliente: quem a pessoa é, separado do que ela tem.

A ContaCorrente guarda dinheiro; o Cliente guarda identidade e contato. Antes
desta classe existir, nome e CPF eram textos soltos dentro da conta. Separar
os dois deixa cada classe com uma única responsabilidade e permite que as
regras sobre dados pessoais (CPF imutável, e-mail válido) morem em um só lugar.
"""

DIGITOS_DO_CPF = 11
MINIMO_DIGITOS_TELEFONE = 8


class Cliente:
    # Lista fechada de atributos. Sem ela, 'objeto.atributo_novo = x' não
    # daria erro: o Python criaria um atributo solto, que a classe nunca lê.
    __slots__ = ("__cpf", "__nome", "__email", "__telefone")

    def __init__(self, nome, cpf, email="", telefone=""):
        if not Cliente.cpf_valido(cpf):
            raise ValueError(f"CPF inválido: '{cpf}'. Use 11 dígitos, "
                             f"com ou sem pontuação (ex: 123.456.789-00).")
        self.__cpf = cpf.strip()

        # As atribuições abaixo passam pelos setters, que validam o valor.
        # Assim a regra existe em um lugar só e vale também para o construtor.
        self.nome = nome
        self.email = email
        self.telefone = telefone

    # ---------------- Validações ----------------

    @staticmethod
    def somente_digitos(texto):
        return "".join(caractere for caractere in str(texto) if caractere.isdigit())

    @staticmethod
    def cpf_valido(cpf):
        """Confere o formato: 11 dígitos, aceitando pontos e traço.

        Não calcula os dígitos verificadores. As contas de demonstração usam
        CPFs como 111.111.111-11, que têm formato correto mas seriam
        recusados pelo cálculo oficial.
        """
        texto = str(cpf).strip()
        permitidos = set("0123456789.-")
        if not texto or any(caractere not in permitidos for caractere in texto):
            return False
        return len(Cliente.somente_digitos(texto)) == DIGITOS_DO_CPF

    # ---------------- Atributos blindados ----------------

    @property
    def cpf(self):
        """Somente leitura: não existe setter.

        O CPF identifica a pessoa e é a chave que liga o cliente às
        instituições do Open Banking. Trocá-lo depois de criado
        desconectaria o cliente dos próprios dados.
        """
        return self.__cpf

    @property
    def nome(self):
        return self.__nome

    @nome.setter
    def nome(self, valor):
        texto = str(valor).strip()
        if not texto:
            raise ValueError("O nome do titular não pode ficar vazio.")
        self.__nome = texto

    @property
    def email(self):
        return self.__email

    @email.setter
    def email(self, valor):
        """Opcional, mas quando informado precisa ter cara de e-mail."""
        texto = str(valor or "").strip()
        if texto and ("@" not in texto or texto.startswith("@") or texto.endswith("@")):
            raise ValueError(f"E-mail inválido: '{texto}'.")
        self.__email = texto

    @property
    def telefone(self):
        return self.__telefone

    @telefone.setter
    def telefone(self, valor):
        """Opcional; quando informado, precisa ter ao menos 8 dígitos."""
        texto = str(valor or "").strip()
        if texto and len(Cliente.somente_digitos(texto)) < MINIMO_DIGITOS_TELEFONE:
            raise ValueError(f"Telefone inválido: '{texto}'.")
        self.__telefone = texto

    # ---------------- Contatos (exercício 1) ----------------

    @property
    def contatos(self):
        """Os dados de contato reunidos. É um dicionário novo a cada leitura:
        alterá-lo não altera o cliente (para isso existem os setters)."""
        return {"email": self.__email, "telefone": self.__telefone}

    def consultar_contatos(self):
        nao_informado = "não informado"
        return (f"Contatos de {self.__nome}\n"
                f"E-mail: {self.__email or nao_informado}\n"
                f"Telefone: {self.__telefone or nao_informado}")

    # ---------------- Gravação em arquivo ----------------

    def para_dicionario(self):
        return {
            "nome": self.nome,
            "cpf": self.cpf,
            "email": self.email,
            "telefone": self.telefone,
        }

    @classmethod
    def de_dicionario(cls, dados):
        return cls(
            nome=dados["nome"],
            cpf=dados["cpf"],
            email=dados.get("email", ""),
            telefone=dados.get("telefone", ""),
        )

    def __repr__(self):
        return f"Cliente({self.nome}, {self.cpf})"
