"""Classe que representa uma conta corrente e suas operações individuais.

Os métodos de operação retornam uma tupla (sucesso, mensagem). A classe não
imprime nada: quem exibe as mensagens é a camada de interface.

Atributos blindados
-------------------
TODOS os atributos da conta são privados (prefixo '__'). Nenhum pode ser
alterado de fora da classe: o estado só muda pelos métodos da própria conta,
que validam cada operação. A leitura é liberada por @property sem setter:

    valores simples    devolvidos como estão (números e textos são imutáveis)
    cofrinhos          devolvidos como CÓPIA: alterar o dicionário recebido
                       não altera a conta
    historico          devolvido como TUPLA, que não aceita append nem pop
    consentimentos     devolvidos como cópia do dicionário
    pilha_refazer      sem leitura externa (uso interno do estorno)
    salt / pin_hash    sem leitura externa (o PIN não é exposto nem em hash)

Devolver a lista ou o dicionário original seria uma blindagem de fachada:
'conta.cofrinhos["Reserva"]["saldo"] = 1e9' passaria pela @property sem setter
e alteraria o dinheiro mesmo assim, porque a property entregaria a referência
ao objeto interno. A cópia corta essa ligação.

Em Python, '__saldo' dentro da classe vira '_ContaCorrente__saldo' (name
mangling). Não é uma tranca absoluta — a linguagem não tem uma —, mas impede
o acesso por engano e deixa explícito que o atributo não faz parte da
interface pública da classe.
"""

from formatacao import (formatar_reais, formatar_numero, formatar_valor_moeda,
                        linha_separadora, linha_titulo)
from transacao import Transacao
from cliente import Cliente
import seguranca
from open_banking import Consentimento
from datetime import datetime, timedelta

TAXAS_CAMBIO = {
    "dolar": 5.00,  # 1 Dólar = 5 Reais
    "euro": 6.00,   # 1 Euro = 6 Reais
    "yuan": 0.75    # 1 Yuan = 0.75 Reais
}

MOEDAS_VALIDAS = list(TAXAS_CAMBIO.keys()) + ["real"]
TAXA_JUROS_EMPRESTIMO_MENSAL = 0.02  # 2% ao mês
# O crédito pré-aprovado equivale a 3x o patrimônio do cliente
MULTIPLICADOR_CREDITO_PRE_APROVADO = 3
MAXIMO_PARCELAS_EMPRESTIMO = 24
LIMITE_MAXIMO_SAQUE_POR_OPERACAO = 2000.00

# Categorias usadas para classificar os gastos (relatório GROUP BY em memória)
CATEGORIAS_GASTO = [
    "Alimentação", "Transporte", "Moradia", "Lazer",
    "Saúde", "Educação", "Outros"
]
CATEGORIA_PADRAO = "Outros"

# Tipos de transação que entram no relatório de gastos
TIPOS_DE_GASTO = ["PAGAMENTO_BOLETO", "COMPRA_CARTAO"]

# Programa de fidelidade BytePoints
PONTOS_POR_REAL_GASTO = 1          # 1 ponto a cada R$ 1,00 gasto
PONTOS_PARA_UM_REAL = 100          # 100 pontos valem R$ 1,00 de cashback
MINIMO_PONTOS_PARA_RESGATE = 100

# Segurança de acesso
MAXIMO_TENTATIVAS_PIN = 3
TAMANHO_PIN = 4

# Cofrinhos (caixinhas de investimento) - rendimento por juros simples
TAXA_RENDIMENTO_MENSAL_PADRAO = 0.005  # 0,5% ao mês

# Operações que acumulam pontos de fidelidade
TIPOS_QUE_GERAM_PONTOS = ["SAQUE", "PIX_ENVIADO", "PAGAMENTO_BOLETO", "COMPRA_CARTAO"]

# Transações que envolvem uma segunda conta
TIPOS_PIX = ("PIX_ENVIADO", "PIX_RECEBIDO")


class ContaCorrente:
    # Lista fechada de atributos. Sem ela, 'objeto.atributo_novo = x' não
    # daria erro: o Python criaria um atributo solto, que a classe nunca lê.
    __slots__ = ("__numero", "__cliente", "__chave_pix", "__salt", "__pin_hash",
                 "__tentativas_falhas", "__bloqueada", "__saldo",
                 "__limite_cartao_credito", "__fatura_cartao_credito",
                 "__divida_emprestimo", "__saldo_dolar", "__saldo_euro",
                 "__saldo_yuan", "__cofrinhos", "__bytepoints", "__historico",
                 "__pilha_refazer", "__consentimentos")

    CAMPOS_FINANCEIROS = [
        "saldo", "fatura_cartao_credito",
        "divida_emprestimo", "saldo_dolar", "saldo_euro", "saldo_yuan",
        "bytepoints"
    ]

    def __init__(self, numero, cliente, chave_pix, saldo=0.0,
                 limite_cartao_credito=0.0, saldo_dolar=0.0, saldo_euro=0.0,
                 saldo_yuan=0.0, cofrinhos_iniciais=None, pin="0000"):
        if not isinstance(cliente, Cliente):
            raise TypeError("A conta precisa receber uma instância de Cliente.")
        if saldo < 0:
            raise ValueError("Uma conta não pode ser aberta com saldo negativo.")

        self.__numero = str(numero).strip()
        self.__cliente = cliente   # Composição: a conta guarda o objeto dono
        self.__chave_pix = chave_pix
        self.__salt = seguranca.gerar_salt()
        self.__pin_hash = seguranca.calcular_hash(pin, self.__salt)
        self.__tentativas_falhas = 0
        self.__bloqueada = False
        self.__saldo = saldo
        self.__limite_cartao_credito = limite_cartao_credito
        self.__fatura_cartao_credito = 0.0
        self.__divida_emprestimo = 0.0
        self.__saldo_dolar = saldo_dolar
        self.__saldo_euro = saldo_euro
        self.__saldo_yuan = saldo_yuan
        # Cofrinhos: subcontas nomeadas, cada uma com saldo e taxa própria
        self.__cofrinhos = {}
        for nome, (valor, taxa) in (cofrinhos_iniciais or {}).items():
            self.__cofrinhos[nome] = {"saldo": valor, "taxa_mensal": taxa}
        self.__bytepoints = 0.0  # Programa de fidelidade
        self.__historico = []      # Pilha (LIFO) de transações efetivadas
        self.__pilha_refazer = []  # Pilha (LIFO) de transações estornadas
        self.__consentimentos = {}  # codigo da instituicao -> Consentimento

    # ---------------- Pilha de transações ----------------

    def __empilhar(self, transacao):
        """Registra uma operação nova no histórico.

        Uma operação nova invalida o refazer pendente: é o mesmo
        comportamento do Ctrl+Z / Ctrl+Y de um editor de texto.
        """
        self.__historico.append(transacao)
        self.__pilha_refazer.clear()

    def proximo_para_refazer(self):
        """Consulta (sem remover) o próximo item da pilha de refazer.

        Devolve uma cópia do item: o Banco precisa saber qual transação será
        refeita (para achar a conta do PIX ou a instituição da portabilidade),
        mas não pode alterar a pilha por meio do que recebeu.
        """
        if not self.__pilha_refazer:
            return None
        return dict(self.__pilha_refazer[-1])

    def ultima_transacao(self):
        """Topo da pilha (LIFO). A transação é imutável, então pode ser
        entregue como está."""
        if not self.__historico:
            return None
        return self.__historico[-1]

    # ---------------- Atributos blindados (somente leitura) ----------------

    @property
    def numero(self):
        return self.__numero

    @property
    def cliente(self):
        return self.__cliente

    @property
    def titular(self):
        """Atalho para o nome do cliente: quem pergunta à conta o titular
        recebe a resposta do Cliente, que é quem guarda esse dado."""
        return self.__cliente.nome

    @property
    def cpf(self):
        return self.__cliente.cpf

    @property
    def saldo(self):
        """Leitura liberada; escrita só pelos métodos da própria conta."""
        return self.__saldo

    @property
    def limite_cartao_credito(self):
        return self.__limite_cartao_credito

    @property
    def bloqueada(self):
        return self.__bloqueada

    @property
    def tentativas_falhas(self):
        return self.__tentativas_falhas

    @property
    def chave_pix(self):
        """Somente leitura: o Banco garante que a chave é única no cadastro.
        Trocá-la depois, por fora, permitiria duas contas com a mesma chave."""
        return self.__chave_pix

    @property
    def fatura_cartao_credito(self):
        return self.__fatura_cartao_credito

    @property
    def divida_emprestimo(self):
        return self.__divida_emprestimo

    @property
    def saldo_dolar(self):
        return self.__saldo_dolar

    @property
    def saldo_euro(self):
        return self.__saldo_euro

    @property
    def saldo_yuan(self):
        return self.__saldo_yuan

    @property
    def bytepoints(self):
        return self.__bytepoints

    @property
    def cofrinhos(self):
        """Cópia dos cofrinhos. Cada cofrinho também é copiado, porque o
        dicionário é aninhado: copiar só o de fora deixaria os de dentro
        compartilhados com a conta."""
        return {nome: dict(info) for nome, info in self.__cofrinhos.items()}

    @property
    def historico(self):
        """Tupla: pode ser percorrida e lida, mas não recebe append nem pop.
        As transações dentro dela também são imutáveis."""
        return tuple(self.__historico)

    @property
    def consentimentos(self):
        return dict(self.__consentimentos)

    def __definir_campo_financeiro(self, campo, valor):
        """Escreve um campo financeiro a partir do nome em texto.

        O estorno e o câmbio trabalham com o nome do campo ("saldo_dolar",
        por exemplo). setattr(self, "saldo_dolar", valor) não funciona mais,
        porque 'saldo_dolar' agora é uma property sem setter. O atributo de
        verdade se chama '_ContaCorrente__saldo_dolar' (name mangling), e é
        nele que este método escreve.

        Só aceita os campos da lista CAMPOS_FINANCEIROS, para que nunca possa
        ser usado para mexer no PIN ou no bloqueio.
        """
        if campo not in ContaCorrente.CAMPOS_FINANCEIROS:
            raise ValueError(f"Campo financeiro desconhecido: {campo}")
        setattr(self, f"_ContaCorrente__{campo}", valor)

    # ---------------- Operações entre contas ----------------
    #
    # O PIX, o estorno de PIX e o refazer de PIX alteram DUAS contas, e as
    # duas precisam mudar juntas ou nenhuma muda. Em vez de a conta oferecer
    # métodos públicos como "creditar(valor)" para o Banco usar — que
    # qualquer um poderia chamar para criar dinheiro —, a própria conta de
    # origem conduz a operação inteira.
    #
    # Isso é possível porque, em Python (assim como em Java e C++), a
    # privacidade é da CLASSE, não do objeto: dentro de um método de
    # ContaCorrente, 'destino.__saldo' acessa o atributo privado de outra
    # ContaCorrente. Fora da classe, ninguém consegue.

    def enviar_pix(self, destino, valor):
        """Transfere valor desta conta para a conta destino.

        Débito, crédito, pontos e o registro nos dois extratos acontecem
        juntos. Devolve (sucesso, mensagem).
        """
        if not isinstance(destino, ContaCorrente):
            return False, "[RECUSADO] Conta de destino inválida."
        if destino.numero == self.numero:
            return False, "[RECUSADO] Não é possível transferir para a própria conta."
        if valor <= 0:
            return False, "[RECUSADO] O valor da transferência deve ser positivo."
        if valor > self.__saldo:
            return False, (f"[RECUSADO] Saldo insuficiente. "
                           f"Saldo disponível: {formatar_reais(self.__saldo)}")

        self.__saldo -= valor
        destino.__saldo += valor
        pontos = self.__acumular_pontos(valor)

        self.__empilhar(Transacao("PIX_ENVIADO", valor,
                                  conta_par=destino.numero, pontos_gerados=pontos))
        destino.__empilhar(Transacao("PIX_RECEBIDO", valor, conta_par=self.numero))

        return True, (f"[OK] PIX de {formatar_reais(valor)} enviado para "
                      f"{destino.titular} ({destino.chave_pix}).\n"
                      f"Saldo atual: {formatar_reais(self.__saldo)}\n"
                      f"+{formatar_numero(pontos)} BytePoints")

    def receber_portabilidade(self, valor, codigo_instituicao, nome_instituicao):
        """Recebe um valor trazido de outra instituição (Open Banking).

        Como um depósito, é uma entrada de dinheiro legítima e sempre fica
        registrada no extrato. Quem retira o valor da instituição de origem
        é o Banco, antes de chamar este método.
        """
        if valor <= 0:
            return False, "[RECUSADO] O valor portado deve ser positivo."
        self.__saldo += valor
        self.__empilhar(Transacao("PORTABILIDADE", valor,
                                  instituicao=codigo_instituicao,
                                  nome_instituicao=nome_instituicao))
        return True, (f"[OK] {formatar_reais(valor)} portados de {nome_instituicao}.\n"
                      f"Saldo atual: {formatar_reais(self.__saldo)}")

    def estornar_ultima(self, conta_par=None):
        """Desfaz a última transação do histórico (pilha LIFO).

        Para um PIX, 'conta_par' é a outra conta envolvida, que o Banco
        localiza; a transação correspondente nela é desfeita junto. Se o
        estorno deixasse qualquer valor negativo em qualquer das contas, as
        duas voltam ao estado anterior e nada muda.

        Devolve (sucesso, mensagem).
        """
        transacao = self.ultima_transacao()
        if transacao is None:
            return False, "Não há transações no histórico para estornar."

        espelho, indice_espelho = None, None
        if transacao.tipo in TIPOS_PIX:
            if (not isinstance(conta_par, ContaCorrente)
                    or conta_par.numero != transacao.obter("conta_par")):
                return False, ("[RECUSADO] A conta envolvida no PIX não foi encontrada. "
                               "Estorno cancelado.")
            tipo_espelho = "PIX_RECEBIDO" if transacao.tipo == "PIX_ENVIADO" else "PIX_ENVIADO"
            indice_espelho, espelho = conta_par.__encontrar_transacao_espelho(
                tipo_espelho, transacao.valor, self.numero)
            if espelho is None:
                return False, ("[RECUSADO] A transação correspondente não foi encontrada "
                               "na conta envolvida. Estorno cancelado.")
        else:
            conta_par = None   # só o PIX envolve outra conta

        pares = [(self, transacao)] if conta_par is None else [(self, transacao),
                                                                (conta_par, espelho)]
        if not ContaCorrente.__aplicar_em_conjunto(pares, sinal=-1):
            return False, "[RECUSADO] O estorno deixaria algum saldo negativo. Operação cancelada."

        self.__historico.pop()
        if conta_par is not None:
            conta_par.__historico.pop(indice_espelho)

        # Guarda o que foi desfeito para permitir refazer depois
        self.__pilha_refazer.append({
            "transacao": transacao,
            "espelho": espelho,
            "conta_par": conta_par.numero if conta_par else None,
        })

        return True, (f"[ESTORNO] Última transação desfeita: {transacao.tipo} de "
                      f"{transacao.descricao()}\n"
                      f"Saldo atual: {formatar_reais(self.__saldo)}")

    def refazer_ultima(self, conta_par=None):
        """Reaplica a última transação estornada (pilha de refazer, LIFO).

        Só refaz o que esta própria conta estornou antes: não recebe a
        transação de fora, apenas a outra conta do PIX quando for o caso.
        Devolve (sucesso, mensagem).
        """
        if not self.__pilha_refazer:
            return False, "Não há transações estornadas para refazer."

        item = self.__pilha_refazer[-1]
        transacao, espelho = item["transacao"], item["espelho"]

        if item["conta_par"] is not None:
            if (not isinstance(conta_par, ContaCorrente)
                    or conta_par.numero != item["conta_par"]):
                return False, ("[RECUSADO] A conta envolvida no PIX não foi encontrada. "
                               "Não é possível refazer.")
        else:
            conta_par = None

        pares = [(self, transacao)] if conta_par is None else [(self, transacao),
                                                                (conta_par, espelho)]
        if not ContaCorrente.__aplicar_em_conjunto(pares, sinal=+1):
            return False, "[RECUSADO] Refazer deixaria algum saldo negativo. Operação cancelada."

        self.__pilha_refazer.pop()
        # Volta ao histórico sem limpar o refazer: os demais itens estornados
        # continuam disponíveis para refazer, como no Ctrl+Y.
        self.__historico.append(transacao)
        if conta_par is not None:
            conta_par.__historico.append(espelho)

        return True, (f"[REFEITO] Transação reaplicada: {transacao.tipo} de "
                      f"{transacao.descricao()}\n"
                      f"Saldo atual: {formatar_reais(self.__saldo)}")

    @staticmethod
    def __aplicar_em_conjunto(pares, sinal):
        """Aplica (sinal=+1) ou desfaz (sinal=-1) o efeito de cada transação na
        sua conta, de forma atômica: se alguma conta ficar com valor negativo,
        todas voltam ao estado em que estavam e o método devolve False.
        """
        fotos = [(conta, conta.__snapshot()) for conta, _ in pares]
        for conta, transacao in pares:
            conta.__aplicar_efeito(transacao, sinal)

        if any(conta.__tem_valor_negativo() for conta, _ in pares):
            for conta, foto in fotos:
                conta.__restaurar(foto)
            return False
        return True

    # ---------------- Consultas ----------------

    @property
    def limite_disponivel(self):
        return self.__limite_cartao_credito - self.__fatura_cartao_credito

    def resumo_saldo(self):
        return (f"Titular: {self.titular}\n"
                f"Conta: {self.numero} | CPF: {self.cpf}\n"
                f"Saldo atual: {formatar_reais(self.__saldo)}")

    def resumo_cartao(self):
        return (f"Titular: {self.titular}\n"
                f"Conta: {self.numero}\n"
                f"Limite total: {formatar_reais(self.__limite_cartao_credito)}\n"
                f"Fatura atual: {formatar_reais(self.__fatura_cartao_credito)}\n"
                f"Limite disponível: {formatar_reais(self.limite_disponivel)}")

    def resumo_emprestimo(self):
        return (f"Titular: {self.titular}\n"
                f"Conta: {self.numero}\n"
                f"Dívida total de empréstimos: {formatar_reais(self.__divida_emprestimo)}")

    def resumo_moedas(self):
        return (f"Titular: {self.titular}\n"
                f"Conta: {self.numero}\n"
                f"Saldo em Dólar: ${formatar_numero(self.__saldo_dolar)} "
                f"({formatar_reais(self.__saldo_dolar * TAXAS_CAMBIO['dolar'])})\n"
                f"Saldo em Euro: €{formatar_numero(self.__saldo_euro)} "
                f"({formatar_reais(self.__saldo_euro * TAXAS_CAMBIO['euro'])})\n"
                f"Saldo em Yuan: ¥{formatar_numero(self.__saldo_yuan)} "
                f"({formatar_reais(self.__saldo_yuan * TAXAS_CAMBIO['yuan'])})")

    def transacoes_do_periodo(self, dias=None):
        """Transações do histórico, opcionalmente limitadas aos últimos N dias."""
        if dias is None:
            return list(self.__historico)

        limite = datetime.now() - timedelta(days=dias)
        selecionadas = []
        for transacao in self.__historico:
            if not transacao.quando:
                continue  # data desconhecida fica fora de recortes por período
            if datetime.fromisoformat(transacao.quando) >= limite:
                selecionadas.append(transacao)
        return selecionadas

    def extrato(self, dias=None):
        titulo = f"Extrato de {self.titular} (Conta {self.numero})"
        if dias:
            titulo += f" - últimos {dias} dias"
        linhas = [linha_titulo(titulo)]

        transacoes = self.transacoes_do_periodo(dias)
        if not transacoes:
            linhas.append("Nenhuma transação no período.")
        else:
            for transacao in reversed(transacoes):
                linhas.append(f"  {transacao.data_hora()}  {transacao.tipo:<22} "
                              f"{transacao.descricao()}")
            linhas.append(f"Transações exibidas: {len(transacoes)}")
        linhas.append(f"Saldo atual: {formatar_reais(self.__saldo)}")
        linhas.append(linha_separadora())
        return "\n".join(linhas)

    def gastos_por_categoria(self, dias=None):
        """Agrupa os gastos do histórico por categoria (GROUP BY em memória).

        Percorre a pilha de transações e acumula o valor de cada gasto no
        dicionário de totais, usando a categoria como chave.
        """
        totais = {}
        for transacao in self.transacoes_do_periodo(dias):
            if transacao.tipo not in TIPOS_DE_GASTO:
                continue
            categoria = transacao.obter("categoria") or CATEGORIA_PADRAO
            totais[categoria] = totais.get(categoria, 0.0) + transacao.valor
        return totais

    def relatorio_gastos(self, dias=None):
        totais = self.gastos_por_categoria(dias)

        titulo = f"Gastos por Categoria - {self.titular}"
        if dias:
            titulo += f" (últimos {dias} dias)"
        linhas = [linha_titulo(titulo)]
        if not totais:
            linhas.append("Nenhum gasto registrado até o momento.")
            linhas.append(linha_separadora())
            return "\n".join(linhas)

        total_geral = sum(totais.values())
        # Da maior para a menor despesa
        for categoria, valor in sorted(totais.items(), key=lambda item: item[1], reverse=True):
            percentual = (valor / total_geral) * 100
            barra = "#" * int(percentual / 5)
            linhas.append(f"  {categoria:<14} {formatar_reais(valor):>16}  "
                          f"{percentual:5.1f}%  {barra}")

        linhas.append(f"  {'TOTAL':<14} {formatar_reais(total_geral):>16}")
        linhas.append(linha_separadora())
        return "\n".join(linhas)

    def __acumular_pontos(self, valor_gasto):
        """Credita pontos proporcionais ao valor gasto e devolve quantos foram creditados."""
        pontos = valor_gasto * PONTOS_POR_REAL_GASTO
        self.__bytepoints += pontos
        return pontos

    @property
    def cashback_disponivel(self):
        return self.__bytepoints / PONTOS_PARA_UM_REAL

    def resumo_fidelidade(self):
        return (f"Titular: {self.titular}\n"
                f"Conta: {self.numero}\n"
                f"Saldo de BytePoints: {formatar_numero(self.__bytepoints)} pontos\n"
                f"Equivalente em cashback: {formatar_reais(self.cashback_disponivel)}\n"
                f"Regra: {PONTOS_POR_REAL_GASTO} ponto por R$ 1,00 gasto | "
                f"{PONTOS_PARA_UM_REAL} pontos = R$ 1,00\n"
                f"Resgate mínimo: {MINIMO_PONTOS_PARA_RESGATE} pontos")

    def resgatar_pontos(self, pontos):
        if pontos <= 0:
            return False, "[RECUSADO] A quantidade de pontos deve ser positiva."
        if pontos < MINIMO_PONTOS_PARA_RESGATE:
            return False, (f"[RECUSADO] O resgate mínimo é de {MINIMO_PONTOS_PARA_RESGATE} pontos. "
                           f"Você tem {formatar_numero(self.__bytepoints)} pontos.")
        if pontos > self.__bytepoints:
            return False, (f"[RECUSADO] Pontos insuficientes. "
                           f"Saldo disponível: {formatar_numero(self.__bytepoints)} pontos.")

        valor_cashback = pontos / PONTOS_PARA_UM_REAL
        self.__bytepoints -= pontos
        self.__saldo += valor_cashback
        self.__empilhar(Transacao("RESGATE_PONTOS", valor_cashback, pontos_resgatados=pontos))
        return True, (f"[OK] Resgate de {formatar_numero(pontos)} pontos realizado.\n"
                      f"Cashback creditado: {formatar_reais(valor_cashback)}\n"
                      f"Saldo atual: {formatar_reais(self.__saldo)}\n"
                      f"BytePoints restantes: {formatar_numero(self.__bytepoints)}")

    # ---------------- Operações básicas ----------------

    def depositar(self, valor):
        if valor <= 0:
            return False, "[RECUSADO] O valor do depósito deve ser positivo."
        self.__saldo += valor
        self.__empilhar(Transacao("DEPOSITO", valor))
        return True, (f"[OK] Depósito de {formatar_reais(valor)} realizado.\n"
                      f"Saldo atual: {formatar_reais(self.__saldo)}")

    def sacar(self, valor):
        if valor <= 0:
            return False, "[RECUSADO] O valor do saque deve ser positivo."
        if valor > LIMITE_MAXIMO_SAQUE_POR_OPERACAO:
            return False, (f"[RECUSADO] O valor excede o limite máximo por operação de saque "
                           f"({formatar_reais(LIMITE_MAXIMO_SAQUE_POR_OPERACAO)}).")
        if valor > self.__saldo:
            return False, f"[RECUSADO] Saldo insuficiente. Saldo disponível: {formatar_reais(self.__saldo)}"
        self.__saldo -= valor
        pontos = self.__acumular_pontos(valor)
        self.__empilhar(Transacao("SAQUE", valor, pontos_gerados=pontos))
        return True, (f"[OK] Saque de {formatar_reais(valor)} realizado.\n"
                      f"Saldo atual: {formatar_reais(self.__saldo)}\n"
                      f"+{formatar_numero(pontos)} BytePoints")

    def pagar_boleto(self, descricao, valor, categoria=CATEGORIA_PADRAO):
        if valor <= 0:
            return False, "[RECUSADO] O valor do pagamento deve ser positivo."
        if valor > self.__saldo:
            return False, (f"[RECUSADO] Saldo insuficiente para pagar o boleto. "
                           f"Saldo disponível: {formatar_reais(self.__saldo)}")
        self.__saldo -= valor
        pontos = self.__acumular_pontos(valor)
        self.__empilhar(Transacao("PAGAMENTO_BOLETO", valor,
                                descricao=descricao, categoria=categoria,
                                pontos_gerados=pontos))
        return True, (f"[OK] Pagamento do boleto '{descricao}' no valor de {formatar_reais(valor)} realizado.\n"
                      f"Categoria: {categoria}\n"
                      f"Saldo atual: {formatar_reais(self.__saldo)}\n"
                      f"+{formatar_numero(pontos)} BytePoints")

    # ---------------- Segurança de acesso ----------------

    @staticmethod
    def pin_valido(pin):
        """O PIN precisa ter exatamente TAMANHO_PIN dígitos numéricos."""
        return len(pin) == TAMANHO_PIN and pin.isdigit()

    def __definir_pin(self, novo_pin):
        """Grava um novo PIN, sempre com salt novo e apenas como hash."""
        self.__salt = seguranca.gerar_salt()
        self.__pin_hash = seguranca.calcular_hash(novo_pin, self.__salt)

    def confere_pin(self, pin):
        return seguranca.conferir(pin, self.__salt, self.__pin_hash)

    def autenticar(self, pin):
        """Confere o PIN e controla o bloqueio por tentativas.

        Devolve (autenticado, mensagem).
        """
        if self.__bloqueada:
            return False, "[BLOQUEADA] Esta conta está bloqueada por excesso de tentativas."

        if self.confere_pin(pin):
            self.__tentativas_falhas = 0
            return True, ""

        self.__tentativas_falhas += 1
        restantes = MAXIMO_TENTATIVAS_PIN - self.__tentativas_falhas

        if restantes <= 0:
            self.__bloqueada = True
            return False, ("[BLOQUEADA] PIN incorreto pela "
                           f"{MAXIMO_TENTATIVAS_PIN}ª vez. Conta bloqueada por segurança.")

        return False, f"[ERRO] PIN incorreto. Tentativa(s) restante(s): {restantes}."

    def desbloquear(self, cpf_informado, novo_pin):
        """Desbloqueia a conta validando o CPF do titular e definindo um novo PIN."""
        if not self.__bloqueada:
            return False, "Esta conta não está bloqueada."
        if cpf_informado != self.cpf:
            return False, "[RECUSADO] CPF não confere com o titular da conta."
        if not ContaCorrente.pin_valido(novo_pin):
            return False, f"[RECUSADO] O PIN deve ter {TAMANHO_PIN} dígitos numéricos."

        self.__definir_pin(novo_pin)
        self.__tentativas_falhas = 0
        self.__bloqueada = False
        return True, "[OK] Conta desbloqueada e novo PIN cadastrado."

    def alterar_pin(self, pin_atual, novo_pin):
        if not self.confere_pin(pin_atual):
            return False, "[RECUSADO] PIN atual incorreto."
        if not ContaCorrente.pin_valido(novo_pin):
            return False, f"[RECUSADO] O PIN deve ter {TAMANHO_PIN} dígitos numéricos."
        if self.confere_pin(novo_pin):
            return False, "[RECUSADO] O novo PIN deve ser diferente do atual."
        self.__definir_pin(novo_pin)
        return True, "[OK] PIN alterado com sucesso."

    # ---------------- Open Banking: consentimentos ----------------

    def autorizar_compartilhamento(self, codigo_instituicao, escopos):
        """Cria ou substitui o consentimento para uma instituição."""
        if not escopos:
            return False, "[RECUSADO] Selecione ao menos um escopo de dados."
        self.__consentimentos[codigo_instituicao] = Consentimento(codigo_instituicao, escopos)
        return True, ""

    def revogar_compartilhamento(self, codigo_instituicao):
        consentimento = self.__consentimentos.get(codigo_instituicao)
        if consentimento is None:
            return False, "[RECUSADO] Não existe consentimento para esta instituição."
        if not consentimento.ativo:
            return False, "[RECUSADO] Este consentimento já está revogado."
        consentimento.revogar()
        return True, ""

    def consentimento_valido(self, codigo_instituicao, escopo=None):
        """Diz se há consentimento em vigor — e, se pedido, se ele cobre o escopo."""
        consentimento = self.__consentimentos.get(codigo_instituicao)
        if consentimento is None or not consentimento.esta_valido():
            return False
        if escopo is None:
            return True
        return consentimento.cobre(escopo)

    def instituicoes_autorizadas(self, escopo=None):
        return [codigo for codigo in self.__consentimentos
                if self.consentimento_valido(codigo, escopo)]

    # ---------------- Cofrinhos (Caixinhas) ----------------

    @property
    def total_em_cofrinhos(self):
        return sum(c["saldo"] for c in self.__cofrinhos.values())

    def resumo_cofrinhos(self):
        linhas = [linha_titulo(f"Cofrinhos de {self.titular}")]
        if not self.__cofrinhos:
            linhas.append("Nenhum cofrinho criado até o momento.")
            linhas.append(linha_separadora())
            return "\n".join(linhas)

        for nome, dados in self.__cofrinhos.items():
            taxa_percentual = dados["taxa_mensal"] * 100
            linhas.append(f"  {nome:<20} {formatar_reais(dados['saldo']):>16}   "
                          f"{taxa_percentual:.2f}% a.m.")
        linhas.append(f"  {'TOTAL GUARDADO':<20} {formatar_reais(self.total_em_cofrinhos):>16}")
        linhas.append(f"Saldo em conta: {formatar_reais(self.__saldo)}")
        linhas.append(linha_separadora())
        return "\n".join(linhas)

    def criar_cofrinho(self, nome, taxa_mensal=TAXA_RENDIMENTO_MENSAL_PADRAO):
        nome = nome.strip()
        if not nome:
            return False, "[RECUSADO] O cofrinho precisa de um nome."
        if nome in self.__cofrinhos:
            return False, f"[RECUSADO] Já existe um cofrinho chamado '{nome}'."
        if taxa_mensal < 0:
            return False, "[RECUSADO] A taxa de rendimento não pode ser negativa."
        self.__cofrinhos[nome] = {"saldo": 0.0, "taxa_mensal": taxa_mensal}
        return True, (f"[OK] Cofrinho '{nome}' criado.\n"
                      f"Taxa de rendimento: {taxa_mensal * 100:.2f}% ao mês (juros simples)")

    def excluir_cofrinho(self, nome):
        if nome not in self.__cofrinhos:
            return False, f"[RECUSADO] Não existe cofrinho chamado '{nome}'."
        if self.__cofrinhos[nome]["saldo"] > 0:
            return False, (f"[RECUSADO] O cofrinho '{nome}' ainda tem "
                           f"{formatar_reais(self.__cofrinhos[nome]['saldo'])}. "
                           f"Resgate o valor antes de excluir.")
        del self.__cofrinhos[nome]
        return True, f"[OK] Cofrinho '{nome}' excluído."

    def guardar_no_cofrinho(self, nome, valor):
        if nome not in self.__cofrinhos:
            return False, f"[RECUSADO] Não existe cofrinho chamado '{nome}'."
        if valor <= 0:
            return False, "[RECUSADO] O valor a guardar deve ser positivo."
        if valor > self.__saldo:
            return False, (f"[RECUSADO] Saldo insuficiente. "
                           f"Saldo disponível: {formatar_reais(self.__saldo)}")
        self.__saldo -= valor
        self.__cofrinhos[nome]["saldo"] += valor
        self.__empilhar(Transacao("GUARDAR_COFRINHO", valor, cofrinho=nome))
        return True, (f"[OK] {formatar_reais(valor)} guardados no cofrinho '{nome}'.\n"
                      f"Saldo do cofrinho: {formatar_reais(self.__cofrinhos[nome]['saldo'])}\n"
                      f"Saldo em conta: {formatar_reais(self.__saldo)}")

    def resgatar_do_cofrinho(self, nome, valor):
        if nome not in self.__cofrinhos:
            return False, f"[RECUSADO] Não existe cofrinho chamado '{nome}'."
        if valor <= 0:
            return False, "[RECUSADO] O valor a resgatar deve ser positivo."
        if valor > self.__cofrinhos[nome]["saldo"]:
            return False, (f"[RECUSADO] O cofrinho '{nome}' tem apenas "
                           f"{formatar_reais(self.__cofrinhos[nome]['saldo'])}.")
        self.__cofrinhos[nome]["saldo"] -= valor
        self.__saldo += valor
        self.__empilhar(Transacao("RESGATAR_COFRINHO", valor, cofrinho=nome))
        return True, (f"[OK] {formatar_reais(valor)} resgatados do cofrinho '{nome}'.\n"
                      f"Saldo do cofrinho: {formatar_reais(self.__cofrinhos[nome]['saldo'])}\n"
                      f"Saldo em conta: {formatar_reais(self.__saldo)}")

    def simular_rendimento(self, nome, meses):
        """Calcula o rendimento por juros simples: J = C x i x t"""
        if nome not in self.__cofrinhos:
            return False, f"[RECUSADO] Não existe cofrinho chamado '{nome}'."
        if meses <= 0:
            return False, "[RECUSADO] O número de meses deve ser positivo."

        capital = self.__cofrinhos[nome]["saldo"]
        taxa = self.__cofrinhos[nome]["taxa_mensal"]
        juros = capital * taxa * meses

        return True, (f"Simulação do cofrinho '{nome}' (juros simples):\n"
                      f"Capital atual: {formatar_reais(capital)}\n"
                      f"Taxa: {taxa * 100:.2f}% ao mês | Período: {meses} mês(es)\n"
                      f"Rendimento estimado: {formatar_reais(juros)}\n"
                      f"Montante final: {formatar_reais(capital + juros)}")

    def aplicar_rendimento(self, nome, meses):
        if nome not in self.__cofrinhos:
            return False, f"[RECUSADO] Não existe cofrinho chamado '{nome}'."
        if meses <= 0:
            return False, "[RECUSADO] O número de meses deve ser positivo."

        capital = self.__cofrinhos[nome]["saldo"]
        if capital <= 0:
            return False, f"[RECUSADO] O cofrinho '{nome}' não tem saldo para render."

        taxa = self.__cofrinhos[nome]["taxa_mensal"]
        juros = capital * taxa * meses
        self.__cofrinhos[nome]["saldo"] += juros
        self.__empilhar(Transacao("RENDIMENTO_COFRINHO", juros, cofrinho=nome, meses=meses))

        return True, (f"[OK] Rendimento de {meses} mês(es) aplicado ao cofrinho '{nome}'.\n"
                      f"Juros creditados: {formatar_reais(juros)}\n"
                      f"Saldo do cofrinho: {formatar_reais(self.__cofrinhos[nome]['saldo'])}")

    # ---------------- Cartão de crédito ----------------

    def comprar_no_cartao(self, valor, categoria=CATEGORIA_PADRAO):
        if valor <= 0:
            return False, "[RECUSADO] O valor da compra deve ser positivo."
        if valor > self.limite_disponivel:
            return False, (f"[RECUSADO] Limite insuficiente no cartão de crédito. "
                           f"Limite disponível: {formatar_reais(self.limite_disponivel)}")
        self.__fatura_cartao_credito += valor
        pontos = self.__acumular_pontos(valor)
        self.__empilhar(Transacao("COMPRA_CARTAO", valor, categoria=categoria,
                                pontos_gerados=pontos))
        return True, (f"[OK] Compra de {formatar_reais(valor)} realizada no cartão de crédito.\n"
                      f"Categoria: {categoria}\n"
                      f"Fatura atual: {formatar_reais(self.__fatura_cartao_credito)}\n"
                      f"Limite disponível: {formatar_reais(self.limite_disponivel)}\n"
                      f"+{formatar_numero(pontos)} BytePoints")

    def pagar_fatura(self, valor):
        if valor <= 0:
            return False, "[RECUSADO] O valor do pagamento deve ser positivo."
        if self.__fatura_cartao_credito == 0:
            return False, "Não há fatura pendente para pagar nesta conta."
        if valor > self.__fatura_cartao_credito:
            return False, (f"[RECUSADO] O valor informado é maior que a fatura atual. "
                           f"Fatura atual: {formatar_reais(self.__fatura_cartao_credito)}")
        if valor > self.__saldo:
            return False, (f"[RECUSADO] Saldo insuficiente para pagar a fatura. "
                           f"Saldo disponível: {formatar_reais(self.__saldo)}")
        self.__saldo -= valor
        self.__fatura_cartao_credito -= valor
        self.__empilhar(Transacao("PAGAMENTO_FATURA", valor))
        return True, (f"[OK] Pagamento de {formatar_reais(valor)} realizado na fatura do cartão de crédito.\n"
                      f"Saldo atual: {formatar_reais(self.__saldo)}\n"
                      f"Fatura restante: {formatar_reais(self.__fatura_cartao_credito)}")

    # ---------------- Empréstimos ----------------

    @staticmethod
    def calcular_parcela(valor, parcelas):
        return (valor * (1 + TAXA_JUROS_EMPRESTIMO_MENSAL) ** parcelas) / parcelas

    @property
    def patrimonio(self):
        """Saldo em conta somado ao que está guardado nos cofrinhos."""
        return self.__saldo + self.total_em_cofrinhos

    @property
    def patrimonio_liquido(self):
        """Patrimônio descontada a dívida de empréstimos já contratada.

        É sobre este valor que o crédito é calculado: sem descontar a dívida,
        o dinheiro recebido de um empréstimo aumentaria o próprio limite,
        permitindo contratações em cascata.
        """
        return self.patrimonio - self.__divida_emprestimo

    @property
    def limite_emprestimo_pre_aprovado(self):
        """Crédito pré-aprovado com base no patrimônio líquido do cliente."""
        return max(0.0, self.patrimonio_liquido * MULTIPLICADOR_CREDITO_PRE_APROVADO)

    def resumo_credito_pre_aprovado(self):
        return (f"Titular: {self.titular}\n"
                f"Conta: {self.numero}\n"
                f"Saldo em conta: {formatar_reais(self.__saldo)}\n"
                f"Guardado em cofrinhos: {formatar_reais(self.total_em_cofrinhos)}\n"
                f"Dívida atual: {formatar_reais(self.__divida_emprestimo)}\n"
                f"Patrimônio líquido: {formatar_reais(self.patrimonio_liquido)}\n"
                f"CRÉDITO PRÉ-APROVADO: {formatar_reais(self.limite_emprestimo_pre_aprovado)}\n"
                f"Regra: até {MULTIPLICADOR_CREDITO_PRE_APROVADO}x o patrimônio líquido "
                f"(saldo + cofrinhos - dívida)\n"
                f"Parcelamento: até {MAXIMO_PARCELAS_EMPRESTIMO}x | "
                f"Juros: {TAXA_JUROS_EMPRESTIMO_MENSAL * 100:.1f}% ao mês")

    def validar_emprestimo(self, valor, parcelas):
        """Regras comuns à simulação e à contratação."""
        if valor <= 0 or parcelas <= 0:
            return False, "[RECUSADO] O valor e o número de parcelas devem ser positivos."
        if parcelas > MAXIMO_PARCELAS_EMPRESTIMO:
            return False, (f"[RECUSADO] O parcelamento máximo é de "
                           f"{MAXIMO_PARCELAS_EMPRESTIMO}x.")
        if valor > self.limite_emprestimo_pre_aprovado:
            return False, (f"[RECUSADO] Valor acima do crédito pré-aprovado.\n"
                           f"Seu limite: {formatar_reais(self.limite_emprestimo_pre_aprovado)}\n"
                           f"Valor solicitado: {formatar_reais(valor)}")
        return True, ""

    def simular_emprestimo(self, valor, parcelas):
        valido, erro = self.validar_emprestimo(valor, parcelas)
        if not valido:
            return False, erro
        valor_parcela = ContaCorrente.calcular_parcela(valor, parcelas)
        return True, ("Simulação de Empréstimo:\n"
                      f"Valor solicitado: {formatar_reais(valor)}\n"
                      f"Número de parcelas: {parcelas}\n"
                      f"Valor da parcela: {formatar_reais(valor_parcela)}\n"
                      f"Total a pagar: {formatar_reais(valor_parcela * parcelas)}\n"
                      f"Crédito pré-aprovado restante após esta contratação: "
                      f"{formatar_reais(max(0.0, self.limite_emprestimo_pre_aprovado - valor))}")

    def contratar_emprestimo(self, valor, parcelas):
        valido, erro = self.validar_emprestimo(valor, parcelas)
        if not valido:
            return False, erro
        valor_parcela = ContaCorrente.calcular_parcela(valor, parcelas)
        total_a_pagar = valor_parcela * parcelas
        self.__saldo += valor
        self.__divida_emprestimo += total_a_pagar
        self.__empilhar(Transacao("CONTRATACAO_EMPRESTIMO", valor,
                                total_a_pagar=total_a_pagar, parcelas=parcelas))
        return True, (f"[OK] Empréstimo de {formatar_reais(valor)} contratado.\n"
                      f"Número de parcelas: {parcelas}\n"
                      f"Valor da parcela: {formatar_reais(valor_parcela)}\n"
                      f"Total a pagar: {formatar_reais(total_a_pagar)}\n"
                      f"Saldo atual: {formatar_reais(self.__saldo)}\n"
                      f"Dívida total de empréstimos: {formatar_reais(self.__divida_emprestimo)}\n"
                      f"Crédito pré-aprovado restante: "
                      f"{formatar_reais(self.limite_emprestimo_pre_aprovado)}")

    def pagar_emprestimo(self, valor):
        if valor <= 0:
            return False, "[RECUSADO] O valor do pagamento deve ser positivo."
        if self.__divida_emprestimo == 0:
            return False, "Não há dívida de empréstimo pendente nesta conta."
        if valor > self.__divida_emprestimo:
            return False, (f"[RECUSADO] O valor informado é maior que a dívida atual. "
                           f"Dívida atual: {formatar_reais(self.__divida_emprestimo)}")
        if valor > self.__saldo:
            return False, (f"[RECUSADO] Saldo insuficiente para pagar o empréstimo. "
                           f"Saldo disponível: {formatar_reais(self.__saldo)}")
        self.__saldo -= valor
        self.__divida_emprestimo -= valor
        self.__empilhar(Transacao("PAGAMENTO_EMPRESTIMO", valor))
        return True, (f"[OK] Pagamento de {formatar_reais(valor)} realizado no empréstimo.\n"
                      f"Saldo atual: {formatar_reais(self.__saldo)}\n"
                      f"Dívida restante: {formatar_reais(self.__divida_emprestimo)}")

    # ---------------- Moedas estrangeiras ----------------

    @staticmethod
    def atributo_moeda(moeda):
        if moeda == "real":
            return "saldo"
        return f"saldo_{moeda}"

    @staticmethod
    def taxa(moeda):
        return TAXAS_CAMBIO.get(moeda, 1.0)

    def saldo_da_moeda(self, moeda):
        return getattr(self, ContaCorrente.atributo_moeda(moeda))

    def __ajustar_saldo_moeda(self, moeda, delta):
        atributo = ContaCorrente.atributo_moeda(moeda)
        # Leitura pela property pública; escrita pelo método privado
        self.__definir_campo_financeiro(atributo, getattr(self, atributo) + delta)

    def cambiar(self, moeda_origem, moeda_destino, quantidade_origem):
        if moeda_origem not in MOEDAS_VALIDAS or moeda_destino not in MOEDAS_VALIDAS:
            return False, "[ERRO] Moeda não suportada. Opções: real, dolar, euro, yuan."
        if moeda_origem == moeda_destino:
            return False, "[RECUSADO] A moeda de origem e a de destino devem ser diferentes."
        if quantidade_origem <= 0:
            return False, "[RECUSADO] A quantidade a ser convertida deve ser positiva."

        saldo_origem = self.saldo_da_moeda(moeda_origem)
        if quantidade_origem > saldo_origem:
            return False, (f"[RECUSADO] Saldo insuficiente em {moeda_origem}. "
                           f"Saldo disponível: {formatar_valor_moeda(moeda_origem, saldo_origem)}")

        valor_reais = quantidade_origem * ContaCorrente.taxa(moeda_origem)
        quantidade_destino = valor_reais / ContaCorrente.taxa(moeda_destino)

        self.__ajustar_saldo_moeda(moeda_origem, -quantidade_origem)
        self.__ajustar_saldo_moeda(moeda_destino, quantidade_destino)

        self.__empilhar(Transacao("CAMBIO", valor_reais,
                                moeda_origem=moeda_origem, moeda_destino=moeda_destino,
                                quantidade_origem=quantidade_origem,
                                quantidade_destino=quantidade_destino))

        return True, (f"[OK] Conversão de {formatar_valor_moeda(moeda_origem, quantidade_origem)} "
                      f"para {formatar_valor_moeda(moeda_destino, quantidade_destino)} realizada.\n"
                      f"Saldo atual em {moeda_origem}: "
                      f"{formatar_valor_moeda(moeda_origem, self.saldo_da_moeda(moeda_origem))}\n"
                      f"Saldo atual em {moeda_destino}: "
                      f"{formatar_valor_moeda(moeda_destino, self.saldo_da_moeda(moeda_destino))}")

    def comprar_moeda(self, moeda, valor_reais):
        if moeda not in TAXAS_CAMBIO:
            return False, f"[ERRO] Moeda '{moeda}' não suportada. Opções: dolar, euro, yuan."
        return self.cambiar("real", moeda, valor_reais)

    def vender_moeda(self, moeda, quantidade):
        if moeda not in TAXAS_CAMBIO:
            return False, f"[ERRO] Moeda '{moeda}' não suportada. Opções: dolar, euro, yuan."
        return self.cambiar(moeda, "real", quantidade)

    # ---------------- Suporte ao estorno ----------------

    def __snapshot(self):
        dados = {campo: getattr(self, campo) for campo in ContaCorrente.CAMPOS_FINANCEIROS}
        # Os cofrinhos são um dicionário aninhado: precisa de cópia própria
        dados["cofrinhos"] = {nome: dict(info) for nome, info in self.__cofrinhos.items()}
        return dados

    def __restaurar(self, snapshot):
        for campo, valor in snapshot.items():
            if campo == "cofrinhos":
                self.__cofrinhos = {nome: dict(info) for nome, info in valor.items()}
            else:
                self.__definir_campo_financeiro(campo, valor)

    def __tem_valor_negativo(self):
        if any(getattr(self, campo) < 0 for campo in ContaCorrente.CAMPOS_FINANCEIROS):
            return True
        return any(dados["saldo"] < 0 for dados in self.__cofrinhos.values())

    def __ajustar_cofrinho(self, nome, delta):
        """Soma delta ao cofrinho, se ele ainda existir."""
        if nome in self.__cofrinhos:
            self.__cofrinhos[nome]["saldo"] += delta

    def __aplicar_efeito(self, transacao, sinal):
        """Aplica o efeito financeiro da transação multiplicado por `sinal`.

        sinal = +1 reaplica a operação (refazer)
        sinal = -1 desfaz a operação  (estorno)

        Como todo efeito é uma soma ou subtração, inverter o sinal basta para
        obter a operação contrária — por isso estorno e refazer compartilham
        este método em vez de duplicarem a lista de tipos.
        """
        tipo = transacao.tipo
        v = transacao.valor * sinal

        pontos_gerados = transacao.obter("pontos_gerados")
        if pontos_gerados:
            self.__bytepoints += pontos_gerados * sinal

        if tipo == "DEPOSITO":
            self.__saldo += v
        elif tipo == "SAQUE":
            self.__saldo -= v
        elif tipo == "GUARDAR_COFRINHO":
            self.__saldo -= v
            self.__ajustar_cofrinho(transacao.obter("cofrinho"), v)
        elif tipo == "RESGATAR_COFRINHO":
            self.__saldo += v
            self.__ajustar_cofrinho(transacao.obter("cofrinho"), -v)
        elif tipo == "RENDIMENTO_COFRINHO":
            self.__ajustar_cofrinho(transacao.obter("cofrinho"), v)
        elif tipo == "PAGAMENTO_BOLETO":
            self.__saldo -= v
        elif tipo == "COMPRA_CARTAO":
            self.__fatura_cartao_credito += v
        elif tipo == "PAGAMENTO_FATURA":
            self.__saldo -= v
            self.__fatura_cartao_credito -= v
        elif tipo == "CONTRATACAO_EMPRESTIMO":
            self.__saldo += v
            self.__divida_emprestimo += transacao.obter("total_a_pagar") * sinal
        elif tipo == "PAGAMENTO_EMPRESTIMO":
            self.__saldo -= v
            self.__divida_emprestimo -= v
        elif tipo == "CAMBIO":
            self.__ajustar_saldo_moeda(transacao.obter("moeda_origem"),
                                     -transacao.obter("quantidade_origem") * sinal)
            self.__ajustar_saldo_moeda(transacao.obter("moeda_destino"),
                                     transacao.obter("quantidade_destino") * sinal)
        elif tipo == "RESGATE_PONTOS":
            self.__saldo += v
            self.__bytepoints -= transacao.obter("pontos_resgatados") * sinal
        elif tipo == "PORTABILIDADE":
            self.__saldo += v
        elif tipo == "PIX_ENVIADO":
            self.__saldo -= v
        elif tipo == "PIX_RECEBIDO":
            self.__saldo += v

    def __encontrar_transacao_espelho(self, tipo_espelho, valor, numero_conta_par):
        """Localiza na pilha a transação correspondente ao outro lado de um PIX.

        Devolve (indice, transacao) ou (None, None) se não encontrar.
        """
        for indice in range(len(self.__historico) - 1, -1, -1):
            transacao = self.__historico[indice]
            if (transacao.tipo == tipo_espelho
                    and transacao.valor == valor
                    and transacao.obter("conta_par") == numero_conta_par):
                return indice, transacao
        return None, None

    def para_dicionario(self):
        """Converte a conta em um dicionário, para gravação em arquivo."""
        return {
            "numero": self.numero,
            "cliente": self.__cliente.para_dicionario(),
            "chave_pix": self.__chave_pix,
            "salt": self.__salt,
            "pin_hash": self.__pin_hash,
            "tentativas_falhas": self.__tentativas_falhas,
            "bloqueada": self.__bloqueada,
            "saldo": self.__saldo,
            "limite_cartao_credito": self.__limite_cartao_credito,
            "fatura_cartao_credito": self.__fatura_cartao_credito,
            "divida_emprestimo": self.__divida_emprestimo,
            "saldo_dolar": self.__saldo_dolar,
            "saldo_euro": self.__saldo_euro,
            "saldo_yuan": self.__saldo_yuan,
            "bytepoints": self.__bytepoints,
            "cofrinhos": {nome: dict(dados) for nome, dados in self.__cofrinhos.items()},
            "historico": [t.para_dicionario() for t in self.__historico],
            "consentimentos": {c: v.para_dicionario()
                               for c, v in self.__consentimentos.items()},
        }

    @classmethod
    def de_dicionario(cls, dados):
        """Recria uma conta a partir de um dicionário lido do arquivo.

        Arquivos gravados antes da classe Cliente existir têm 'titular' e
        'cpf' soltos no nível da conta; os novos têm um bloco 'cliente'.
        Os dois formatos são aceitos, para que os dados antigos não se percam.

        Por estar dentro da classe, este método pode escrever nos atributos
        privados de 'conta' — é a própria classe se reconstruindo.
        """
        if "cliente" in dados:
            cliente = Cliente.de_dicionario(dados["cliente"])
        else:
            cliente = Cliente(nome=dados["titular"], cpf=dados["cpf"])

        conta = cls(
            numero=dados["numero"],
            cliente=cliente,
            chave_pix=dados["chave_pix"],
            saldo=dados.get("saldo", 0.0),
            limite_cartao_credito=dados.get("limite_cartao_credito", 0.0),
            saldo_dolar=dados.get("saldo_dolar", 0.0),
            saldo_euro=dados.get("saldo_euro", 0.0),
            saldo_yuan=dados.get("saldo_yuan", 0.0),
        )
        if "pin_hash" in dados and "salt" in dados:
            conta.__salt = dados["salt"]
            conta.__pin_hash = dados["pin_hash"]
        elif "pin" in dados:
            # Arquivo de uma versão anterior, com PIN em texto: migra para hash
            conta.__definir_pin(dados["pin"])
        conta.__tentativas_falhas = dados.get("tentativas_falhas", 0)
        conta.__bloqueada = dados.get("bloqueada", False)
        conta.__fatura_cartao_credito = dados.get("fatura_cartao_credito", 0.0)
        conta.__divida_emprestimo = dados.get("divida_emprestimo", 0.0)
        conta.__bytepoints = dados.get("bytepoints", 0.0)
        conta.__cofrinhos = {nome: dict(info) for nome, info in dados.get("cofrinhos", {}).items()}
        conta.__historico = [Transacao.de_dicionario(t) for t in dados.get("historico", [])]
        conta.__consentimentos = {c: Consentimento.de_dicionario(v)
                                for c, v in dados.get("consentimentos", {}).items()}
        return conta

    def __repr__(self):
        return f"ContaCorrente({self.numero}, {self.titular}, {formatar_reais(self.__saldo)})"
