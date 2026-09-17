contas = [
    {"numero": "0001", "titular": "Amanda Silva", "chave_pix": "amanda@email.com", "saldo": 1000.00, "carteira_investimentos": 5000.00},
    {"numero": "0002", "titular": "Caio Ferreira", "chave_pix": "caio@email.com", "saldo": 2500.50,"carteira_investimentos": 3000.00},
    {"numero": "0003", "titular": "Douglas Alves", "chave_pix": "douglas@email.com", "saldo": 320.00, "carteira_investimentos": 1000.00},

]


def buscar_conta_por_numero(numero):
    for conta in contas:
        if conta["numero"] == numero:
            return conta
    return None


def buscar_conta_por_chave_pix(chave):
    for conta in contas:
        if conta["chave_pix"] == chave:
            return conta
    return None


def consultar_saldo(conta):
    print(f"\nTitular: {conta['titular']}")
    print(f"Conta: {conta['numero']}")
    print(f"Saldo atual: R$ {conta['saldo']:.2f}\n")

def consultar_carteira_investimentos(conta):
    print(f"\nTitular: {conta['titular']}")
    print(f"Conta: {conta['numero']}")
    print(f"Saldo da carteira de investimentos: R$ {conta['carteira_investimentos']:.2f}\n")

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
    print("[0] Sair")
    print("=" * 45)


def pedir_valor():
    while True:
        entrada = input("Digite o valor: R$ ").strip()
        try:
            return float(entrada)
        except ValueError:
            print("[ERRO] Valor inválido. Digite um número (ex: 100 ou 99.90).\n")


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
