import psutil
import os

def parar_processo_na_porta(porta):
    """
    Encontra e encerra o processo que está usando uma porta específica.
    """
    for conexao in psutil.net_connections(kind='inet'):
        if conexao.laddr.port == porta:
            pid = conexao.pid
            if pid:
                print(f"Encerrando processo com PID {pid} na porta {porta}...")
                try:
                    processo = psutil.Process(pid)
                    processo.terminate()
                    print(f"Processo {pid} encerrado com sucesso.")
                    return True
                except psutil.NoSuchProcess:
                    print(f"Processo com PID {pid} já não existe.")
                    return False
                except psutil.AccessDenied:
                    print(f"Acesso negado. Tente executar com privilégios de administrador/superusuário.")
                    return False

    print(f"Nenhum processo encontrado na porta {porta}.")
    return False

if __name__ == "__main__":
    PORTA_DO_SERVIDOR = 5000  # Substitua pela porta que o seu servidor está usando
    parar_processo_na_porta(PORTA_DO_SERVIDOR)