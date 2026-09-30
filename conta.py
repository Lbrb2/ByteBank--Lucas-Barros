"""Classe que representa uma conta bancária e suas operações individuais.

Os métodos de operação retornam uma tupla (sucesso, mensagem). A classe não
imprime nada: quem exibe as mensagens é a camada de interface.
"""

from formatacao import (formatar_reais, formatar_numero, formatar_valor_moeda,
                        linha_separadora, linha_titulo)
from transacao import Transacao
import seguranca
from open_banking import Consentimento

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


class Conta:
    CAMPOS_FINANCEIROS = [
        "saldo", "fatura_cartao_credito",
        "divida_emprestimo", "saldo_dolar", "saldo_euro", "saldo_yuan",
        "bytepoints"
    ]

    def __init__(self, numero, titular, cpf, chave_pix, saldo=0.0,
                 limite_cartao_credito=0.0, saldo_dolar=0.0, saldo_euro=0.0,
                 saldo_yuan=0.0, cofrinhos_iniciais=None, pin="0000"):
        self.numero = numero
        self.titular = titular
        self.cpf = cpf
        self.chave_pix = chave_pix
        self.salt = seguranca.gerar_salt()
        self.pin_hash = seguranca.calcular_hash(pin, self.salt)
        self.tentativas_falhas = 0
        self.bloqueada = False
        self.saldo = saldo
        self.limite_cartao_credito = limite_cartao_credito
        self.fatura_cartao_credito = 0.0
        self.divida_emprestimo = 0.0
        self.saldo_dolar = saldo_dolar
        self.saldo_euro = saldo_euro
        self.saldo_yuan = saldo_yuan
        # Cofrinhos: subcontas nomeadas, cada uma com saldo e taxa própria
        self.cofrinhos = {}
        for nome, (valor, taxa) in (cofrinhos_iniciais or {}).items():
            self.cofrinhos[nome] = {"saldo": valor, "taxa_mensal": taxa}
        self.bytepoints = 0.0  # Programa de fidelidade
        self.historico = []      # Pilha (LIFO) de transações efetivadas
        self.pilha_refazer = []  # Pilha (LIFO) de transações estornadas
        self.consentimentos = {}  # codigo da instituicao -> Consentimento

    # ---------------- Pilha de transações ----------------

    def empilhar(self, transacao):
        """Registra uma operação nova no histórico.

        Uma operação nova invalida o refazer pendente: é o mesmo
        comportamento do Ctrl+Z / Ctrl+Y de um editor de texto.
        """
        self.historico.append(transacao)
        self.pilha_refazer.clear()

    def reempilhar(self, transacao):
        """Devolve ao histórico uma transação refeita, sem limpar o refazer."""
        self.historico.append(transacao)

    def empilhar_para_refazer(self, item):
        self.pilha_refazer.append(item)

    def proximo_para_refazer(self):
        if not self.pilha_refazer:
            return None
        return self.pilha_refazer[-1]

    def desempilhar_refazer(self):
        return self.pilha_refazer.pop()

    def ultima_transacao(self):
        if not self.historico:
            return None
        return self.historico[-1]

    def desempilhar(self):
        return self.historico.pop()

    # ---------------- Consultas ----------------

    @property
    def limite_disponivel(self):
        return self.limite_cartao_credito - self.fatura_cartao_credito

    def resumo_saldo(self):
        return (f"Titular: {self.titular}\n"
                f"Conta: {self.numero} | CPF: {self.cpf}\n"
                f"Saldo atual: {formatar_reais(self.saldo)}")

    def resumo_cartao(self):
        return (f"Titular: {self.titular}\n"
                f"Conta: {self.numero}\n"
                f"Limite total: {formatar_reais(self.limite_cartao_credito)}\n"
                f"Fatura atual: {formatar_reais(self.fatura_cartao_credito)}\n"
                f"Limite disponível: {formatar_reais(self.limite_disponivel)}")

    def resumo_emprestimo(self):
        return (f"Titular: {self.titular}\n"
                f"Conta: {self.numero}\n"
                f"Dívida total de empréstimos: {formatar_reais(self.divida_emprestimo)}")

    def resumo_moedas(self):
        return (f"Titular: {self.titular}\n"
                f"Conta: {self.numero}\n"
                f"Saldo em Dólar: ${formatar_numero(self.saldo_dolar)} "
                f"({formatar_reais(self.saldo_dolar * TAXAS_CAMBIO['dolar'])})\n"
                f"Saldo em Euro: €{formatar_numero(self.saldo_euro)} "
                f"({formatar_reais(self.saldo_euro * TAXAS_CAMBIO['euro'])})\n"
                f"Saldo em Yuan: ¥{formatar_numero(self.saldo_yuan)} "
                f"({formatar_reais(self.saldo_yuan * TAXAS_CAMBIO['yuan'])})")

    def extrato(self):
        linhas = [linha_titulo(f"Extrato de {self.titular} (Conta {self.numero})")]
        if not self.historico:
            linhas.append("Nenhuma transação registrada.")
        else:
            for transacao in reversed(self.historico):
                linhas.append(f"  {transacao.tipo:<26} {transacao.descricao()}")
        linhas.append(f"Saldo atual: {formatar_reais(self.saldo)}")
        linhas.append(linha_separadora())
        return "\n".join(linhas)

    def gastos_por_categoria(self):
        """Agrupa os gastos do histórico por categoria (GROUP BY em memória).

        Percorre a pilha de transações e acumula o valor de cada gasto no
        dicionário de totais, usando a categoria como chave.
        """
        totais = {}
        for transacao in self.historico:
            if transacao.tipo not in TIPOS_DE_GASTO:
                continue
            categoria = transacao.obter("categoria") or CATEGORIA_PADRAO
            totais[categoria] = totais.get(categoria, 0.0) + transacao.valor
        return totais

    def relatorio_gastos(self):
        totais = self.gastos_por_categoria()

        linhas = [linha_titulo(f"Gastos por Categoria - {self.titular}")]
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

    def acumular_pontos(self, valor_gasto):
        """Credita pontos proporcionais ao valor gasto e devolve quantos foram creditados."""
        pontos = valor_gasto * PONTOS_POR_REAL_GASTO
        self.bytepoints += pontos
        return pontos

    @property
    def cashback_disponivel(self):
        return self.bytepoints / PONTOS_PARA_UM_REAL

    def resumo_fidelidade(self):
        return (f"Titular: {self.titular}\n"
                f"Conta: {self.numero}\n"
                f"Saldo de BytePoints: {formatar_numero(self.bytepoints)} pontos\n"
                f"Equivalente em cashback: {formatar_reais(self.cashback_disponivel)}\n"
                f"Regra: {PONTOS_POR_REAL_GASTO} ponto por R$ 1,00 gasto | "
                f"{PONTOS_PARA_UM_REAL} pontos = R$ 1,00\n"
                f"Resgate mínimo: {MINIMO_PONTOS_PARA_RESGATE} pontos")

    def resgatar_pontos(self, pontos):
        if pontos <= 0:
            return False, "[RECUSADO] A quantidade de pontos deve ser positiva."
        if pontos < MINIMO_PONTOS_PARA_RESGATE:
            return False, (f"[RECUSADO] O resgate mínimo é de {MINIMO_PONTOS_PARA_RESGATE} pontos. "
                           f"Você tem {formatar_numero(self.bytepoints)} pontos.")
        if pontos > self.bytepoints:
            return False, (f"[RECUSADO] Pontos insuficientes. "
                           f"Saldo disponível: {formatar_numero(self.bytepoints)} pontos.")

        valor_cashback = pontos / PONTOS_PARA_UM_REAL
        self.bytepoints -= pontos
        self.saldo += valor_cashback
        self.empilhar(Transacao("RESGATE_PONTOS", valor_cashback, pontos_resgatados=pontos))
        return True, (f"[OK] Resgate de {formatar_numero(pontos)} pontos realizado.\n"
                      f"Cashback creditado: {formatar_reais(valor_cashback)}\n"
                      f"Saldo atual: {formatar_reais(self.saldo)}\n"
                      f"BytePoints restantes: {formatar_numero(self.bytepoints)}")

    # ---------------- Operações básicas ----------------

    def depositar(self, valor):
        if valor <= 0:
            return False, "[RECUSADO] O valor do depósito deve ser positivo."
        self.saldo += valor
        self.empilhar(Transacao("DEPOSITO", valor))
        return True, (f"[OK] Depósito de {formatar_reais(valor)} realizado.\n"
                      f"Saldo atual: {formatar_reais(self.saldo)}")

    def sacar(self, valor):
        if valor <= 0:
            return False, "[RECUSADO] O valor do saque deve ser positivo."
        if valor > LIMITE_MAXIMO_SAQUE_POR_OPERACAO:
            return False, (f"[RECUSADO] O valor excede o limite máximo por operação de saque "
                           f"({formatar_reais(LIMITE_MAXIMO_SAQUE_POR_OPERACAO)}).")
        if valor > self.saldo:
            return False, f"[RECUSADO] Saldo insuficiente. Saldo disponível: {formatar_reais(self.saldo)}"
        self.saldo -= valor
        pontos = self.acumular_pontos(valor)
        self.empilhar(Transacao("SAQUE", valor, pontos_gerados=pontos))
        return True, (f"[OK] Saque de {formatar_reais(valor)} realizado.\n"
                      f"Saldo atual: {formatar_reais(self.saldo)}\n"
                      f"+{formatar_numero(pontos)} BytePoints")

    def pagar_boleto(self, descricao, valor, categoria=CATEGORIA_PADRAO):
        if valor <= 0:
            return False, "[RECUSADO] O valor do pagamento deve ser positivo."
        if valor > self.saldo:
            return False, (f"[RECUSADO] Saldo insuficiente para pagar o boleto. "
                           f"Saldo disponível: {formatar_reais(self.saldo)}")
        self.saldo -= valor
        pontos = self.acumular_pontos(valor)
        self.empilhar(Transacao("PAGAMENTO_BOLETO", valor,
                                descricao=descricao, categoria=categoria,
                                pontos_gerados=pontos))
        return True, (f"[OK] Pagamento do boleto '{descricao}' no valor de {formatar_reais(valor)} realizado.\n"
                      f"Categoria: {categoria}\n"
                      f"Saldo atual: {formatar_reais(self.saldo)}\n"
                      f"+{formatar_numero(pontos)} BytePoints")

    # ---------------- Segurança de acesso ----------------

    @staticmethod
    def pin_valido(pin):
        """O PIN precisa ter exatamente TAMANHO_PIN dígitos numéricos."""
        return len(pin) == TAMANHO_PIN and pin.isdigit()

    def definir_pin(self, novo_pin):
        """Grava um novo PIN, sempre com salt novo e apenas como hash."""
        self.salt = seguranca.gerar_salt()
        self.pin_hash = seguranca.calcular_hash(novo_pin, self.salt)

    def confere_pin(self, pin):
        return seguranca.conferir(pin, self.salt, self.pin_hash)

    def autenticar(self, pin):
        """Confere o PIN e controla o bloqueio por tentativas.

        Devolve (autenticado, mensagem).
        """
        if self.bloqueada:
            return False, "[BLOQUEADA] Esta conta está bloqueada por excesso de tentativas."

        if self.confere_pin(pin):
            self.tentativas_falhas = 0
            return True, ""

        self.tentativas_falhas += 1
        restantes = MAXIMO_TENTATIVAS_PIN - self.tentativas_falhas

        if restantes <= 0:
            self.bloqueada = True
            return False, ("[BLOQUEADA] PIN incorreto pela "
                           f"{MAXIMO_TENTATIVAS_PIN}ª vez. Conta bloqueada por segurança.")

        return False, f"[ERRO] PIN incorreto. Tentativa(s) restante(s): {restantes}."

    def desbloquear(self, cpf_informado, novo_pin):
        """Desbloqueia a conta validando o CPF do titular e definindo um novo PIN."""
        if not self.bloqueada:
            return False, "Esta conta não está bloqueada."
        if cpf_informado != self.cpf:
            return False, "[RECUSADO] CPF não confere com o titular da conta."
        if not Conta.pin_valido(novo_pin):
            return False, f"[RECUSADO] O PIN deve ter {TAMANHO_PIN} dígitos numéricos."

        self.definir_pin(novo_pin)
        self.tentativas_falhas = 0
        self.bloqueada = False
        return True, "[OK] Conta desbloqueada e novo PIN cadastrado."

    def alterar_pin(self, pin_atual, novo_pin):
        if not self.confere_pin(pin_atual):
            return False, "[RECUSADO] PIN atual incorreto."
        if not Conta.pin_valido(novo_pin):
            return False, f"[RECUSADO] O PIN deve ter {TAMANHO_PIN} dígitos numéricos."
        if self.confere_pin(novo_pin):
            return False, "[RECUSADO] O novo PIN deve ser diferente do atual."
        self.definir_pin(novo_pin)
        return True, "[OK] PIN alterado com sucesso."

    # ---------------- Open Banking: consentimentos ----------------

    def autorizar_compartilhamento(self, codigo_instituicao, escopos):
        """Cria ou substitui o consentimento para uma instituição."""
        if not escopos:
            return False, "[RECUSADO] Selecione ao menos um escopo de dados."
        self.consentimentos[codigo_instituicao] = Consentimento(codigo_instituicao, escopos)
        return True, ""

    def revogar_compartilhamento(self, codigo_instituicao):
        consentimento = self.consentimentos.get(codigo_instituicao)
        if consentimento is None:
            return False, "[RECUSADO] Não existe consentimento para esta instituição."
        if not consentimento.ativo:
            return False, "[RECUSADO] Este consentimento já está revogado."
        consentimento.revogar()
        return True, ""

    def consentimento_valido(self, codigo_instituicao, escopo=None):
        """Diz se há consentimento em vigor — e, se pedido, se ele cobre o escopo."""
        consentimento = self.consentimentos.get(codigo_instituicao)
        if consentimento is None or not consentimento.esta_valido():
            return False
        if escopo is None:
            return True
        return consentimento.cobre(escopo)

    def instituicoes_autorizadas(self, escopo=None):
        return [codigo for codigo in self.consentimentos
                if self.consentimento_valido(codigo, escopo)]

    # ---------------- Cofrinhos (Caixinhas) ----------------

    @property
    def total_em_cofrinhos(self):
        return sum(c["saldo"] for c in self.cofrinhos.values())

    def resumo_cofrinhos(self):
        linhas = [linha_titulo(f"Cofrinhos de {self.titular}")]
        if not self.cofrinhos:
            linhas.append("Nenhum cofrinho criado até o momento.")
            linhas.append(linha_separadora())
            return "\n".join(linhas)

        for nome, dados in self.cofrinhos.items():
            taxa_percentual = dados["taxa_mensal"] * 100
            linhas.append(f"  {nome:<20} {formatar_reais(dados['saldo']):>16}   "
                          f"{taxa_percentual:.2f}% a.m.")
        linhas.append(f"  {'TOTAL GUARDADO':<20} {formatar_reais(self.total_em_cofrinhos):>16}")
        linhas.append(f"Saldo em conta: {formatar_reais(self.saldo)}")
        linhas.append(linha_separadora())
        return "\n".join(linhas)

    def criar_cofrinho(self, nome, taxa_mensal=TAXA_RENDIMENTO_MENSAL_PADRAO):
        nome = nome.strip()
        if not nome:
            return False, "[RECUSADO] O cofrinho precisa de um nome."
        if nome in self.cofrinhos:
            return False, f"[RECUSADO] Já existe um cofrinho chamado '{nome}'."
        if taxa_mensal < 0:
            return False, "[RECUSADO] A taxa de rendimento não pode ser negativa."
        self.cofrinhos[nome] = {"saldo": 0.0, "taxa_mensal": taxa_mensal}
        return True, (f"[OK] Cofrinho '{nome}' criado.\n"
                      f"Taxa de rendimento: {taxa_mensal * 100:.2f}% ao mês (juros simples)")

    def excluir_cofrinho(self, nome):
        if nome not in self.cofrinhos:
            return False, f"[RECUSADO] Não existe cofrinho chamado '{nome}'."
        if self.cofrinhos[nome]["saldo"] > 0:
            return False, (f"[RECUSADO] O cofrinho '{nome}' ainda tem "
                           f"{formatar_reais(self.cofrinhos[nome]['saldo'])}. "
                           f"Resgate o valor antes de excluir.")
        del self.cofrinhos[nome]
        return True, f"[OK] Cofrinho '{nome}' excluído."

    def guardar_no_cofrinho(self, nome, valor):
        if nome not in self.cofrinhos:
            return False, f"[RECUSADO] Não existe cofrinho chamado '{nome}'."
        if valor <= 0:
            return False, "[RECUSADO] O valor a guardar deve ser positivo."
        if valor > self.saldo:
            return False, (f"[RECUSADO] Saldo insuficiente. "
                           f"Saldo disponível: {formatar_reais(self.saldo)}")
        self.saldo -= valor
        self.cofrinhos[nome]["saldo"] += valor
        self.empilhar(Transacao("GUARDAR_COFRINHO", valor, cofrinho=nome))
        return True, (f"[OK] {formatar_reais(valor)} guardados no cofrinho '{nome}'.\n"
                      f"Saldo do cofrinho: {formatar_reais(self.cofrinhos[nome]['saldo'])}\n"
                      f"Saldo em conta: {formatar_reais(self.saldo)}")

    def resgatar_do_cofrinho(self, nome, valor):
        if nome not in self.cofrinhos:
            return False, f"[RECUSADO] Não existe cofrinho chamado '{nome}'."
        if valor <= 0:
            return False, "[RECUSADO] O valor a resgatar deve ser positivo."
        if valor > self.cofrinhos[nome]["saldo"]:
            return False, (f"[RECUSADO] O cofrinho '{nome}' tem apenas "
                           f"{formatar_reais(self.cofrinhos[nome]['saldo'])}.")
        self.cofrinhos[nome]["saldo"] -= valor
        self.saldo += valor
        self.empilhar(Transacao("RESGATAR_COFRINHO", valor, cofrinho=nome))
        return True, (f"[OK] {formatar_reais(valor)} resgatados do cofrinho '{nome}'.\n"
                      f"Saldo do cofrinho: {formatar_reais(self.cofrinhos[nome]['saldo'])}\n"
                      f"Saldo em conta: {formatar_reais(self.saldo)}")

    def simular_rendimento(self, nome, meses):
        """Calcula o rendimento por juros simples: J = C x i x t"""
        if nome not in self.cofrinhos:
            return False, f"[RECUSADO] Não existe cofrinho chamado '{nome}'."
        if meses <= 0:
            return False, "[RECUSADO] O número de meses deve ser positivo."

        capital = self.cofrinhos[nome]["saldo"]
        taxa = self.cofrinhos[nome]["taxa_mensal"]
        juros = capital * taxa * meses

        return True, (f"Simulação do cofrinho '{nome}' (juros simples):\n"
                      f"Capital atual: {formatar_reais(capital)}\n"
                      f"Taxa: {taxa * 100:.2f}% ao mês | Período: {meses} mês(es)\n"
                      f"Rendimento estimado: {formatar_reais(juros)}\n"
                      f"Montante final: {formatar_reais(capital + juros)}")

    def aplicar_rendimento(self, nome, meses):
        if nome not in self.cofrinhos:
            return False, f"[RECUSADO] Não existe cofrinho chamado '{nome}'."
        if meses <= 0:
            return False, "[RECUSADO] O número de meses deve ser positivo."

        capital = self.cofrinhos[nome]["saldo"]
        if capital <= 0:
            return False, f"[RECUSADO] O cofrinho '{nome}' não tem saldo para render."

        taxa = self.cofrinhos[nome]["taxa_mensal"]
        juros = capital * taxa * meses
        self.cofrinhos[nome]["saldo"] += juros
        self.empilhar(Transacao("RENDIMENTO_COFRINHO", juros, cofrinho=nome, meses=meses))

        return True, (f"[OK] Rendimento de {meses} mês(es) aplicado ao cofrinho '{nome}'.\n"
                      f"Juros creditados: {formatar_reais(juros)}\n"
                      f"Saldo do cofrinho: {formatar_reais(self.cofrinhos[nome]['saldo'])}")

    # ---------------- Cartão de crédito ----------------

    def comprar_no_cartao(self, valor, categoria=CATEGORIA_PADRAO):
        if valor <= 0:
            return False, "[RECUSADO] O valor da compra deve ser positivo."
        if valor > self.limite_disponivel:
            return False, (f"[RECUSADO] Limite insuficiente no cartão de crédito. "
                           f"Limite disponível: {formatar_reais(self.limite_disponivel)}")
        self.fatura_cartao_credito += valor
        pontos = self.acumular_pontos(valor)
        self.empilhar(Transacao("COMPRA_CARTAO", valor, categoria=categoria,
                                pontos_gerados=pontos))
        return True, (f"[OK] Compra de {formatar_reais(valor)} realizada no cartão de crédito.\n"
                      f"Categoria: {categoria}\n"
                      f"Fatura atual: {formatar_reais(self.fatura_cartao_credito)}\n"
                      f"Limite disponível: {formatar_reais(self.limite_disponivel)}\n"
                      f"+{formatar_numero(pontos)} BytePoints")

    def pagar_fatura(self, valor):
        if valor <= 0:
            return False, "[RECUSADO] O valor do pagamento deve ser positivo."
        if self.fatura_cartao_credito == 0:
            return False, "Não há fatura pendente para pagar nesta conta."
        if valor > self.fatura_cartao_credito:
            return False, (f"[RECUSADO] O valor informado é maior que a fatura atual. "
                           f"Fatura atual: {formatar_reais(self.fatura_cartao_credito)}")
        if valor > self.saldo:
            return False, (f"[RECUSADO] Saldo insuficiente para pagar a fatura. "
                           f"Saldo disponível: {formatar_reais(self.saldo)}")
        self.saldo -= valor
        self.fatura_cartao_credito -= valor
        self.empilhar(Transacao("PAGAMENTO_FATURA", valor))
        return True, (f"[OK] Pagamento de {formatar_reais(valor)} realizado na fatura do cartão de crédito.\n"
                      f"Saldo atual: {formatar_reais(self.saldo)}\n"
                      f"Fatura restante: {formatar_reais(self.fatura_cartao_credito)}")

    # ---------------- Empréstimos ----------------

    @staticmethod
    def calcular_parcela(valor, parcelas):
        return (valor * (1 + TAXA_JUROS_EMPRESTIMO_MENSAL) ** parcelas) / parcelas

    @property
    def patrimonio(self):
        """Saldo em conta somado ao que está guardado nos cofrinhos."""
        return self.saldo + self.total_em_cofrinhos

    @property
    def patrimonio_liquido(self):
        """Patrimônio descontada a dívida de empréstimos já contratada.

        É sobre este valor que o crédito é calculado: sem descontar a dívida,
        o dinheiro recebido de um empréstimo aumentaria o próprio limite,
        permitindo contratações em cascata.
        """
        return self.patrimonio - self.divida_emprestimo

    @property
    def limite_emprestimo_pre_aprovado(self):
        """Crédito pré-aprovado com base no patrimônio líquido do cliente."""
        return max(0.0, self.patrimonio_liquido * MULTIPLICADOR_CREDITO_PRE_APROVADO)

    def resumo_credito_pre_aprovado(self):
        return (f"Titular: {self.titular}\n"
                f"Conta: {self.numero}\n"
                f"Saldo em conta: {formatar_reais(self.saldo)}\n"
                f"Guardado em cofrinhos: {formatar_reais(self.total_em_cofrinhos)}\n"
                f"Dívida atual: {formatar_reais(self.divida_emprestimo)}\n"
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
        valor_parcela = Conta.calcular_parcela(valor, parcelas)
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
        valor_parcela = Conta.calcular_parcela(valor, parcelas)
        total_a_pagar = valor_parcela * parcelas
        self.saldo += valor
        self.divida_emprestimo += total_a_pagar
        self.empilhar(Transacao("CONTRATACAO_EMPRESTIMO", valor,
                                total_a_pagar=total_a_pagar, parcelas=parcelas))
        return True, (f"[OK] Empréstimo de {formatar_reais(valor)} contratado.\n"
                      f"Número de parcelas: {parcelas}\n"
                      f"Valor da parcela: {formatar_reais(valor_parcela)}\n"
                      f"Total a pagar: {formatar_reais(total_a_pagar)}\n"
                      f"Saldo atual: {formatar_reais(self.saldo)}\n"
                      f"Dívida total de empréstimos: {formatar_reais(self.divida_emprestimo)}\n"
                      f"Crédito pré-aprovado restante: "
                      f"{formatar_reais(self.limite_emprestimo_pre_aprovado)}")

    def pagar_emprestimo(self, valor):
        if valor <= 0:
            return False, "[RECUSADO] O valor do pagamento deve ser positivo."
        if self.divida_emprestimo == 0:
            return False, "Não há dívida de empréstimo pendente nesta conta."
        if valor > self.divida_emprestimo:
            return False, (f"[RECUSADO] O valor informado é maior que a dívida atual. "
                           f"Dívida atual: {formatar_reais(self.divida_emprestimo)}")
        if valor > self.saldo:
            return False, (f"[RECUSADO] Saldo insuficiente para pagar o empréstimo. "
                           f"Saldo disponível: {formatar_reais(self.saldo)}")
        self.saldo -= valor
        self.divida_emprestimo -= valor
        self.empilhar(Transacao("PAGAMENTO_EMPRESTIMO", valor))
        return True, (f"[OK] Pagamento de {formatar_reais(valor)} realizado no empréstimo.\n"
                      f"Saldo atual: {formatar_reais(self.saldo)}\n"
                      f"Dívida restante: {formatar_reais(self.divida_emprestimo)}")

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
        return getattr(self, Conta.atributo_moeda(moeda))

    def ajustar_saldo_moeda(self, moeda, delta):
        atributo = Conta.atributo_moeda(moeda)
        setattr(self, atributo, getattr(self, atributo) + delta)

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

        valor_reais = quantidade_origem * Conta.taxa(moeda_origem)
        quantidade_destino = valor_reais / Conta.taxa(moeda_destino)

        self.ajustar_saldo_moeda(moeda_origem, -quantidade_origem)
        self.ajustar_saldo_moeda(moeda_destino, quantidade_destino)

        self.empilhar(Transacao("CAMBIO", valor_reais,
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

    def snapshot(self):
        dados = {campo: getattr(self, campo) for campo in Conta.CAMPOS_FINANCEIROS}
        # Os cofrinhos são um dicionário aninhado: precisa de cópia própria
        dados["cofrinhos"] = {nome: dict(info) for nome, info in self.cofrinhos.items()}
        return dados

    def restaurar(self, snapshot):
        for campo, valor in snapshot.items():
            if campo == "cofrinhos":
                self.cofrinhos = {nome: dict(info) for nome, info in valor.items()}
            else:
                setattr(self, campo, valor)

    def tem_valor_negativo(self):
        if any(getattr(self, campo) < 0 for campo in Conta.CAMPOS_FINANCEIROS):
            return True
        return any(dados["saldo"] < 0 for dados in self.cofrinhos.values())

    def _ajustar_cofrinho(self, nome, delta):
        """Soma delta ao cofrinho, se ele ainda existir."""
        if nome in self.cofrinhos:
            self.cofrinhos[nome]["saldo"] += delta

    def _aplicar_efeito(self, transacao, sinal):
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
            self.bytepoints += pontos_gerados * sinal

        if tipo == "DEPOSITO":
            self.saldo += v
        elif tipo == "SAQUE":
            self.saldo -= v
        elif tipo == "GUARDAR_COFRINHO":
            self.saldo -= v
            self._ajustar_cofrinho(transacao.obter("cofrinho"), v)
        elif tipo == "RESGATAR_COFRINHO":
            self.saldo += v
            self._ajustar_cofrinho(transacao.obter("cofrinho"), -v)
        elif tipo == "RENDIMENTO_COFRINHO":
            self._ajustar_cofrinho(transacao.obter("cofrinho"), v)
        elif tipo == "PAGAMENTO_BOLETO":
            self.saldo -= v
        elif tipo == "COMPRA_CARTAO":
            self.fatura_cartao_credito += v
        elif tipo == "PAGAMENTO_FATURA":
            self.saldo -= v
            self.fatura_cartao_credito -= v
        elif tipo == "CONTRATACAO_EMPRESTIMO":
            self.saldo += v
            self.divida_emprestimo += transacao.obter("total_a_pagar") * sinal
        elif tipo == "PAGAMENTO_EMPRESTIMO":
            self.saldo -= v
            self.divida_emprestimo -= v
        elif tipo == "CAMBIO":
            self.ajustar_saldo_moeda(transacao.obter("moeda_origem"),
                                     -transacao.obter("quantidade_origem") * sinal)
            self.ajustar_saldo_moeda(transacao.obter("moeda_destino"),
                                     transacao.obter("quantidade_destino") * sinal)
        elif tipo == "RESGATE_PONTOS":
            self.saldo += v
            self.bytepoints -= transacao.obter("pontos_resgatados") * sinal
        elif tipo == "PORTABILIDADE":
            self.saldo += v
        elif tipo == "PIX_ENVIADO":
            self.saldo -= v
        elif tipo == "PIX_RECEBIDO":
            self.saldo += v

    def aplicar_reversao(self, transacao):
        """Desfaz o efeito financeiro de uma transação nesta conta."""
        self._aplicar_efeito(transacao, -1)

    def reaplicar(self, transacao):
        """Refaz o efeito financeiro de uma transação estornada."""
        self._aplicar_efeito(transacao, +1)

    def encontrar_transacao_espelho(self, tipo_espelho, valor, numero_conta_par):
        """Localiza na pilha a transação correspondente ao outro lado de um PIX.

        Devolve (indice, transacao) ou (None, None) se não encontrar.
        """
        for indice in range(len(self.historico) - 1, -1, -1):
            transacao = self.historico[indice]
            if (transacao.tipo == tipo_espelho
                    and transacao.valor == valor
                    and transacao.obter("conta_par") == numero_conta_par):
                return indice, transacao
        return None, None

    def remover_transacao(self, indice):
        self.historico.pop(indice)

    def para_dicionario(self):
        """Converte a conta em um dicionário, para gravação em arquivo."""
        return {
            "numero": self.numero,
            "titular": self.titular,
            "cpf": self.cpf,
            "chave_pix": self.chave_pix,
            "salt": self.salt,
            "pin_hash": self.pin_hash,
            "tentativas_falhas": self.tentativas_falhas,
            "bloqueada": self.bloqueada,
            "saldo": self.saldo,
            "limite_cartao_credito": self.limite_cartao_credito,
            "fatura_cartao_credito": self.fatura_cartao_credito,
            "divida_emprestimo": self.divida_emprestimo,
            "saldo_dolar": self.saldo_dolar,
            "saldo_euro": self.saldo_euro,
            "saldo_yuan": self.saldo_yuan,
            "bytepoints": self.bytepoints,
            "cofrinhos": {nome: dict(dados) for nome, dados in self.cofrinhos.items()},
            "historico": [t.para_dicionario() for t in self.historico],
            "consentimentos": {c: v.para_dicionario()
                               for c, v in self.consentimentos.items()},
        }

    @classmethod
    def de_dicionario(cls, dados):
        """Recria uma conta a partir de um dicionário lido do arquivo."""
        conta = cls(
            numero=dados["numero"],
            titular=dados["titular"],
            cpf=dados["cpf"],
            chave_pix=dados["chave_pix"],
            saldo=dados.get("saldo", 0.0),
            limite_cartao_credito=dados.get("limite_cartao_credito", 0.0),
            saldo_dolar=dados.get("saldo_dolar", 0.0),
            saldo_euro=dados.get("saldo_euro", 0.0),
            saldo_yuan=dados.get("saldo_yuan", 0.0),
        )
        if "pin_hash" in dados and "salt" in dados:
            conta.salt = dados["salt"]
            conta.pin_hash = dados["pin_hash"]
        elif "pin" in dados:
            # Arquivo de uma versão anterior, com PIN em texto: migra para hash
            conta.definir_pin(dados["pin"])
        conta.tentativas_falhas = dados.get("tentativas_falhas", 0)
        conta.bloqueada = dados.get("bloqueada", False)
        conta.fatura_cartao_credito = dados.get("fatura_cartao_credito", 0.0)
        conta.divida_emprestimo = dados.get("divida_emprestimo", 0.0)
        conta.bytepoints = dados.get("bytepoints", 0.0)
        conta.cofrinhos = {nome: dict(info) for nome, info in dados.get("cofrinhos", {}).items()}
        conta.historico = [Transacao.de_dicionario(t) for t in dados.get("historico", [])]
        conta.consentimentos = {c: Consentimento.de_dicionario(v)
                                for c, v in dados.get("consentimentos", {}).items()}
        return conta

    def __repr__(self):
        return f"Conta({self.numero}, {self.titular}, {formatar_reais(self.saldo)})"
