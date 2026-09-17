contas = [
    {"numero": "0001", "titular": "Amanda Silva", "chave_pix": "amanda@email.com", "saldo": 1000.00, "carteira_investimentos": 5000.00, "limite_cartao_credito": 4000.00, "fatura_cartao_credito": 0.00, "divida_emprestimo": 0.00, "saldo_dolar": 200.00, "saldo_euro": 150.00, "saldo_yuan": 1000.00},
    {"numero": "0002", "titular": "Caio Ferreira", "chave_pix": "caio@email.com", "saldo": 2500.50, "carteira_investimentos": 3000.00, "limite_cartao_credito": 2500.00, "fatura_cartao_credito": 0.00, "divida_emprestimo": 0.00, "saldo_dolar": 300.00, "saldo_euro": 200.00, "saldo_yuan": 1500.00},
    {"numero": "0003", "titular": "Douglas Alves", "chave_pix": "douglas@email.com", "saldo": 320.00, "carteira_investimentos": 1000.00, "limite_cartao_credito": 3000.00, "fatura_cartao_credito": 0.00, "divida_emprestimo": 0.00, "saldo_dolar": 100.00, "saldo_euro": 80.00, "saldo_yuan": 500.00},

]
conversao_moedas = {
    "dolar": 5.00,  # 1 Dólar = 5 Reais
    "euro": 6.00,   # 1 Euro = 6 Reais
    "yuan": 0.75    # 1 Yuan = 0.75 Reais
}

MOEDAS_VALIDAS = list(conversao_moedas.keys()) + ["real"]
TAXA_JUROS_EMPRESTIMO_MENSAL = 0.02  # 2% ao mês


def chave_saldo_moeda(moeda):
    if moeda == "real":
        return "saldo"
    return f"saldo_{moeda}"


def taxa_moeda(moeda):
    return conversao_moedas.get(moeda, 1.0)


def formatar_valor_moeda(moeda, valor):
    if moeda == "real":
        return f"R$ {valor:.2f}"
    return f"{valor:.2f} {moeda}"


def buscar_conta_por_numero(numero):
    for conta in contas:
        if conta["numero"] == numero:
            return conta
    return None

def criar_conta(numero, titular, chave_pix, saldo_inicial=0.0, carteira_investimentos=0.0, limite_cartao_credito=0.0):
    if buscar_conta_por_numero(numero):
        print(f"\n[ERRO] Já existe uma conta com o número {numero}.\n")
        return None
    if buscar_conta_por_chave_pix(chave_pix):
        print(f"\n[ERRO] Já existe uma conta cadastrada com a chave PIX '{chave_pix}'.\n")
        return None
    nova_conta = {
        "numero": numero,
        "titular": titular,
        "chave_pix": chave_pix,
        "saldo": saldo_inicial,
        "carteira_investimentos": carteira_investimentos,
        "limite_cartao_credito": limite_cartao_credito,
        "fatura_cartao_credito": 0.0,
        "divida_emprestimo": 0.0,
        "saldo_dolar": 0.0,
        "saldo_euro": 0.0,
        "saldo_yuan": 0.0
    }
    contas.append(nova_conta)
    print(f"\n[OK] Conta criada com sucesso! Número: {numero}, Titular: {titular}\n")
    return nova_conta


def buscar_conta_por_chave_pix(chave):
    for conta in contas:
        if conta["chave_pix"] == chave:
            return conta
    return None


def consultar_saldo(conta):
    print(f"\nTitular: {conta['titular']}")
    print(f"Conta: {conta['numero']}")
    print(f"Saldo atual: R$ {conta['saldo']:.2f}\n")

def consultar_saldo_moedas(conta):
    print(f"\nTitular: {conta['titular']}")
    print(f"Conta: {conta['numero']}")
    print(f"Saldo em Dólar: ${conta['saldo_dolar']:.2f} (R$ {conta['saldo_dolar'] * conversao_moedas['dolar']:.2f})")
    print(f"Saldo em Euro: €{conta['saldo_euro']:.2f} (R$ {conta['saldo_euro'] * conversao_moedas['euro']:.2f})")
    print(f"Saldo em Yuan: ¥{conta['saldo_yuan']:.2f} (R$ {conta['saldo_yuan'] * conversao_moedas['yuan']:.2f})\n")

def comprar_moeda(conta, moeda, valor_reais):
    if moeda not in conversao_moedas:
        print(f"\n[ERRO] Moeda '{moeda}' não suportada. Opções: dolar, euro, yuan.\n")
        return
    cambio_entre_moedas(conta, "real", moeda, valor_reais)


def vender_moeda(conta, moeda, quantidade_moeda):
    if moeda not in conversao_moedas:
        print(f"\n[ERRO] Moeda '{moeda}' não suportada. Opções: dolar, euro, yuan.\n")
        return
    cambio_entre_moedas(conta, moeda, "real", quantidade_moeda)


def cambio_entre_moedas(conta, moeda_origem, moeda_destino, quantidade_origem):
    if moeda_origem not in MOEDAS_VALIDAS or moeda_destino not in MOEDAS_VALIDAS:
        print(f"\n[ERRO] Moeda não suportada. Opções: real, dolar, euro, yuan.\n")
        return

    if moeda_origem == moeda_destino:
        print("\n[RECUSADO] A moeda de origem e a de destino devem ser diferentes.\n")
        return

    if quantidade_origem <= 0:
        print("\n[RECUSADO] A quantidade a ser convertida deve ser positiva.\n")
        return

    chave_origem = chave_saldo_moeda(moeda_origem)
    chave_destino = chave_saldo_moeda(moeda_destino)

    saldo_origem = conta[chave_origem]
    if quantidade_origem > saldo_origem:
        print(f"\n[RECUSADO] Saldo insuficiente em {moeda_origem}. Saldo disponível: {formatar_valor_moeda(moeda_origem, saldo_origem)}\n")
        return

    valor_reais = quantidade_origem * taxa_moeda(moeda_origem)
    quantidade_destino = valor_reais / taxa_moeda(moeda_destino)

    conta[chave_origem] -= quantidade_origem
    conta[chave_destino] += quantidade_destino

    print(f"\n[OK] Conversão de {formatar_valor_moeda(moeda_origem, quantidade_origem)} para {formatar_valor_moeda(moeda_destino, quantidade_destino)} realizada.")
    print(f"Saldo atual em {moeda_origem}: {formatar_valor_moeda(moeda_origem, conta[chave_origem])}")
    print(f"Saldo atual em {moeda_destino}: {formatar_valor_moeda(moeda_destino, conta[chave_destino])}\n")

def consultar_carteira_investimentos(conta):
    print(f"\nTitular: {conta['titular']}")
    print(f"Conta: {conta['numero']}")
    print(f"Saldo da carteira de investimentos: R$ {conta['carteira_investimentos']:.2f}\n")

def consultar_limite_cartao_credito(conta):
    limite_disponivel = conta["limite_cartao_credito"] - conta["fatura_cartao_credito"]
    print(f"\nTitular: {conta['titular']}")
    print(f"Conta: {conta['numero']}")
    print(f"Limite total do cartão de crédito: R$ {conta['limite_cartao_credito']:.2f}")
    print(f"Limite disponível: R$ {limite_disponivel:.2f}\n")

def comprar_cartao_credito(conta, valor):
    if valor <= 0:
        print("\n[RECUSADO] O valor da compra deve ser positivo.\n")
        return
    limite_disponivel = conta["limite_cartao_credito"] - conta["fatura_cartao_credito"]
    if valor > limite_disponivel:
        print(f"\n[RECUSADO] Limite insuficiente no cartão de crédito. Limite disponível: R$ {limite_disponivel:.2f}\n")
        return
    conta["fatura_cartao_credito"] += valor
    limite_disponivel = conta["limite_cartao_credito"] - conta["fatura_cartao_credito"]
    print(f"\n[OK] Compra de R$ {valor:.2f} realizada no cartão de crédito.")
    print(f"Fatura atual: R$ {conta['fatura_cartao_credito']:.2f}")
    print(f"Limite disponível: R$ {limite_disponivel:.2f}\n")

def consultar_fatura_cartao_credito(conta):
    fatura = conta["fatura_cartao_credito"]
    print(f"\nTitular: {conta['titular']}")
    print(f"Conta: {conta['numero']}")
    print(f"Fatura atual do cartão de crédito: R$ {fatura:.2f}\n")

def simular_emprestimo(conta, valor, parcelas):
    if valor <= 0 or parcelas <= 0:
        print("\n[RECUSADO] O valor e o número de parcelas devem ser positivos.\n")
        return
    valor_parcela = (valor * (1 + TAXA_JUROS_EMPRESTIMO_MENSAL) ** parcelas) / parcelas
    print(f"\nSimulação de Empréstimo:")
    print(f"Valor solicitado: R$ {valor:.2f}")
    print(f"Número de parcelas: {parcelas}")
    print(f"Valor da parcela: R$ {valor_parcela:.2f}")
    print(f"Total a pagar: R$ {valor_parcela * parcelas:.2f}\n")

def contratar_emprestimo(conta, valor, parcelas):
    if valor <= 0 or parcelas <= 0:
        print("\n[RECUSADO] O valor e o número de parcelas devem ser positivos.\n")
        return
    valor_parcela = (valor * (1 + TAXA_JUROS_EMPRESTIMO_MENSAL) ** parcelas) / parcelas
    total_a_pagar = valor_parcela * parcelas
    conta["saldo"] += valor
    conta["divida_emprestimo"] += total_a_pagar
    print(f"\n[OK] Empréstimo de R$ {valor:.2f} contratado.")
    print(f"Número de parcelas: {parcelas}")
    print(f"Valor da parcela: R$ {valor_parcela:.2f}")
    print(f"Total a pagar: R$ {total_a_pagar:.2f}")
    print(f"Saldo atual: R$ {conta['saldo']:.2f}")
    print(f"Dívida total de empréstimos: R$ {conta['divida_emprestimo']:.2f}\n")

def consultar_divida_emprestimo(conta):
    print(f"\nTitular: {conta['titular']}")
    print(f"Conta: {conta['numero']}")
    print(f"Dívida total de empréstimos: R$ {conta['divida_emprestimo']:.2f}\n")

def pagar_emprestimo(conta, valor):
    if valor <= 0:
        print("\n[RECUSADO] O valor do pagamento deve ser positivo.\n")
        return
    divida_atual = conta["divida_emprestimo"]
    if divida_atual == 0:
        print("\nNão há dívida de empréstimo pendente nesta conta.\n")
        return
    if valor > divida_atual:
        print(f"\n[RECUSADO] O valor informado é maior que a dívida atual. Dívida atual: R$ {divida_atual:.2f}\n")
        return
    if valor > conta["saldo"]:
        print(f"\n[RECUSADO] Saldo insuficiente para pagar o empréstimo. Saldo disponível: R$ {conta['saldo']:.2f}\n")
        return
    conta["saldo"] -= valor
    conta["divida_emprestimo"] -= valor
    print(f"\n[OK] Pagamento de R$ {valor:.2f} realizado no empréstimo.")
    print(f"Saldo atual: R$ {conta['saldo']:.2f}")
    print(f"Dívida restante: R$ {conta['divida_emprestimo']:.2f}\n")
    
def pagar_fatura_cartao_credito(conta, valor):
    if valor <= 0:
        print("\n[RECUSADO] O valor do pagamento deve ser positivo.\n")
        return
    fatura_atual = conta["fatura_cartao_credito"]
    if fatura_atual == 0:
        print("\nNão há fatura pendente para pagar nesta conta.\n")
        return
    if valor > fatura_atual:
        print(f"\n[RECUSADO] O valor informado é maior que a fatura atual. Fatura atual: R$ {fatura_atual:.2f}\n")
        return
    if valor > conta["saldo"]:
        print(f"\n[RECUSADO] Saldo insuficiente para pagar a fatura. Saldo disponível: R$ {conta['saldo']:.2f}\n")
        return
    conta["saldo"] -= valor
    conta["fatura_cartao_credito"] -= valor
    print(f"\n[OK] Pagamento de R$ {valor:.2f} realizado na fatura do cartão de crédito.")
    print(f"Saldo atual: R$ {conta['saldo']:.2f}")
    print(f"Fatura restante: R$ {conta['fatura_cartao_credito']:.2f}\n")

def investir(conta, valor):
    if valor <= 0:
        print("\n[RECUSADO] O valor do investimento deve ser positivo.\n")
        return
    if valor > conta["saldo"]:
        print(f"\n[RECUSADO] Saldo insuficiente para investir. Saldo disponível: R$ {conta['saldo']:.2f}\n")
        return
    conta["saldo"] -= valor
    conta["carteira_investimentos"] += valor
    print(f"\n[OK] Investimento de R$ {valor:.2f} realizado.")
    print(f"Saldo atual: R$ {conta['saldo']:.2f}")
    print(f"Saldo da carteira de investimentos: R$ {conta['carteira_investimentos']:.2f}\n")

def resgatar_investimento(conta, valor):
    if valor <= 0:
        print("\n[RECUSADO] O valor do resgate deve ser positivo.\n")
        return
    if valor > conta["carteira_investimentos"]:
        print(f"\n[RECUSADO] Saldo insuficiente na carteira de investimentos. Saldo disponível: R$ {conta['carteira_investimentos']:.2f}\n")
        return
    conta["carteira_investimentos"] -= valor
    conta["saldo"] += valor
    print(f"\n[OK] Resgate de R$ {valor:.2f} realizado.")
    print(f"Saldo atual: R$ {conta['saldo']:.2f}")
    print(f"Saldo da carteira de investimentos: R$ {conta['carteira_investimentos']:.2f}\n")


def depositar(conta, valor):
    if valor <= 0:
        print("\n[RECUSADO] O valor do depósito deve ser positivo.\n")
        return
    conta["saldo"] += valor
    print(f"\n[OK] Depósito de R$ {valor:.2f} realizado.")
    print(f"Saldo atual: R$ {conta['saldo']:.2f}\n")



def sacar(conta, valor):
    if valor <= 0:
        print("\n[RECUSADO] O valor do saque deve ser positivo.\n")
        return
    if valor > conta["saldo"]:
        print(f"\n[RECUSADO] Saldo insuficiente. Saldo disponível: R$ {conta['saldo']:.2f}\n")
        return
    conta["saldo"] -= valor
    print(f"\n[OK] Saque de R$ {valor:.2f} realizado.")
    print(f"Saldo atual: R$ {conta['saldo']:.2f}\n")


def transferir_pix(conta_origem, chave_destino, valor):
    if valor <= 0:
        print("\n[RECUSADO] O valor da transferência deve ser positivo.\n")
        return

    conta_destino = buscar_conta_por_chave_pix(chave_destino)
    if conta_destino is None:
        print(f"\n[RECUSADO] Nenhuma conta encontrada com a chave PIX '{chave_destino}'.\n")
        return

    if conta_destino["numero"] == conta_origem["numero"]:
        print("\n[RECUSADO] Não é possível transferir para a própria conta.\n")
        return

    if valor > conta_origem["saldo"]:
        print(f"\n[RECUSADO] Saldo insuficiente. Saldo disponível: R$ {conta_origem['saldo']:.2f}\n")
        return

    conta_origem["saldo"] -= valor
    conta_destino["saldo"] += valor

    print(f"\n[OK] PIX de R$ {valor:.2f} enviado para {conta_destino['titular']} ({chave_destino}).")
    print(f"Saldo atual: R$ {conta_origem['saldo']:.2f}\n")


def exibir_menu(conta):
    print("=" * 45)
    print(f"   ByteBank | Conta {conta['numero']} - {conta['titular']}")
    print("=" * 45)
    print("[1] Consultar Saldo")
    print("[2] Depositar")
    print("[3] Sacar")
    print("[4] Transferir (PIX)")
    print("[5] Trocar de Conta")
    print("[6] Consultar Carteira de Investimentos")
    print("[7] Investir")
    print("[8] Resgatar Investimento")
    print("[9] Consultar Limite do Cartão de Crédito")
    print("[10] Cadastrar Nova Conta")
    print("[11] Consultar Fatura do Cartão de Crédito")
    print("[12] Pagar Fatura do Cartão de Crédito")
    print("[13] Consultar Saldo em Moedas Estrangeiras")
    print("[14] Comprar Moeda Estrangeira")
    print("[15] Câmbio entre Moedas Estrangeiras")
    print("[16] Vender Moeda Estrangeira (converter para Saldo Original)")
    print("[17] Comprar no Cartão de Crédito")
    print("[18] Simular Empréstimo")
    print("[19] Contratar Empréstimo")
    print("[20] Consultar Dívida de Empréstimo")
    print("[21] Pagar Empréstimo")
    print("[0] Sair")
    print("=" * 45)


def pedir_valor():
    while True:
        entrada = input("Digite o valor: R$ ").strip()
        try:
            return float(entrada)
        except ValueError:
            print("[ERRO] Valor inválido. Digite um número (ex: 100 ou 99.90).\n")


def pedir_inteiro(mensagem):
    while True:
        entrada = input(mensagem).strip()
        try:
            return int(entrada)
        except ValueError:
            print("[ERRO] Valor inválido. Digite um número inteiro (ex: 3, 12).\n")


def fazer_login():
    print("=" * 45)
    print("           BEM-VINDO AO BYTEBANK")
    print("=" * 45)
    while True:
        numero = input("Digite o número da sua conta: ").strip()
        conta = buscar_conta_por_numero(numero)
        if conta:
            print(f"\nLogin realizado com sucesso! Olá, {conta['titular']}.\n")
            return conta
        print("[ERRO] Conta não encontrada. Tente novamente.\n")


def operar_conta(conta):
    while True:
        exibir_menu(conta)
        opcao = input("Escolha uma opção: ").strip()

        match opcao:
            case "1":
                consultar_saldo(conta)

            case "2":
                depositar(conta, pedir_valor())

            case "3":
                sacar(conta, pedir_valor())

            case "4":
                chave = input("Digite a chave PIX de destino: ").strip()
                transferir_pix(conta, chave, pedir_valor())

            case "5":
                return "trocar"
            case "6":
                consultar_carteira_investimentos(conta)
            case "7":
                investir(conta, pedir_valor())
            case "8":
                resgatar_investimento(conta, pedir_valor())

            case "9":
                consultar_limite_cartao_credito(conta)

            case "10":
                numero = input("Digite o número da nova conta: ").strip()
                titular = input("Digite o nome do titular: ").strip()
                chave_pix = input("Digite a chave PIX: ").strip()
                criar_conta(numero, titular, chave_pix)

            case "11":
                consultar_fatura_cartao_credito(conta)

            case "12":
                pagar_fatura_cartao_credito(conta, pedir_valor())

            case "13":
                consultar_saldo_moedas(conta)

            case "14":
                moeda = input("Digite a moeda a ser comprada (dolar, euro, yuan): ").strip().lower()
                valor_reais = pedir_valor()
                comprar_moeda(conta, moeda, valor_reais)

            case "15":
                moeda_origem = input("Digite a moeda de origem (real, dolar, euro, yuan): ").strip().lower()
                moeda_destino = input("Digite a moeda de destino (real, dolar, euro, yuan): ").strip().lower()
                quantidade_origem = pedir_valor()
                cambio_entre_moedas(conta, moeda_origem, moeda_destino, quantidade_origem)

            case "16":
                moeda = input("Digite a moeda a ser vendida (dolar, euro, yuan): ").strip().lower()
                quantidade = pedir_valor()
                vender_moeda(conta, moeda, quantidade)

            case "17":
                comprar_cartao_credito(conta, pedir_valor())

            case "18":
                valor = pedir_valor()
                parcelas = pedir_inteiro("Digite o número de parcelas: ")
                simular_emprestimo(conta, valor, parcelas)

            case "19":
                valor = pedir_valor()
                parcelas = pedir_inteiro("Digite o número de parcelas: ")
                contratar_emprestimo(conta, valor, parcelas)

            case "20":
                consultar_divida_emprestimo(conta)

            case "21":
                pagar_emprestimo(conta, pedir_valor())

            case "0":
                return "sair"

            case _:
                print("\n[ERRO] Opção inválida. Tente novamente.\n")


def main():
    while True:
        conta_logada = fazer_login()
        resultado = operar_conta(conta_logada)
        if resultado == "sair":
            print("\nObrigado por usar o ByteBank. Até logo!")
            break


if __name__ == "__main__":
    main()
