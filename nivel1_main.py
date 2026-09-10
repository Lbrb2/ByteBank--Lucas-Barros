contas = [
    {"numero": "0001", "titular": "Amanda Silva", "saldo": 1000.00},
    {"numero": "0002", "titular": "Caio Ferreira", "saldo": 2500.50},
    {"numero": "0003", "titular": "Douglas Alves", "saldo": 320.00},
]


def buscar_conta_por_numero(numero):
    for conta in contas:
        if conta["numero"] == numero:
            return conta
    return None


def consultar_saldo(conta):
    print(f"\nTitular: {conta['titular']}")
    print(f"Conta: {conta['numero']}")
    print(f"Saldo atual: R$ {conta['saldo']:.2f}\n")


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


def exibir_menu(conta):
    print("=" * 45)
    print(f"   ByteBank | Conta {conta['numero']} - {conta['titular']}")
    print("=" * 45)
    print("[1] Consultar Saldo")
    print("[2] Depositar")
    print("[3] Sacar")
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


def main():
    conta = fazer_login()

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

            case "0":
                print("\nObrigado por usar o ByteBank. Até logo!")
                break

            case _:
                print("\n[ERRO] Opção inválida. Tente novamente.\n")


if __name__ == "__main__":
    main()
