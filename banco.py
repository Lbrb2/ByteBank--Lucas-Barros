"""Classe que coordena o conjunto de contas, as operações entre contas,
a fila de boletos agendados (FIFO), o log de auditoria do sistema e a
persistência de todo esse estado em disco.

Arquitetura (Cliente -> ContaCorrente -> Banco):

    Cliente  --possui 1-->  ContaCorrente  --pertence a-->  Banco  --> disco
    nome, CPF, contato      saldo privado,                 todas as contas,
                            limite, o Cliente dono         salvar_estado()
"""

import json
import os

from formatacao import formatar_reais, formatar_numero, linha_separadora, linha_titulo
from cliente import Cliente
from conta import ContaCorrente, CATEGORIA_PADRAO, TAMANHO_PIN, TIPOS_PIX
from open_banking import Diretorio, ESCOPOS
from datetime import datetime, timedelta
import heapq
import persistencia_txt

ARQUIVO_ESTADO = "dados_bytebank.json"


class Banco:
    """Contêiner de todas as contas.

    Todos os atributos são privados. De fora, as contas podem ser lidas pela
    property 'contas' (uma tupla, que não aceita insert nem append) e só
    entram pelo método adicionar_conta, que mantém a lista ordenada e
    recusa duplicatas. O log de auditoria não tem acesso externo de escrita:
    um registro de auditoria que aceitasse entradas de fora não provaria nada.
    """

    # Lista fechada de atributos. Sem ela, 'objeto.atributo_novo = x' não
    # daria erro: o Python criaria um atributo solto, que a classe nunca lê.
    __slots__ = ("__nome", "__contas", "__fila_boletos", "__registro_operacoes",
                 "__diretorio", "__acessos_open_banking")

    def __init__(self, nome="ByteBank"):
        self.__nome = nome
        self.__contas = []
        self.__fila_boletos = []      # Fila (FIFO) de boletos agendados
        self.__registro_operacoes = []  # Log de auditoria de todas as operações
        self.__diretorio = Diretorio()  # Instituições do Open Banking
        self.__acessos_open_banking = []  # Trilha de acessos a dados externos

    # ---------------- Atributos blindados (somente leitura) ----------------

    @property
    def nome(self):
        return self.__nome

    @property
    def contas(self):
        """Tupla com as contas, na ordem de número. Alterar a lista por fora
        (um append, por exemplo) quebraria a ordenação da busca binária."""
        return tuple(self.__contas)

    @property
    def diretorio(self):
        """O diretório do Open Banking. O objeto é entregue, mas ele mesmo
        protege o que guarda: só aceita instituições por adicionar()."""
        return self.__diretorio

    # ---------------- Log de auditoria ----------------

    def __registrar(self, conta, tipo, detalhes):
        self.__registro_operacoes.append({
            "conta": conta.numero,
            "titular": conta.titular,
            "tipo": tipo,
            "detalhes": detalhes
        })

    def operacoes_da_conta(self, conta):
        return [op for op in self.__registro_operacoes if op["conta"] == conta.numero]

    def historico_formatado(self, conta):
        operacoes = self.operacoes_da_conta(conta)
        if not operacoes:
            return "Nenhuma operação registrada para esta conta até o momento."

        linhas = [linha_titulo(f"Histórico de Operações - {conta.titular} (Conta {conta.numero})")]
        for posicao, operacao in enumerate(operacoes, start=1):
            linhas.append(f"  {posicao}. {operacao['tipo']:<28} {operacao['detalhes']}")
        linhas.append(f"Total de operações: {len(operacoes)}")
        linhas.append(linha_separadora())
        return "\n".join(linhas)

    # ---------------- Busca e cadastro ----------------

    def buscar_por_numero(self, numero):
        """Busca uma conta pelo número. Usa busca binária: O(log n)."""
        conta, _ = self.busca_binaria(numero)
        return conta

    def busca_binaria(self, numero):
        """Busca binária sobre a lista de contas, ordenada por número.

        A cada passo descarta metade do intervalo de busca, o que dá
        complexidade O(log n). Devolve (conta, comparacoes) — o contador
        existe para permitir comparar o desempenho com a busca sequencial.
        """
        inicio = 0
        fim = len(self.__contas) - 1
        comparacoes = 0

        while inicio <= fim:
            meio = (inicio + fim) // 2
            comparacoes += 1
            numero_do_meio = self.__contas[meio].numero

            if numero_do_meio == numero:
                return self.__contas[meio], comparacoes
            if numero_do_meio < numero:
                inicio = meio + 1   # procura na metade de cima
            else:
                fim = meio - 1      # procura na metade de baixo

        return None, comparacoes

    def busca_sequencial(self, numero):
        """Busca linear O(n), mantida para efeito de comparação."""
        comparacoes = 0
        for conta in self.__contas:
            comparacoes += 1
            if conta.numero == numero:
                return conta, comparacoes
        return None, comparacoes

    def posicao_de_insercao(self, numero):
        """Encontra, por busca binária, onde inserir para manter a ordem."""
        inicio = 0
        fim = len(self.__contas)
        while inicio < fim:
            meio = (inicio + fim) // 2
            if self.__contas[meio].numero < numero:
                inicio = meio + 1
            else:
                fim = meio
        return inicio

    def buscar_por_cpf(self, cpf):
        """Busca sequencial O(n): a lista está ordenada por número de conta,
        não por CPF, então a busca binária não se aplica aqui."""
        for conta in self.__contas:
            if conta.cpf == cpf:
                return conta
        return None

    def buscar_por_numero_ou_cpf(self, identificador):
        return self.buscar_por_numero(identificador) or self.buscar_por_cpf(identificador)

    def buscar_por_chave_pix(self, chave):
        for conta in self.__contas:
            if conta.chave_pix == chave:
                return conta
        return None

    def adicionar_conta(self, conta):
        """Insere a conta na posição que mantém a lista ordenada por número.

        A ordenação é pré-requisito da busca binária: inserir no fim com
        append() quebraria o algoritmo. É a única porta de entrada de contas
        no banco, então é aqui que fica a garantia de que número, CPF e chave
        PIX não se repetem. Devolve (sucesso, mensagem).
        """
        if not isinstance(conta, ContaCorrente):
            return False, "[ERRO] Só é possível adicionar instâncias de ContaCorrente."
        if self.buscar_por_numero(conta.numero):
            return False, f"[ERRO] Já existe uma conta com o número {conta.numero}."
        if self.buscar_por_cpf(conta.cpf):
            return False, f"[ERRO] Já existe uma conta cadastrada com o CPF '{conta.cpf}'."
        if self.buscar_por_chave_pix(conta.chave_pix):
            return False, (f"[ERRO] Já existe uma conta cadastrada com a chave PIX "
                           f"'{conta.chave_pix}'.")
        self.__contas.insert(self.posicao_de_insercao(conta.numero), conta)
        return True, ""

    def criar_conta(self, numero, titular, cpf, chave_pix,
                    email="", telefone="", **kwargs):
        if not str(numero).strip():
            return None, "[ERRO] O número da conta não pode ficar vazio."
        if self.buscar_por_numero(numero):
            return None, f"[ERRO] Já existe uma conta com o número {numero}."
        if self.buscar_por_cpf(cpf):
            return None, f"[ERRO] Já existe uma conta cadastrada com o CPF '{cpf}'."
        if self.buscar_por_chave_pix(chave_pix):
            return None, f"[ERRO] Já existe uma conta cadastrada com a chave PIX '{chave_pix}'."
        pin = kwargs.get("pin", "")
        if not ContaCorrente.pin_valido(pin):
            return None, f"[ERRO] O PIN deve ter {TAMANHO_PIN} dígitos numéricos."

        # O Cliente valida os próprios dados (CPF, nome, e-mail, telefone) e
        # recusa com ValueError. Aqui o erro vira mensagem para a interface.
        try:
            cliente = Cliente(titular, cpf, email, telefone)
        except ValueError as erro:
            return None, f"[ERRO] {erro}"

        nova_conta = ContaCorrente(numero, cliente, chave_pix, **kwargs)
        self.adicionar_conta(nova_conta)
        self.__registrar(nova_conta, "criar_conta", f"titular: {titular}, CPF: {cpf}")
        return nova_conta, f"[OK] Conta criada com sucesso! Número: {numero}, Titular: {titular}"

    # ---------------- Operações de uma conta (com log) ----------------

    def executar(self, conta, metodo, *args):
        """Executa uma operação da conta e registra no log apenas se ela for concluída.

        O nome da operação no log é derivado do próprio método executado.
        """
        sucesso, mensagem = metodo(*args)
        if sucesso:
            self.__registrar(conta, metodo.__name__, self.__detalhe_ultima(conta))
        return sucesso, mensagem

    def __detalhe_ultima(self, conta):
        transacao = conta.ultima_transacao()
        if transacao is None:
            return ""
        return transacao.descricao()

    # ---------------- Transferência PIX ----------------

    def transferir_pix(self, conta_origem, chave_destino, valor):
        """Localiza a conta de destino pela chave e pede à conta de origem
        que faça a transferência. Débito, crédito e extratos são feitos pela
        própria conta (ContaCorrente.enviar_pix); o Banco localiza e registra."""
        if valor <= 0:
            return False, "[RECUSADO] O valor da transferência deve ser positivo."

        conta_destino = self.buscar_por_chave_pix(chave_destino)
        if conta_destino is None:
            return False, f"[RECUSADO] Nenhuma conta encontrada com a chave PIX '{chave_destino}'."

        if conta_destino.numero == conta_origem.numero:
            return False, "[RECUSADO] Não é possível transferir para a própria conta."

        sucesso, mensagem = conta_origem.enviar_pix(conta_destino, valor)
        if sucesso:
            self.__registrar(conta_origem, "pix_enviado",
                             f"{formatar_reais(valor)} para {conta_destino.titular}")
            self.__registrar(conta_destino, "pix_recebido",
                             f"{formatar_reais(valor)} de {conta_origem.titular}")
        return sucesso, mensagem

    # ---------------- Estorno (Pilha / LIFO) ----------------

    def estornar_ultima_transacao(self, conta):
        """Desfaz a última transação da conta.

        A conta desfaz o próprio efeito (e o da outra conta, num PIX). Ao
        Banco cabe o que está fora das contas: localizar a outra conta do PIX
        e, numa portabilidade, devolver o dinheiro à instituição de origem.
        """
        transacao = conta.ultima_transacao()
        if transacao is None:
            return False, "Não há transações no histórico para estornar."

        conta_par = None
        if transacao.tipo in TIPOS_PIX:
            conta_par = self.buscar_por_numero(transacao.obter("conta_par"))
            if conta_par is None:
                return False, ("[RECUSADO] A conta envolvida no PIX não foi encontrada. "
                               "Estorno cancelado.")

        # A portabilidade trouxe dinheiro de outra instituição: desfazê-la
        # exige devolvê-lo lá, senão o valor desapareceria do sistema. A
        # devolução vem primeiro porque é a etapa que pode ser recusada.
        instituicao = None
        if transacao.tipo == "PORTABILIDADE":
            instituicao = self.__diretorio.buscar(transacao.obter("instituicao"))
            if instituicao is not None:
                sucesso, erro = instituicao.devolver(conta.cpf, transacao.valor)
                if not sucesso:
                    return False, f"[RECUSADO] Não é possível estornar: {erro}"

        sucesso, mensagem = conta.estornar_ultima(conta_par)
        if not sucesso:
            if instituicao is not None:
                instituicao.debitar(conta.cpf, transacao.valor)   # desfaz a devolução
            return False, mensagem

        self.__registrar(conta, "estorno", f"{transacao.tipo} de {transacao.descricao()}")
        return True, mensagem

    def refazer_ultima_transacao(self, conta):
        """Reaplica a última transação estornada (pilha de refazer, LIFO)."""
        item = conta.proximo_para_refazer()
        if item is None:
            return False, "Não há transações estornadas para refazer."

        transacao = item["transacao"]
        conta_par = None
        if item["conta_par"] is not None:
            conta_par = self.buscar_por_numero(item["conta_par"])
            if conta_par is None:
                return False, ("[RECUSADO] A conta envolvida no PIX não foi encontrada. "
                               "Não é possível refazer.")

        instituicao = None
        if transacao.tipo == "PORTABILIDADE":
            instituicao = self.__diretorio.buscar(transacao.obter("instituicao"))
            if instituicao is not None:
                sucesso, erro = instituicao.debitar(conta.cpf, transacao.valor)
                if not sucesso:
                    return False, f"[RECUSADO] Não é possível refazer: {erro}"

        sucesso, mensagem = conta.refazer_ultima(conta_par)
        if not sucesso:
            if instituicao is not None:
                instituicao.devolver(conta.cpf, transacao.valor)   # desfaz o débito
            return False, mensagem

        self.__registrar(conta, "refazer", f"{transacao.tipo} de {transacao.descricao()}")
        return True, mensagem


    # ---------------- Open Banking ----------------

    def __registrar_acesso(self, conta, instituicao, escopo):
        """Registra na trilha de auditoria um acesso a dados de outra instituição."""
        self.__acessos_open_banking.append({
            "quando": datetime.now().isoformat(timespec="seconds"),
            "conta": conta.numero,
            "cpf": conta.cpf,
            "instituicao": instituicao.nome,
            "codigo": instituicao.codigo,
            "escopo": escopo,
        })

    def instituicoes_com_cliente(self, conta):
        """Instituições parceiras que têm conta no CPF do cliente."""
        return [i for i in self.__diretorio.listar() if i.tem_cliente(conta.cpf)]

    def listar_instituicoes(self, conta):
        linhas = [linha_titulo("Instituições Participantes do Open Banking")]
        parceiras = self.__diretorio.listar()
        if not parceiras:
            linhas.append("Nenhuma instituição cadastrada.")
            linhas.append(linha_separadora())
            return "\n".join(linhas)

        for instituicao in parceiras:
            tem_conta = "sim" if instituicao.tem_cliente(conta.cpf) else "não"
            consentimento = conta.consentimentos.get(instituicao.codigo)
            situacao = consentimento.situacao() if consentimento else "SEM CONSENTIMENTO"
            linhas.append(f"  [{instituicao.codigo}] {instituicao.nome:<26} "
                          f"conta sua: {tem_conta:<4} | {situacao}")
        linhas.append(linha_separadora())
        return "\n".join(linhas)

    def autorizar(self, conta, codigo, escopos):
        instituicao = self.__diretorio.buscar(codigo)
        if instituicao is None:
            return False, f"[RECUSADO] Instituição '{codigo}' não encontrada no diretório."

        sucesso, erro = conta.autorizar_compartilhamento(codigo, escopos)
        if not sucesso:
            return False, erro

        consentimento = conta.consentimentos[codigo]
        nomes = ", ".join(ESCOPOS.get(e, e) for e in escopos)
        self.__registrar(conta, "open_banking_autorizar", f"{instituicao.nome} ({nomes})")
        return True, (f"[OK] Compartilhamento autorizado com {instituicao.nome}.\n"
                      f"Dados: {nomes}\n"
                      f"Válido até: {consentimento.valida_ate[:10]}")

    def revogar(self, conta, codigo):
        instituicao = self.__diretorio.buscar(codigo)
        nome = instituicao.nome if instituicao else codigo

        sucesso, erro = conta.revogar_compartilhamento(codigo)
        if not sucesso:
            return False, erro

        self.__registrar(conta, "open_banking_revogar", nome)
        return True, (f"[OK] Consentimento revogado para {nome}.\n"
                      "Os dados desta instituição não aparecem mais na visão consolidada.")

    def listar_consentimentos(self, conta):
        linhas = [linha_titulo(f"Consentimentos de {conta.titular}")]
        if not conta.consentimentos:
            linhas.append("Nenhum consentimento concedido até o momento.")
            linhas.append(linha_separadora())
            return "\n".join(linhas)

        for codigo, consentimento in conta.consentimentos.items():
            instituicao = self.__diretorio.buscar(codigo)
            nome = instituicao.nome if instituicao else codigo
            escopos = ", ".join(ESCOPOS.get(e, e) for e in consentimento.escopos)
            linhas.append(f"  {nome:<26} {consentimento.situacao()}")
            linhas.append(f"     dados: {escopos}")
            linhas.append(f"     concedido em {consentimento.criado_em[:10]} | "
                          f"válido até {consentimento.valida_ate[:10]}")
            if consentimento.revogado_em:
                linhas.append(f"     revogado em {consentimento.revogado_em[:10]}")
        linhas.append(linha_separadora())
        return "\n".join(linhas)

    def visao_consolidada(self, conta):
        """Agrega o patrimônio do cliente no ByteBank e nas instituições autorizadas."""
        linhas = [linha_titulo(f"Visão Consolidada - {conta.titular}")]

        total = conta.saldo + conta.total_em_cofrinhos
        linhas.append(f"  {self.__nome + ' (aqui)':<28} {formatar_reais(total):>16}")
        linhas.append(f"     conta: {formatar_reais(conta.saldo)} | "
                      f"cofrinhos: {formatar_reais(conta.total_em_cofrinhos)}")

        consultadas = 0
        sem_consentimento = []

        for instituicao in self.instituicoes_com_cliente(conta):
            if not conta.consentimento_valido(instituicao.codigo, "saldo"):
                sem_consentimento.append(instituicao.nome)
                continue

            dados = instituicao.dados_do_cliente(conta.cpf)
            self.__registrar_acesso(conta, instituicao, "saldo")
            consultadas += 1

            saldo = dados.get("saldo", 0.0)
            investimentos = 0.0
            if conta.consentimento_valido(instituicao.codigo, "investimentos"):
                investimentos = dados.get("investimentos", 0.0)

            subtotal = saldo + investimentos
            total += subtotal
            linhas.append(f"  {instituicao.nome:<28} {formatar_reais(subtotal):>16}")
            detalhe = f"     conta: {formatar_reais(saldo)}"
            if conta.consentimento_valido(instituicao.codigo, "investimentos"):
                detalhe += f" | investimentos: {formatar_reais(investimentos)}"
            else:
                detalhe += " | investimentos: não autorizado"
            linhas.append(detalhe)

        linhas.append(f"  {'PATRIMÔNIO TOTAL':<28} {formatar_reais(total):>16}")
        linhas.append(f"Instituições consultadas: {consultadas}")
        if sem_consentimento:
            linhas.append("Sem consentimento (não incluídas): " + ", ".join(sem_consentimento))
        linhas.append(linha_separadora())
        return "\n".join(linhas)

    def portar_saldo(self, conta, codigo, valor):
        """Traz saldo de uma instituição parceira para o ByteBank."""
        instituicao = self.__diretorio.buscar(codigo)
        if instituicao is None:
            return False, f"[RECUSADO] Instituição '{codigo}' não encontrada."
        if not instituicao.tem_cliente(conta.cpf):
            return False, f"[RECUSADO] Você não possui conta em {instituicao.nome}."
        if not conta.consentimento_valido(codigo, "saldo"):
            return False, (f"[RECUSADO] É preciso um consentimento ativo com "
                           f"{instituicao.nome} para portar saldo.")

        sucesso, erro = instituicao.debitar(conta.cpf, valor)
        if not sucesso:
            return False, f"[RECUSADO] {erro}"

        sucesso, mensagem = conta.receber_portabilidade(valor, codigo, instituicao.nome)
        if not sucesso:
            instituicao.devolver(conta.cpf, valor)   # o dinheiro volta para lá
            return False, mensagem

        self.__registrar_acesso(conta, instituicao, "portabilidade")
        self.__registrar(conta, "open_banking_portabilidade",
                       f"{formatar_reais(valor)} de {instituicao.nome}")
        return True, mensagem

    def trilha_acessos(self, conta):
        acessos = [a for a in self.__acessos_open_banking if a["conta"] == conta.numero]
        linhas = [linha_titulo("Trilha de Acessos - Open Banking")]
        if not acessos:
            linhas.append("Nenhum acesso a dados externos registrado.")
            linhas.append(linha_separadora())
            return "\n".join(linhas)

        for acesso in acessos:
            quando = acesso["quando"].replace("T", " ")
            linhas.append(f"  {quando} | {acesso['instituicao']:<24} | {acesso['escopo']}")
        linhas.append(f"Total de acessos: {len(acessos)}")
        linhas.append(linha_separadora())
        return "\n".join(linhas)

    # ---------------- Fila de boletos (FIFO) ----------------

    def agendar_boleto(self, conta, descricao, valor,
                       categoria=CATEGORIA_PADRAO, dias_para_vencer=30):
        if valor <= 0:
            return False, "[RECUSADO] O valor do boleto deve ser positivo."
        if dias_para_vencer < 0:
            return False, "[RECUSADO] O prazo de vencimento não pode ser negativo."

        vencimento = (datetime.now() + timedelta(days=dias_para_vencer))
        self.__fila_boletos.append({
            "conta": conta.numero,
            "descricao": descricao,
            "valor": valor,
            "categoria": categoria,
            "vencimento": vencimento.isoformat(timespec="seconds"),
        })
        self.__registrar(conta, "agendar_boleto", f"{descricao} - {formatar_reais(valor)}")
        return True, (f"[OK] Boleto '{descricao}' de {formatar_reais(valor)} agendado.\n"
                      f"Categoria: {categoria}\n"
                      f"Vencimento: {vencimento.strftime('%d/%m/%Y')}")

    def fila_formatada(self):
        linhas = [linha_titulo("Fila de Boletos Agendados")]
        if not self.__fila_boletos:
            linhas.append("Nenhum boleto agendado.")
        else:
            for posicao, boleto in enumerate(self.__fila_boletos, start=1):
                linhas.append(f"  {posicao}º - Conta {boleto['conta']}: "
                              f"{boleto['descricao']} - {formatar_reais(boleto['valor'])} "
                              f"| vence {Banco.vencimento_formatado(boleto)}")
        linhas.append(linha_separadora())
        return "\n".join(linhas)

    def processar_boletos(self):
        if not self.__fila_boletos:
            return False, "Não há boletos agendados na fila."

        linhas = [linha_titulo("Processando fila de boletos (ordem de chegada)")]
        pendentes = []

        while self.__fila_boletos:
            boleto = self.__fila_boletos.pop(0)  # FIFO
            conta = self.buscar_por_numero(boleto["conta"])

            if conta is None:
                linhas.append(f"[ERRO] Conta {boleto['conta']} não encontrada. Boleto descartado.")
                continue

            sucesso, mensagem = conta.pagar_boleto(boleto["descricao"], boleto["valor"],
                                                   boleto.get("categoria", CATEGORIA_PADRAO))
            if not sucesso:
                pendentes.append(boleto)
                linhas.append(f"[PENDENTE] {boleto['descricao']} "
                              f"({formatar_reais(boleto['valor'])}) na conta {conta.numero}: "
                              f"{mensagem.replace('[RECUSADO] ', '')} "
                              f"O boleto continua na fila.")
                continue

            self.__registrar(conta, "pagar_boleto_agendado",
                           f"{boleto['descricao']} - {formatar_reais(boleto['valor'])}")
            linhas.append(f"[PAGO] {boleto['descricao']} - {formatar_reais(boleto['valor'])} "
                          f"debitado da conta {conta.numero} ({conta.titular})")

        self.__fila_boletos = pendentes
        if pendentes:
            linhas.append(linha_titulo(f"{len(pendentes)} boleto(s) continuam pendentes na fila"))
        else:
            linhas.append(linha_titulo("Fila de boletos finalizada"))
        return True, "\n".join(linhas)

    @staticmethod
    def vencimento_formatado(boleto):
        vencimento = boleto.get("vencimento")
        if not vencimento:
            return "sem data"
        return datetime.fromisoformat(vencimento).strftime("%d/%m/%Y")

    @staticmethod
    def chave_vencimento(boleto):
        """Boletos sem data vão para o fim da ordenação por urgência."""
        return boleto.get("vencimento") or "9999-12-31T23:59:59"

    def processar_boletos_por_vencimento(self):
        """Processa os boletos do mais urgente ao menos urgente.

        Usa uma fila de prioridade (heap binário). Diferente da fila FIFO, que
        respeita a ordem de chegada, aqui a saída é sempre o boleto de menor
        vencimento — independentemente de quando foi agendado.

        O heap mantém o menor elemento na raiz, então cada retirada custa
        O(log n) em vez de O(n) de uma busca pelo menor a cada passo.
        """
        if not self.__fila_boletos:
            return False, "Não há boletos agendados na fila."

        heap = []
        for ordem, boleto in enumerate(self.__fila_boletos):
            # a ordem entra como desempate, para vencimentos iguais manterem
            # a ordem de chegada (e para o heap nunca comparar dicionários)
            heapq.heappush(heap, (Banco.chave_vencimento(boleto), ordem, boleto))

        linhas = [linha_titulo("Processando boletos por vencimento (mais urgente primeiro)")]
        pendentes = []

        while heap:
            _, _, boleto = heapq.heappop(heap)
            conta = self.buscar_por_numero(boleto["conta"])
            vencimento = Banco.vencimento_formatado(boleto)

            if conta is None:
                linhas.append(f"[ERRO] Conta {boleto['conta']} não encontrada. Boleto descartado.")
                continue

            sucesso, mensagem = conta.pagar_boleto(boleto["descricao"], boleto["valor"],
                                                   boleto.get("categoria", CATEGORIA_PADRAO))
            if not sucesso:
                pendentes.append(boleto)
                linhas.append(f"[PENDENTE] {boleto['descricao']} (vence {vencimento}): "
                              f"{mensagem.replace('[RECUSADO] ', '')} O boleto continua na fila.")
                continue

            self.__registrar(conta, "pagar_boleto_agendado",
                           f"{boleto['descricao']} - {formatar_reais(boleto['valor'])}")
            linhas.append(f"[PAGO] {boleto['descricao']} - {formatar_reais(boleto['valor'])} "
                          f"| vencia {vencimento} | conta {conta.numero}")

        self.__fila_boletos = pendentes
        if pendentes:
            linhas.append(linha_titulo(f"{len(pendentes)} boleto(s) continuam pendentes"))
        else:
            linhas.append(linha_titulo("Todos os boletos foram processados"))
        return True, "\n".join(linhas)

    # ---------------- Persistência ----------------

    def para_dicionario(self):
        """Converte o estado completo do banco em um dicionário."""
        return {
            "nome": self.__nome,
            "contas": [conta.para_dicionario() for conta in self.__contas],
            "fila_boletos": list(self.__fila_boletos),
            "registro_operacoes": list(self.__registro_operacoes),
            "diretorio": self.__diretorio.para_dicionario(),
            "acessos_open_banking": list(self.__acessos_open_banking),
        }

    @classmethod
    def de_dicionario(cls, dados):
        """Recria o banco a partir de um dicionário lido do arquivo."""
        banco = cls(dados.get("nome", "ByteBank"))
        contas = [ContaCorrente.de_dicionario(c) for c in dados.get("contas", [])]
        # A busca binária exige a lista ordenada por número de conta: a ordem
        # gravada no arquivo não é garantia suficiente.
        banco.__contas = sorted(contas, key=lambda conta: conta.numero)
        banco.__fila_boletos = list(dados.get("fila_boletos", []))
        banco.__registro_operacoes = list(dados.get("registro_operacoes", []))
        dados_diretorio = Banco.__completar_portabilidades(dados.get("diretorio") or {}, contas)
        banco.__diretorio = Diretorio.de_dicionario(dados_diretorio)
        banco.__acessos_open_banking = list(dados.get("acessos_open_banking", []))
        return banco

    @staticmethod
    def __completar_portabilidades(dados_diretorio, contas):
        """Reconstrói o registro do que cada parceira já portou, quando ele
        não está no arquivo (arquivos de versões anteriores).

        Sem esse registro, a parceira recusaria receber de volta o dinheiro
        de um estorno de portabilidade. Ele pode ser reconstruído com
        exatidão a partir dos extratos: toda PORTABILIDADE que ainda está no
        histórico de uma conta é dinheiro que saiu da parceira e não voltou.
        """
        totais = {}
        for conta in contas:
            for transacao in conta.historico:
                if transacao.tipo == "PORTABILIDADE":
                    chave = (transacao.obter("instituicao"), conta.cpf)
                    totais[chave] = totais.get(chave, 0.0) + transacao.valor

        completado = {}
        for codigo, info in dados_diretorio.items():
            info = dict(info)
            if "portado_por_cpf" not in info:
                info["portado_por_cpf"] = {cpf: valor for (instituicao, cpf), valor
                                           in totais.items() if instituicao == codigo}
            completado[codigo] = info
        return completado

    # ---------------- Persistência (sobrevivência dos dados) ----------------

    def salvar_estado(self, caminho_json=ARQUIVO_ESTADO,
                      caminho_txt=persistencia_txt.ARQUIVO_CONTAS):
        """Persiste toda a malha de dados do banco em disco.

        Como o Banco é o contêiner que conhece todas as contas, é ele quem
        sabe se gravar por inteiro. São gravados dois arquivos:

          - JSON: o estado completo — contas com extrato e consentimentos,
            fila de boletos, log de auditoria e instituições do Open Banking;
          - TXT: contas e saldos, no formato do Projeto 1 da Aula 7, por meio
            de salvar_contas_txt().

        Devolve (sucesso, mensagem); sucesso só é True se os dois gravarem.
        """
        mensagens = []

        sucesso_txt = persistencia_txt.salvar_contas_txt(self.__contas, caminho_txt)
        if sucesso_txt:
            mensagens.append(f"{len(self.__contas)} conta(s) gravada(s) em '{caminho_txt}'.")
        else:
            mensagens.append(f"[ERRO] Não foi possível gravar '{caminho_txt}'.")

        try:
            # O texto é montado inteiro ANTES de abrir o arquivo. Se algo der
            # errado na conversão, o erro acontece aqui e o arquivo anterior
            # continua intacto. Abrindo primeiro, o modo 'w' já teria apagado
            # o conteúdo antigo e um erro no meio deixaria o arquivo pela metade.
            conteudo = json.dumps(self.para_dicionario(), ensure_ascii=False, indent=2)
            with open(caminho_json, "w", encoding="utf-8") as arquivo:
                arquivo.write(conteudo)
            mensagens.append(f"Estado completo salvo em '{caminho_json}'.")
            sucesso_json = True
        except (OSError, TypeError, ValueError) as erro:
            mensagens.append(f"[ERRO] Não foi possível salvar '{caminho_json}': {erro}")
            sucesso_json = False

        return sucesso_txt and sucesso_json, "\n".join(mensagens)

    @classmethod
    def carregar_estado(cls, caminho_json=ARQUIVO_ESTADO,
                        caminho_txt=persistencia_txt.ARQUIVO_CONTAS):
        """Restaura o banco a partir do disco. Devolve (banco, mensagem).

        Os dois arquivos são lidos. Quando ambos existem, vale o JSON, que
        contém tudo o que o TXT contém e mais; o TXT serve de conferência
        independente dos saldos. Quando só o TXT existe, ele reconstrói as
        contas sozinho. Sem nenhum dos dois, devolve (None, mensagem) e quem
        chamou decide como começar.
        """
        mensagens = []

        contas_txt, ignoradas = persistencia_txt.carregar_contas_txt_detalhado(caminho_txt)
        mensagens.append(persistencia_txt.resumo_do_carregamento(
            contas_txt, ignoradas, caminho_txt))

        banco, mensagem_json = cls.ler_json(caminho_json)
        mensagens.append(mensagem_json)

        if banco is not None:
            # Só faz sentido conferir quando o TXT existe. Sem ele não há o que
            # comparar, e acusar divergência em todas as contas seria alarme falso.
            if os.path.exists(caminho_txt):
                for divergencia in persistencia_txt.conferir_saldos(contas_txt, banco.__contas):
                    mensagens.append(f"[AVISO] Divergência entre os arquivos: {divergencia}")
            return banco, "\n".join(mensagens)

        if contas_txt:
            banco = cls()
            for conta in contas_txt:
                sucesso, erro = banco.adicionar_conta(conta)
                if not sucesso:
                    # Linha repetida no TXT (editado à mão, por exemplo)
                    mensagens.append(f"[AVISO] Conta {conta.numero} ignorada: {erro}")
            mensagens.append("Estado reconstruído a partir do arquivo de texto.")
            return banco, "\n".join(mensagens)

        return None, "\n".join(mensagens)

    @classmethod
    def ler_json(cls, caminho):
        """Lê o arquivo JSON de estado. Devolve (banco, mensagem) ou (None, mensagem)."""
        if not os.path.exists(caminho):
            return None, f"Nenhum arquivo '{caminho}' encontrado."
        try:
            with open(caminho, "r", encoding="utf-8") as arquivo:
                dados = json.load(arquivo)
            banco = cls.de_dicionario(dados)
            return banco, f"Estado completo carregado de '{caminho}' ({len(banco.__contas)} conta(s))."
        except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as erro:
            # ValueError cobre também um Cliente com CPF inválido no arquivo
            return None, f"[AVISO] Não foi possível ler '{caminho}': {erro}"
