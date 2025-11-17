import discord
from flask import Flask, request, jsonify
import asyncio
from threading import Thread
import os                 # <-- ADICIONADO
from dotenv import load_dotenv # <-- ADICIONADO
import sys                # <-- ADICIONADO

load_dotenv() # <-- ADICIONADO (Carrega variáveis do .env)

# --- CONFIGURAÇÃO (Modificada para ler do .env) ---
BOT_TOKEN = os.getenv("TELEFONE_BOT_TOKEN") # <-- MODIFICADO

# Carrega o ID do canal e converte para int
channel_id_str = os.getenv("TELEFONE_NOTIFY_CHANNEL_ID")
CHANNEL_ID = None
if channel_id_str:
    try:
        CHANNEL_ID = int(channel_id_str)
    except ValueError:
        print(f"ERRO: TELEFONE_NOTIFY_CHANNEL_ID ('{channel_id_str}') no .env não é um número válido.")
# --- FIM DA CONFIGURAÇÃO ---


# Configura as 'intenções' do bot (permissões mínimas necessárias)
intents = discord.Intents.default()
# intents.members = True # Descomente se precisar de 'members' (para buscar DMs)

client = discord.Client(intents=intents)
api = Flask(__name__)

# --- LÓGICA DO BOT ---

@client.event
async def on_ready():
    """Evento que é acionado quando o bot se conecta com sucesso ao Discord."""
    print(f'Bot {client.user} (Telefone) conectado e pronto!')
    
    # Tenta encontrar o canal para garantir que a configuração está correta
    if not CHANNEL_ID:
        print("ERRO: ID do Canal (TELEFONE_NOTIFY_CHANNEL_ID) não foi carregado do .env")
        return
        
    try:
        channel = await client.fetch_channel(CHANNEL_ID)
        print(f'Canal de notificação "{channel.name}" encontrado com sucesso no servidor.')
    except discord.NotFound:
        print(f'ERRO: O canal com ID {CHANNEL_ID} não foi encontrado. Verifique a configuração.')
    except discord.Forbidden:
        print(f'ERRO: O bot não tem permissão para ver o canal com ID {CHANNEL_ID}.')
    except Exception as e:
        print(f"Ocorreu um erro inesperado ao buscar o canal: {e}")


async def send_channel_message(discord_id, message):
    """Função assíncrona que encontra o canal e envia a mensagem marcando o usuário."""
    if not CHANNEL_ID:
        print("ERRO: Tentativa de enviar mensagem sem CHANNEL_ID configurado.")
        return
        
    try:
        channel = await client.fetch_channel(CHANNEL_ID)
        if channel:
            # Monta a mensagem final com a marcação do usuário e a linha de separação
            full_message = f"<@{discord_id}> {message}\n{'-'*70}"
            await channel.send(full_message)
            print(f"Mensagem enviada para o canal {channel.name} marcando o usuário {discord_id}")
        else:
            print(f"ERRO: Canal com ID {CHANNEL_ID} não encontrado ao tentar enviar mensagem.")
    except Exception as e:
        print(f"ERRO ao tentar enviar mensagem para o canal: {e}")

# --- API PARA RECEBER COMANDOS DO APP.PY ---

@api.route('/notify', methods=['POST'])
def notify():
    data = request.get_json()
    discord_id = data.get('discord_id')
    message = data.get('message')

    if not discord_id or not message:
        return jsonify({'error': 'discord_id e message são obrigatórios'}), 400

    # Chama a função do bot de forma segura a partir da thread da API
    asyncio.run_coroutine_threadsafe(send_channel_message(discord_id, message), client.loop)
    
    return jsonify({'success': True, 'message': 'Notificação enviada para a fila de tarefas do bot.'})

def run_api():
    """Função para rodar o servidor Flask em uma thread separada."""
    # Roda em uma porta diferente (5001) para não conflitar com seu app principal (5000)
    print("* API Interna do Bot (Telefone) rodando na porta 5001...") # Log atualizado
    api.run(host='0.0.0.0', port=5001)

# --- INICIALIZAÇÃO ---

if __name__ == '__main__':
    
    # --- VERIFICAÇÃO ADICIONADA ---
    if not BOT_TOKEN or not CHANNEL_ID:
        print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
        print("!!! ERRO: BOT_TOKEN ou TELEFONE_NOTIFY_CHANNEL_ID não      !!!")
        print("!!!       foram encontrados no arquivo .env.               !!!")
        print("!!!       Verifique seu .env e reinicie o bot.             !!!")
        print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
        sys.exit(1) # Impede o bot de iniciar
    # --- FIM DA VERIFICAÇÃO ---

    # Inicia o servidor da API em uma thread para não bloquear o bot
    api_thread = Thread(target=run_api)
    api_thread.daemon = True
    print("Iniciando o servidor da API do bot de Telefone...")
    api_thread.start()
    
    # Inicia o bot do Discord
    print("Iniciando o bot de Telefone...")
    try:
        client.run(BOT_TOKEN)
    except discord.errors.LoginFailure:
        print("\nERRO CRÍTICO: O token do bot (TELEFONE_BOT_TOKEN) é inválido. Verifique o .env e reinicie.")
    except Exception as e:
        print(f"\nOcorreu um erro ao tentar rodar o bot de telefone: {e}")