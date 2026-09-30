"""Camada de interface: exibe os menus, lê as entradas do usuário e
imprime as mensagens devolvidas pelas classes Conta e Banco.
"""

from formatacao import formatar_reais, linha_separadora, linha_titulo, LARGURA_PAINEL
from conta import (CATEGORIAS_GASTO, CATEGORIA_PADRAO,
                   TAXA_RENDIMENTO_MENSAL_PADRAO, TAMANHO_PIN)
from open_banking import ESCOPOS


class Interface:
    def __init__(self, banco):
        self.banco = banco

    # ---------------- Utilitários de entrada e saída ----------------

    @staticmethod
    def mostrar(mensagem):
        print(f"\n{mensagem}\n")

    @staticmethod
    def pedir_valor():
        while True:
            entrada = input("Digite o valor: R$ ").strip()
            try:
                return float(entrada)
            except ValueError:
                print("[ERRO] Valor inválido. Digite um número (ex: 100 ou 99.90).\n")

    @staticmethod
    def pedir_inteiro(mensagem):
        while True:
            entrada = input(mensagem).strip()
            try:
                return int(entrada)
            except ValueError:
                print("[ERRO] Valor inválido. Digite um número inteiro (ex: 3, 12).\n")

    @staticmethod
    def pedir_texto(mensagem):
        return input(mensagem).strip()

    @staticmethod
    def pedir_taxa():
        """Taxa mensal de rendimento em porcentagem; Enter usa a taxa padrão."""
        while True:
            entrada = input("Taxa de rendimento mensal em % (Enter para padrão): ").strip()
            if not entrada:
                return TAXA_RENDIMENTO_MENSAL_PADRAO
            try:
                return float(entrada.replace(",", ".")) / 100
            except ValueError:
                print("[ERRO] Digite um número (ex: 0.5 para 0,5% ao mês).\n")

    @staticmethod
    def escolher_cofrinho(conta):
        """Lista os cofrinhos e devolve o nome escolhido, ou None se não houver."""
        if not conta.cofrinhos:
            print("\nNenhum cofrinho criado ainda. Crie um primeiro.\n")
            return None

        nomes = list(conta.cofrinhos)
        print("\nCofrinhos disponíveis:")
        for numero, nome in enumerate(nomes, start=1):
            saldo = conta.cofrinhos[nome]["saldo"]
            print(f"  [{numero}] {nome} - {formatar_reais(saldo)}")

        while True:
            escolha = input(f"Escolha o cofrinho [1-{len(nomes)}] ou Enter para cancelar: ").strip()
            if not escolha:
                return None
            try:
                indice = int(escolha)
            except ValueError:
                print("[ERRO] Digite o número do cofrinho.\n")
                continue
            if 1 <= indice <= len(nomes):
                return nomes[indice - 1]
            print(f"[ERRO] Escolha um número entre 1 e {len(nomes)}.\n")

    @staticmethod
    def pedir_categoria():
        """Mostra as categorias disponíveis e devolve a escolhida."""
        print("\nCategorias disponíveis:")
        for numero, categoria in enumerate(CATEGORIAS_GASTO, start=1):
            print(f"  [{numero}] {categoria}")

        while True:
            escolha = input(f"Escolha a categoria [1-{len(CATEGORIAS_GASTO)}]: ").strip()
            if not escolha:
                return CATEGORIA_PADRAO
            try:
                indice = int(escolha)
            except ValueError:
                print("[ERRO] Digite o número da categoria.\n")
                continue
            if 1 <= indice <= len(CATEGORIAS_GASTO):
                return CATEGORIAS_GASTO[indice - 1]
            print(f"[ERRO] Escolha um número entre 1 e {len(CATEGORIAS_GASTO)}.\n")

    def cabecalho(self, conta, titulo=None):
        print()
        print(linha_titulo(f"{self.banco.nome} | Conta {conta.numero} - {conta.titular}"))
        if titulo:
            print(titulo.center(LARGURA_PAINEL).rstrip())
        print(linha_separadora("-"))

    @staticmethod
    def opcao_invalida():
        print("\n[ERRO] Opção inválida. Tente novamente.\n")

    # ---------------- Login ----------------

    def login(self):
        print(linha_titulo(f"BEM-VINDO AO {self.banco.nome.upper()}"))
        while True:
            identificador = self.pedir_texto("Digite o número da conta ou o CPF: ")
            conta = self.banco.buscar_por_numero_ou_cpf(identificador)

            if conta is None:
                print("[ERRO] Conta não encontrada. Tente novamente.\n")
                continue

            if conta.bloqueada:
                self.tratar_conta_bloqueada(conta)
                continue

            if self.autenticar(conta):
                return conta

            # Se as tentativas se esgotaram agora, oferece o desbloqueio na hora
            if conta.bloqueada:
                self.tratar_conta_bloqueada(conta)

    def autenticar(self, conta):
        """Pede o PIN até acertar, esgotar as tentativas ou o usuário desistir."""
        while True:
            pin = self.pedir_texto(f"Digite o PIN de {conta.titular} "
                                   f"(Enter para voltar): ")
            if not pin:
                print()
                return False

            autenticado, mensagem = conta.autenticar(pin)
            if autenticado:
                print(f"\nAcesso liberado. Olá, {conta.titular}.\n")
                return True

            print(mensagem + "\n")
            if conta.bloqueada:
                return False

    def tratar_conta_bloqueada(self, conta):
        """Oferece o desbloqueio de uma conta bloqueada. Devolve True se liberou."""
        print(f"\n[BLOQUEADA] A conta de {conta.titular} está bloqueada "
              f"por excesso de tentativas.")
        resposta = self.pedir_texto("Deseja desbloquear informando o CPF? (s/n): ").lower()
        if resposta != "s":
            print()
            return False

        cpf = self.pedir_texto("Digite o CPF do titular: ")
        novo_pin = self.pedir_texto(f"Cadastre um novo PIN de {TAMANHO_PIN} dígitos: ")
        sucesso, mensagem = conta.desbloquear(cpf, novo_pin)
        print(f"\n{mensagem}\n")
        return sucesso

    # ---------------- Submenus ----------------    # ---------------- Submenus ----------------

    def submenu_conta(self, conta):
        while True:
            self.cabecalho(conta, "CONTA E SALDO")
            print("[1] Consultar Saldo")
            print("[2] Depositar")
            print("[3] Sacar")
            print("[4] Ver Extrato (Pilha)")
            print("[5] Estornar Última Transação")
            print("[6] Refazer Transação Estornada")
            print("[7] Histórico de Operações")
            print("[8] Relatório de Gastos por Categoria")
            print("[0] Voltar")
            print(linha_separadora())

            match self.pedir_texto("Escolha uma opção: "):
                case "1":
                    self.mostrar(conta.resumo_saldo())
                case "2":
                    valor = self.pedir_valor()
                    _, mensagem = self.banco.executar(conta, conta.depositar, valor)
                    self.mostrar(mensagem)
                case "3":
                    valor = self.pedir_valor()
                    _, mensagem = self.banco.executar(conta, conta.sacar, valor)
                    self.mostrar(mensagem)
                case "4":
                    self.mostrar(conta.extrato())
                case "5":
                    _, mensagem = self.banco.estornar_ultima_transacao(conta)
                    self.mostrar(mensagem)
                case "6":
                    _, mensagem = self.banco.refazer_ultima_transacao(conta)
                    self.mostrar(mensagem)
                case "7":
                    self.mostrar(self.banco.historico_formatado(conta))
                case "8":
                    self.mostrar(conta.relatorio_gastos())
                case "0":
                    return
                case _:
                    self.opcao_invalida()

    def submenu_transferencias(self, conta):
        while True:
            self.cabecalho(conta, "TRANSFERÊNCIAS E PAGAMENTOS")
            print("[1] Transferir (PIX)")
            print("[2] Pagar Boleto Agora")
            print("[3] Agendar Boleto (Fila)")
            print("[4] Ver Fila de Boletos")
            print("[5] Processar Boletos Agendados")
            print("[0] Voltar")
            print(linha_separadora())

            match self.pedir_texto("Escolha uma opção: "):
                case "1":
                    chave = self.pedir_texto("Digite a chave PIX de destino: ")
                    valor = self.pedir_valor()
                    _, mensagem = self.banco.transferir_pix(conta, chave, valor)
                    self.mostrar(mensagem)
                case "2":
                    descricao = self.pedir_texto("Descrição do boleto (ex: Conta de Luz): ")
                    valor = self.pedir_valor()
                    categoria = self.pedir_categoria()
                    _, mensagem = self.banco.executar(conta, conta.pagar_boleto,
                                                      descricao, valor, categoria)
                    self.mostrar(mensagem)
                case "3":
                    descricao = self.pedir_texto("Descrição do boleto (ex: Conta de Luz): ")
                    valor = self.pedir_valor()
                    categoria = self.pedir_categoria()
                    _, mensagem = self.banco.agendar_boleto(conta, descricao, valor, categoria)
                    self.mostrar(mensagem)
                case "4":
                    self.mostrar(self.banco.fila_formatada())
                case "5":
                    _, mensagem = self.banco.processar_boletos()
                    self.mostrar(mensagem)
                case "0":
                    return
                case _:
                    self.opcao_invalida()

    def submenu_cofrinhos(self, conta):
        while True:
            self.cabecalho(conta, "COFRINHOS (CAIXINHAS)")
            print("[1] Ver Cofrinhos")
            print("[2] Criar Cofrinho")
            print("[3] Guardar Dinheiro")
            print("[4] Resgatar Dinheiro")
            print("[5] Simular Rendimento")
            print("[6] Aplicar Rendimento")
            print("[7] Excluir Cofrinho")
            print("[0] Voltar")
            print(linha_separadora())

            match self.pedir_texto("Escolha uma opção: "):
                case "1":
                    self.mostrar(conta.resumo_cofrinhos())
                case "2":
                    nome = self.pedir_texto("Nome do cofrinho (ex: Viagem): ")
                    taxa = self.pedir_taxa()
                    _, mensagem = conta.criar_cofrinho(nome, taxa)
                    self.mostrar(mensagem)
                case "3":
                    nome = self.escolher_cofrinho(conta)
                    if nome:
                        valor = self.pedir_valor()
                        _, mensagem = self.banco.executar(conta, conta.guardar_no_cofrinho,
                                                          nome, valor)
                        self.mostrar(mensagem)
                case "4":
                    nome = self.escolher_cofrinho(conta)
                    if nome:
                        valor = self.pedir_valor()
                        _, mensagem = self.banco.executar(conta, conta.resgatar_do_cofrinho,
                                                          nome, valor)
                        self.mostrar(mensagem)
                case "5":
                    nome = self.escolher_cofrinho(conta)
                    if nome:
                        meses = self.pedir_inteiro("Período em meses: ")
                        _, mensagem = conta.simular_rendimento(nome, meses)
                        self.mostrar(mensagem)
                case "6":
                    nome = self.escolher_cofrinho(conta)
                    if nome:
                        meses = self.pedir_inteiro("Período em meses: ")
                        _, mensagem = self.banco.executar(conta, conta.aplicar_rendimento,
                                                          nome, meses)
                        self.mostrar(mensagem)
                case "7":
                    nome = self.escolher_cofrinho(conta)
                    if nome:
                        _, mensagem = conta.excluir_cofrinho(nome)
                        self.mostrar(mensagem)
                case "0":
                    return
                case _:
                    self.opcao_invalida()

    def submenu_cartao_credito(self, conta):
        while True:
            self.cabecalho(conta, "CARTÃO DE CRÉDITO")
            print("[1] Consultar Limite e Fatura")
            print("[2] Comprar no Cartão de Crédito")
            print("[3] Pagar Fatura")
            print("[0] Voltar")
            print(linha_separadora())

            match self.pedir_texto("Escolha uma opção: "):
                case "1":
                    self.mostrar(conta.resumo_cartao())
                case "2":
                    valor = self.pedir_valor()
                    categoria = self.pedir_categoria()
                    _, mensagem = self.banco.executar(conta, conta.comprar_no_cartao,
                                                      valor, categoria)
                    self.mostrar(mensagem)
                case "3":
                    valor = self.pedir_valor()
                    _, mensagem = self.banco.executar(conta, conta.pagar_fatura, valor)
                    self.mostrar(mensagem)
                case "0":
                    return
                case _:
                    self.opcao_invalida()

    def submenu_moedas(self, conta):
        while True:
            self.cabecalho(conta, "MOEDAS ESTRANGEIRAS")
            print("[1] Consultar Saldo em Moedas Estrangeiras")
            print("[2] Comprar Moeda Estrangeira")
            print("[3] Vender Moeda Estrangeira")
            print("[4] Câmbio entre Moedas")
            print("[0] Voltar")
            print(linha_separadora())

            match self.pedir_texto("Escolha uma opção: "):
                case "1":
                    self.mostrar(conta.resumo_moedas())
                case "2":
                    moeda = self.pedir_texto("Digite a moeda a ser comprada (dolar, euro, yuan): ").lower()
                    valor = self.pedir_valor()
                    _, mensagem = self.banco.executar(conta, conta.comprar_moeda, moeda, valor)
                    self.mostrar(mensagem)
                case "3":
                    moeda = self.pedir_texto("Digite a moeda a ser vendida (dolar, euro, yuan): ").lower()
                    valor = self.pedir_valor()
                    _, mensagem = self.banco.executar(conta, conta.vender_moeda, moeda, valor)
                    self.mostrar(mensagem)
                case "4":
                    origem = self.pedir_texto("Digite a moeda de origem (real, dolar, euro, yuan): ").lower()
                    destino = self.pedir_texto("Digite a moeda de destino (real, dolar, euro, yuan): ").lower()
                    valor = self.pedir_valor()
                    _, mensagem = self.banco.executar(conta, conta.cambiar, origem, destino, valor)
                    self.mostrar(mensagem)
                case "0":
                    return
                case _:
                    self.opcao_invalida()

    def submenu_emprestimos(self, conta):
        while True:
            self.cabecalho(conta, "EMPRÉSTIMOS")
            print("[1] Consultar Crédito Pré-Aprovado")
            print("[2] Simular Empréstimo")
            print("[3] Contratar Empréstimo")
            print("[4] Consultar Dívida")
            print("[5] Pagar Empréstimo")
            print("[0] Voltar")
            print(linha_separadora())

            match self.pedir_texto("Escolha uma opção: "):
                case "1":
                    self.mostrar(conta.resumo_credito_pre_aprovado())
                case "2":
                    valor = self.pedir_valor()
                    parcelas = self.pedir_inteiro("Digite o número de parcelas: ")
                    _, mensagem = conta.simular_emprestimo(valor, parcelas)
                    self.mostrar(mensagem)
                case "3":
                    valor = self.pedir_valor()
                    parcelas = self.pedir_inteiro("Digite o número de parcelas: ")
                    _, mensagem = self.banco.executar(conta, conta.contratar_emprestimo, valor, parcelas)
                    self.mostrar(mensagem)
                case "4":
                    self.mostrar(conta.resumo_emprestimo())
                case "5":
                    valor = self.pedir_valor()
                    _, mensagem = self.banco.executar(conta, conta.pagar_emprestimo, valor)
                    self.mostrar(mensagem)
                case "0":
                    return
                case _:
                    self.opcao_invalida()

    def submenu_fidelidade(self, conta):
        while True:
            self.cabecalho(conta, "PROGRAMA DE FIDELIDADE (BYTEPOINTS)")
            print("[1] Consultar Pontos")
            print("[2] Resgatar Pontos (cashback)")
            print("[0] Voltar")
            print(linha_separadora())

            match self.pedir_texto("Escolha uma opção: "):
                case "1":
                    self.mostrar(conta.resumo_fidelidade())
                case "2":
                    pontos = self.pedir_inteiro("Digite a quantidade de pontos a resgatar: ")
                    _, mensagem = self.banco.executar(conta, conta.resgatar_pontos, pontos)
                    self.mostrar(mensagem)
                case "0":
                    return
                case _:
                    self.opcao_invalida()

    def escolher_instituicao(self, conta, apenas_com_conta=False):
        """Lista as instituições e devolve o código escolhido, ou None."""
        parceiras = (self.banco.instituicoes_com_cliente(conta) if apenas_com_conta
                     else self.banco.diretorio.listar())
        if not parceiras:
            print("\nNenhuma instituição disponível.\n")
            return None

        print("\nInstituições:")
        for numero, instituicao in enumerate(parceiras, start=1):
            print(f"  [{numero}] {instituicao.nome} ({instituicao.codigo})")

        while True:
            escolha = input(f"Escolha [1-{len(parceiras)}] ou Enter para cancelar: ").strip()
            if not escolha:
                return None
            try:
                indice = int(escolha)
            except ValueError:
                print("[ERRO] Digite o número da instituição.\n")
                continue
            if 1 <= indice <= len(parceiras):
                return parceiras[indice - 1].codigo
            print(f"[ERRO] Escolha um número entre 1 e {len(parceiras)}.\n")

    @staticmethod
    def escolher_escopos():
        """Permite marcar quais dados serão compartilhados."""
        itens = list(ESCOPOS.items())
        print("\nQuais dados deseja compartilhar?")
        for numero, (_, descricao) in enumerate(itens, start=1):
            print(f"  [{numero}] {descricao}")

        entrada = input("Digite os números separados por vírgula (ex: 1,2): ").strip()
        escolhidos = []
        for parte in entrada.split(","):
            parte = parte.strip()
            if not parte.isdigit():
                continue
            indice = int(parte)
            if 1 <= indice <= len(itens):
                codigo = itens[indice - 1][0]
                if codigo not in escolhidos:
                    escolhidos.append(codigo)
        return escolhidos

    def submenu_open_banking(self, conta):
        while True:
            self.cabecalho(conta, "OPEN BANKING")
            print("[1] Instituições Participantes")
            print("[2] Autorizar Compartilhamento")
            print("[3] Meus Consentimentos")
            print("[4] Revogar Consentimento")
            print("[5] Visão Consolidada do Patrimônio")
            print("[6] Portabilidade de Saldo")
            print("[7] Trilha de Acessos")
            print("[0] Voltar")
            print(linha_separadora())

            match self.pedir_texto("Escolha uma opção: "):
                case "1":
                    self.mostrar(self.banco.listar_instituicoes(conta))
                case "2":
                    codigo = self.escolher_instituicao(conta)
                    if codigo:
                        escopos = self.escolher_escopos()
                        _, mensagem = self.banco.autorizar(conta, codigo, escopos)
                        self.mostrar(mensagem)
                case "3":
                    self.mostrar(self.banco.listar_consentimentos(conta))
                case "4":
                    codigo = self.escolher_instituicao(conta)
                    if codigo:
                        _, mensagem = self.banco.revogar(conta, codigo)
                        self.mostrar(mensagem)
                case "5":
                    self.mostrar(self.banco.visao_consolidada(conta))
                case "6":
                    codigo = self.escolher_instituicao(conta, apenas_com_conta=True)
                    if codigo:
                        valor = self.pedir_valor()
                        _, mensagem = self.banco.portar_saldo(conta, codigo, valor)
                        self.mostrar(mensagem)
                case "7":
                    self.mostrar(self.banco.trilha_acessos(conta))
                case "0":
                    return
                case _:
                    self.opcao_invalida()

    def submenu_cadastro(self, conta):
        while True:
            self.cabecalho(conta, "CADASTRO E ACESSO")
            print("[1] Cadastrar Nova Conta")
            print("[2] Alterar meu PIN")
            print("[3] Trocar de Conta")
            print("[0] Voltar")
            print(linha_separadora())

            match self.pedir_texto("Escolha uma opção: "):
                case "1":
                    numero = self.pedir_texto("Digite o número da nova conta: ")
                    titular = self.pedir_texto("Digite o nome do titular: ")
                    cpf = self.pedir_texto("Digite o CPF do titular: ")
                    chave_pix = self.pedir_texto("Digite a chave PIX: ")
                    pin = self.pedir_texto(f"Defina o PIN de {TAMANHO_PIN} dígitos: ")
                    _, mensagem = self.banco.criar_conta(numero, titular, cpf, chave_pix, pin=pin)
                    self.mostrar(mensagem)
                case "2":
                    atual = self.pedir_texto("Digite o PIN atual: ")
                    novo = self.pedir_texto(f"Digite o novo PIN de {TAMANHO_PIN} dígitos: ")
                    _, mensagem = conta.alterar_pin(atual, novo)
                    self.mostrar(mensagem)
                case "3":
                    return "trocar"
                case "0":
                    return None
                case _:
                    self.opcao_invalida()

    # ---------------- Menu principal ----------------

    def menu_principal(self, conta):
        while True:
            self.cabecalho(conta)
            print("[1] Conta e Saldo")
            print("[2] Transferências e Pagamentos")
            print("[3] Cofrinhos (Caixinhas)")
            print("[4] Cartão de Crédito")
            print("[5] Moedas Estrangeiras")
            print("[6] Empréstimos")
            print("[7] Programa de Fidelidade")
            print("[8] Open Banking")
            print("[9] Cadastro e Acesso")
            print("[0] Sair")
            print(linha_separadora())

            match self.pedir_texto("Escolha uma opção: "):
                case "1":
                    self.submenu_conta(conta)
                case "2":
                    self.submenu_transferencias(conta)
                case "3":
                    self.submenu_cofrinhos(conta)
                case "4":
                    self.submenu_cartao_credito(conta)
                case "5":
                    self.submenu_moedas(conta)
                case "6":
                    self.submenu_emprestimos(conta)
                case "7":
                    self.submenu_fidelidade(conta)
                case "8":
                    self.submenu_open_banking(conta)
                case "9":
                    if self.submenu_cadastro(conta) == "trocar":
                        return "trocar"
                case "0":
                    return "sair"
                case _:
                    self.opcao_invalida()

    def executar(self):
        while True:
            conta = self.login()
            if self.menu_principal(conta) == "sair":
                print(f"\nObrigado por usar o {self.banco.nome}. Até logo!")
                break
