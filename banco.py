"""Classe que coordena o conjunto de contas, as operações entre contas,
a fila de boletos agendados (FIFO) e o log de auditoria do sistema.
"""

from formatacao import formatar_reais, formatar_numero, linha_separadora, linha_titulo
from conta import Conta, CATEGORIA_PADRAO, TAMANHO_PIN
from transacao import Transacao
from open_banking import Diretorio, ESCOPOS
from datetime import datetime


class Banco:
    def __init__(self, nome="ByteBank"):
        self.nome = nome
        self.contas = []
        self.fila_boletos = []      # Fila (FIFO) de boletos agendados
        self.registro_operacoes = []  # Log de auditoria de todas as operações
        self.diretorio = Diretorio()  # Instituições do Open Banking
        self.acessos_open_banking = []  # Trilha de acessos a dados externos

    # ---------------- Log de auditoria ----------------

    def registrar(self, conta, tipo, detalhes):
        self.registro_operacoes.append({
            "conta": conta.numero,
            "titular": conta.titular,
            "tipo": tipo,
            "detalhes": detalhes
        })

    def operacoes_da_conta(self, conta):
        return [op for op in self.registro_operacoes if op["conta"] == conta.numero]

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
        fim = len(self.contas) - 1
        comparacoes = 0

        while inicio <= fim:
            meio = (inicio + fim) // 2
            comparacoes += 1
            numero_do_meio = self.contas[meio].numero

            if numero_do_meio == numero:
                return self.contas[meio], comparacoes
            if numero_do_meio < numero:
                inicio = meio + 1   # procura na metade de cima
            else:
                fim = meio - 1      # procura na metade de baixo

        return None, comparacoes

    def busca_sequencial(self, numero):
        """Busca linear O(n), mantida para efeito de comparação."""
        comparacoes = 0
        for conta in self.contas:
            comparacoes += 1
            if conta.numero == numero:
                return conta, comparacoes
        return None, comparacoes

    def posicao_de_insercao(self, numero):
        """Encontra, por busca binária, onde inserir para manter a ordem."""
        inicio = 0
        fim = len(self.contas)
        while inicio < fim:
            meio = (inicio + fim) // 2
            if self.contas[meio].numero < numero:
                inicio = meio + 1
            else:
                fim = meio
        return inicio

    def buscar_por_cpf(self, cpf):
        """Busca sequencial O(n): a lista está ordenada por número de conta,
        não por CPF, então a busca binária não se aplica aqui."""
        for conta in self.contas:
            if conta.cpf == cpf:
                return conta
        return None

    def buscar_por_numero_ou_cpf(self, identificador):
        return self.buscar_por_numero(identificador) or self.buscar_por_cpf(identificador)

    def buscar_por_chave_pix(self, chave):
        for conta in self.contas:
            if conta.chave_pix == chave:
                return conta
        return None

    def adicionar_conta(self, conta):
        """Insere a conta na posição que mantém a lista ordenada por número.

        A ordenação é pré-requisito da busca binária: inserir no fim com
        append() quebraria o algoritmo.
        """
        self.contas.insert(self.posicao_de_insercao(conta.numero), conta)
        return conta

    def criar_conta(self, numero, titular, cpf, chave_pix, **kwargs):
        if self.buscar_por_numero(numero):
            return None, f"[ERRO] Já existe uma conta com o número {numero}."
        if self.buscar_por_cpf(cpf):
            return None, f"[ERRO] Já existe uma conta cadastrada com o CPF '{cpf}'."
        if self.buscar_por_chave_pix(chave_pix):
            return None, f"[ERRO] Já existe uma conta cadastrada com a chave PIX '{chave_pix}'."
        pin = kwargs.get("pin", "")
        if not Conta.pin_valido(pin):
            return None, f"[ERRO] O PIN deve ter {TAMANHO_PIN} dígitos numéricos."

        nova_conta = Conta(numero, titular, cpf, chave_pix, **kwargs)
        self.adicionar_conta(nova_conta)
        self.registrar(nova_conta, "criar_conta", f"titular: {titular}, CPF: {cpf}")
        return nova_conta, f"[OK] Conta criada com sucesso! Número: {numero}, Titular: {titular}"

    # ---------------- Operações de uma conta (com log) ----------------

    def executar(self, conta, metodo, *args):
        """Executa uma operação da conta e registra no log apenas se ela for concluída.

        O nome da operação no log é derivado do próprio método executado.
        """
        sucesso, mensagem = metodo(*args)
        if sucesso:
            self.registrar(conta, metodo.__name__, self._detalhe_ultima(conta))
        return sucesso, mensagem

    def _detalhe_ultima(self, conta):
        transacao = conta.ultima_transacao()
        if transacao is None:
            return ""
        return transacao.descricao()

    # ---------------- Transferência PIX ----------------

    def transferir_pix(self, conta_origem, chave_destino, valor):
        if valor <= 0:
            return False, "[RECUSADO] O valor da transferência deve ser positivo."

        conta_destino = self.buscar_por_chave_pix(chave_destino)
        if conta_destino is None:
            return False, f"[RECUSADO] Nenhuma conta encontrada com a chave PIX '{chave_destino}'."

        if conta_destino.numero == conta_origem.numero:
            return False, "[RECUSADO] Não é possível transferir para a própria conta."

        if valor > conta_origem.saldo:
            return False, f"[RECUSADO] Saldo insuficiente. Saldo disponível: {formatar_reais(conta_origem.saldo)}"

        conta_origem.saldo -= valor
        conta_destino.saldo += valor
        pontos = conta_origem.acumular_pontos(valor)

        conta_origem.empilhar(Transacao("PIX_ENVIADO", valor,
                                        conta_par=conta_destino.numero,
                                        pontos_gerados=pontos))
        conta_destino.empilhar(Transacao("PIX_RECEBIDO", valor, conta_par=conta_origem.numero))

        self.registrar(conta_origem, "pix_enviado", f"{formatar_reais(valor)} para {conta_destino.titular}")
        self.registrar(conta_destino, "pix_recebido", f"{formatar_reais(valor)} de {conta_origem.titular}")

        return True, (f"[OK] PIX de {formatar_reais(valor)} enviado para "
                      f"{conta_destino.titular} ({chave_destino}).\n"
                      f"Saldo atual: {formatar_reais(conta_origem.saldo)}\n"
                      f"+{formatar_numero(pontos)} BytePoints")

    # ---------------- Estorno (Pilha / LIFO) ----------------

    def estornar_ultima_transacao(self, conta):
        transacao = conta.ultima_transacao()
        if transacao is None:
            return False, "Não há transações no histórico para estornar."

        tipo = transacao.tipo
        conta_par = None
        transacao_espelho = None
        indice_espelho = None

        if tipo in ("PIX_ENVIADO", "PIX_RECEBIDO"):
            conta_par = self.buscar_por_numero(transacao.obter("conta_par"))
            if conta_par is None:
                return False, "[RECUSADO] A conta envolvida no PIX não foi encontrada. Estorno cancelado."
            tipo_espelho = "PIX_RECEBIDO" if tipo == "PIX_ENVIADO" else "PIX_ENVIADO"
            indice_espelho, transacao_espelho = conta_par.encontrar_transacao_espelho(
                tipo_espelho, transacao.valor, conta.numero)
            if transacao_espelho is None:
                return False, ("[RECUSADO] A transação correspondente não foi encontrada "
                               "na conta envolvida. Estorno cancelado.")

        contas_afetadas = [conta] if conta_par is None else [conta, conta_par]
        snapshots = {c.numero: c.snapshot() for c in contas_afetadas}

        conta.aplicar_reversao(transacao)
        if conta_par is not None:
            conta_par.aplicar_reversao(transacao_espelho)

        # A portabilidade moveu dinheiro de outra instituição: desfazer aqui
        # exige devolvê-lo lá, senão o valor desapareceria do sistema.
        instituicao_portabilidade = None
        if tipo == "PORTABILIDADE":
            instituicao_portabilidade = self.diretorio.buscar(transacao.obter("instituicao"))
            if instituicao_portabilidade is not None:
                instituicao_portabilidade.creditar(conta.cpf, transacao.valor)

        if any(c.tem_valor_negativo() for c in contas_afetadas):
            for c in contas_afetadas:
                c.restaurar(snapshots[c.numero])
            if instituicao_portabilidade is not None:
                instituicao_portabilidade.debitar(conta.cpf, transacao.valor)
            return False, "[RECUSADO] O estorno deixaria algum saldo negativo. Operação cancelada."

        conta.desempilhar()
        if conta_par is not None:
            conta_par.remover_transacao(indice_espelho)

        # Guarda o que foi desfeito para permitir refazer depois
        conta.empilhar_para_refazer({
            "transacao": transacao,
            "espelho": transacao_espelho,
            "conta_par": conta_par.numero if conta_par else None,
        })

        self.registrar(conta, "estorno", f"{tipo} de {transacao.descricao()}")
        return True, (f"[ESTORNO] Última transação desfeita: {tipo} de {transacao.descricao()}\n"
                      f"Saldo atual: {formatar_reais(conta.saldo)}")

    def refazer_ultima_transacao(self, conta):
        """Reaplica a última transação estornada (pilha de refazer, LIFO)."""
        item = conta.proximo_para_refazer()
        if item is None:
            return False, "Não há transações estornadas para refazer."

        transacao = item["transacao"]
        espelho = item["espelho"]
        conta_par = None

        if item["conta_par"] is not None:
            conta_par = self.buscar_por_numero(item["conta_par"])
            if conta_par is None:
                return False, ("[RECUSADO] A conta envolvida no PIX não foi encontrada. "
                               "Não é possível refazer.")

        contas_afetadas = [conta] if conta_par is None else [conta, conta_par]
        snapshots = {c.numero: c.snapshot() for c in contas_afetadas}

        if transacao.tipo == "PORTABILIDADE":
            instituicao = self.diretorio.buscar(transacao.obter("instituicao"))
            if instituicao is not None:
                sucesso, erro = instituicao.debitar(conta.cpf, transacao.valor)
                if not sucesso:
                    return False, f"[RECUSADO] Não é possível refazer: {erro}"

        conta.reaplicar(transacao)
        if conta_par is not None:
            conta_par.reaplicar(espelho)

        if any(c.tem_valor_negativo() for c in contas_afetadas):
            for c in contas_afetadas:
                c.restaurar(snapshots[c.numero])
            return False, "[RECUSADO] Refazer deixaria algum saldo negativo. Operação cancelada."

        conta.desempilhar_refazer()
        conta.reempilhar(transacao)
        if conta_par is not None:
            conta_par.reempilhar(espelho)

        self.registrar(conta, "refazer", f"{transacao.tipo} de {transacao.descricao()}")
        return True, (f"[REFEITO] Transação reaplicada: {transacao.tipo} de "
                      f"{transacao.descricao()}\n"
                      f"Saldo atual: {formatar_reais(conta.saldo)}")


    # ---------------- Open Banking ----------------

    def registrar_acesso(self, conta, instituicao, escopo):
        """Registra na trilha de auditoria um acesso a dados de outra instituição."""
        self.acessos_open_banking.append({
            "quando": datetime.now().isoformat(timespec="seconds"),
            "conta": conta.numero,
            "cpf": conta.cpf,
            "instituicao": instituicao.nome,
            "codigo": instituicao.codigo,
            "escopo": escopo,
        })

    def instituicoes_com_cliente(self, conta):
        """Instituições parceiras que têm conta no CPF do cliente."""
        return [i for i in self.diretorio.listar() if i.tem_cliente(conta.cpf)]

    def listar_instituicoes(self, conta):
        linhas = [linha_titulo("Instituições Participantes do Open Banking")]
        parceiras = self.diretorio.listar()
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
        instituicao = self.diretorio.buscar(codigo)
        if instituicao is None:
            return False, f"[RECUSADO] Instituição '{codigo}' não encontrada no diretório."

        sucesso, erro = conta.autorizar_compartilhamento(codigo, escopos)
        if not sucesso:
            return False, erro

        consentimento = conta.consentimentos[codigo]
        nomes = ", ".join(ESCOPOS.get(e, e) for e in escopos)
        self.registrar(conta, "open_banking_autorizar", f"{instituicao.nome} ({nomes})")
        return True, (f"[OK] Compartilhamento autorizado com {instituicao.nome}.\n"
                      f"Dados: {nomes}\n"
                      f"Válido até: {consentimento.valida_ate[:10]}")

    def revogar(self, conta, codigo):
        instituicao = self.diretorio.buscar(codigo)
        nome = instituicao.nome if instituicao else codigo

        sucesso, erro = conta.revogar_compartilhamento(codigo)
        if not sucesso:
            return False, erro

        self.registrar(conta, "open_banking_revogar", nome)
        return True, (f"[OK] Consentimento revogado para {nome}.\n"
                      "Os dados desta instituição não aparecem mais na visão consolidada.")

    def listar_consentimentos(self, conta):
        linhas = [linha_titulo(f"Consentimentos de {conta.titular}")]
        if not conta.consentimentos:
            linhas.append("Nenhum consentimento concedido até o momento.")
            linhas.append(linha_separadora())
            return "\n".join(linhas)

        for codigo, consentimento in conta.consentimentos.items():
            instituicao = self.diretorio.buscar(codigo)
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
        linhas.append(f"  {self.nome + ' (aqui)':<28} {formatar_reais(total):>16}")
        linhas.append(f"     conta: {formatar_reais(conta.saldo)} | "
                      f"cofrinhos: {formatar_reais(conta.total_em_cofrinhos)}")

        consultadas = 0
        sem_consentimento = []

        for instituicao in self.instituicoes_com_cliente(conta):
            if not conta.consentimento_valido(instituicao.codigo, "saldo"):
                sem_consentimento.append(instituicao.nome)
                continue

            dados = instituicao.dados_do_cliente(conta.cpf)
            self.registrar_acesso(conta, instituicao, "saldo")
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
        instituicao = self.diretorio.buscar(codigo)
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

        conta.saldo += valor
        conta.empilhar(Transacao("PORTABILIDADE", valor,
                                 instituicao=codigo, nome_instituicao=instituicao.nome))
        self.registrar_acesso(conta, instituicao, "portabilidade")
        self.registrar(conta, "open_banking_portabilidade",
                       f"{formatar_reais(valor)} de {instituicao.nome}")

        return True, (f"[OK] {formatar_reais(valor)} portados de {instituicao.nome}.\n"
                      f"Saldo atual: {formatar_reais(conta.saldo)}")

    def trilha_acessos(self, conta):
        acessos = [a for a in self.acessos_open_banking if a["conta"] == conta.numero]
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

    def agendar_boleto(self, conta, descricao, valor, categoria=CATEGORIA_PADRAO):
        if valor <= 0:
            return False, "[RECUSADO] O valor do boleto deve ser positivo."
        self.fila_boletos.append({
            "conta": conta.numero,
            "descricao": descricao,
            "valor": valor,
            "categoria": categoria
        })
        self.registrar(conta, "agendar_boleto", f"{descricao} - {formatar_reais(valor)}")
        return True, (f"[OK] Boleto '{descricao}' de {formatar_reais(valor)} agendado.\n"
                      f"Categoria: {categoria}")

    def fila_formatada(self):
        linhas = [linha_titulo("Fila de Boletos Agendados")]
        if not self.fila_boletos:
            linhas.append("Nenhum boleto agendado.")
        else:
            for posicao, boleto in enumerate(self.fila_boletos, start=1):
                linhas.append(f"  {posicao}º - Conta {boleto['conta']}: "
                              f"{boleto['descricao']} - {formatar_reais(boleto['valor'])}")
        linhas.append(linha_separadora())
        return "\n".join(linhas)

    def processar_boletos(self):
        if not self.fila_boletos:
            return False, "Não há boletos agendados na fila."

        linhas = [linha_titulo("Processando fila de boletos (ordem de chegada)")]
        pendentes = []

        while self.fila_boletos:
            boleto = self.fila_boletos.pop(0)  # FIFO
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

            self.registrar(conta, "pagar_boleto_agendado",
                           f"{boleto['descricao']} - {formatar_reais(boleto['valor'])}")
            linhas.append(f"[PAGO] {boleto['descricao']} - {formatar_reais(boleto['valor'])} "
                          f"debitado da conta {conta.numero} ({conta.titular})")

        self.fila_boletos = pendentes
        if pendentes:
            linhas.append(linha_titulo(f"{len(pendentes)} boleto(s) continuam pendentes na fila"))
        else:
            linhas.append(linha_titulo("Fila de boletos finalizada"))
        return True, "\n".join(linhas)

    # ---------------- Persistência ----------------

    def para_dicionario(self):
        """Converte o estado completo do banco em um dicionário."""
        return {
            "nome": self.nome,
            "contas": [conta.para_dicionario() for conta in self.contas],
            "fila_boletos": list(self.fila_boletos),
            "registro_operacoes": list(self.registro_operacoes),
            "diretorio": self.diretorio.para_dicionario(),
            "acessos_open_banking": list(self.acessos_open_banking),
        }

    @classmethod
    def de_dicionario(cls, dados):
        """Recria o banco a partir de um dicionário lido do arquivo."""
        banco = cls(dados.get("nome", "ByteBank"))
        contas = [Conta.de_dicionario(c) for c in dados.get("contas", [])]
        # A busca binária exige a lista ordenada por número de conta: a ordem
        # gravada no arquivo não é garantia suficiente.
        banco.contas = sorted(contas, key=lambda conta: conta.numero)
        banco.fila_boletos = list(dados.get("fila_boletos", []))
        banco.registro_operacoes = list(dados.get("registro_operacoes", []))
        banco.diretorio = Diretorio.de_dicionario(dados.get("diretorio"))
        banco.acessos_open_banking = list(dados.get("acessos_open_banking", []))
        return banco
