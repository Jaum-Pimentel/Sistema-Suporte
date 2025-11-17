import discord
from flask import Flask, request, jsonify
import asyncio
from threading import Thread
import os                 # <-- ADICIONADO
from dotenv import load_dotenv # <-- ADICIONADO
import sys                # <-- ADICIONADO

load_dotenv() # <-- ADICIONADO (Carrega variáveis do .env)

# --- CONFIGURAÇÃO (Modificada para ler do .env) ---
BOT_TOKEN = os.getenv("QUERY_BOT_TOKEN")

# Carrega IDs de canal e converte para int
new_channel_id_str = os.getenv("QUERY_NEW_CHANNEL_ID")
answered_channel_id_str = os.getenv("QUERY_ANSWERED_CHANNEL_ID")

NEW_QUERY_CHANNEL_ID = None
ANSWERED_QUERY_CHANNEL_ID = None

if new_channel_id_str:
    try:
        NEW_QUERY_CHANNEL_ID = int(new_channel_id_str)
    except ValueError:
        print(f"ERRO: QUERY_NEW_CHANNEL_ID ('{new_channel_id_str}') no .env não é um número.")
        
if answered_channel_id_str:
    try:
        ANSWERED_QUERY_CHANNEL_ID = int(answered_channel_id_str)
    except ValueError:
        print(f"ERRO: QUERY_ANSWERED_CHANNEL_ID ('{answered_channel_id_str}') no .env não é um número.")
# --- FIM DA CONFIGURAÇÃO ---


# Configura as 'intenções' do bot
intents = discord.Intents.default()
# (Seu bot não busca membros, então 'intents.members = True' não é necessário aqui)
client = discord.Client(intents=intents)
api = Flask(__name__)

# --- LÓGICA DO BOT ---

@client.event
async def on_ready():
    """Evento que é acionado quando o bot se conecta com sucesso ao Discord."""
    print(f'Bot de Queries ({client.user}) conectado e pronto!')
    # Checagem de canais
    try:
        if NEW_QUERY_CHANNEL_ID: await client.fetch_channel(NEW_QUERY_CHANNEL_ID)
        print(f"Canal de Novas Queries (ID: {NEW_QUERY_CHANNEL_ID}) OK.")
    except Exception as e:
        print(f"ERRO ao acessar Canal de Novas Queries (ID: {NEW_QUERY_CHANNEL_ID}): {e}")
    try:
        if ANSWERED_QUERY_CHANNEL_ID: await client.fetch_channel(ANSWERED_QUERY_CHANNEL_ID)
        print(f"Canal de Respostas (ID: {ANSWERED_QUERY_CHANNEL_ID}) OK.")
    except Exception as e:
        print(f"ERRO ao acessar Canal de Respostas (ID: {ANSWERED_QUERY_CHANNEL_ID}): {e}")


async def send_new_query_notification(data):
    """Envia uma notificação para o canal de novas queries, marcando @here."""
    if not NEW_QUERY_CHANNEL_ID:
        print("ERRO: Tentativa de enviar nova query, mas QUERY_NEW_CHANNEL_ID não configurado.")
        return
    try:
        channel = await client.fetch_channel(NEW_QUERY_CHANNEL_ID)
        if not channel:
            print(f"ERRO: Canal de novas queries com ID {NEW_QUERY_CHANNEL_ID} não encontrado.")
            return

        embed = discord.Embed(
            title="🚨 Nova Solicitação de Query",
            description=data.get('description'),
            color=discord.Color.orange()
        )
        embed.set_footer(text=f"Solicitado por: {data.get('requester_name')}")
        
        await channel.send(content="@here", embed=embed)
        print(f"Notificação de nova query enviada para o canal #{channel.name}.")
    except Exception as e:
        print(f"ERRO ao enviar notificação de nova query: {e}")

async def send_answered_notification(data):
    """Envia uma notificação para o canal de respostas, marcando o solicitante."""
    if not ANSWERED_QUERY_CHANNEL_ID:
        print("ERRO: Tentativa de enviar resposta, mas QUERY_ANSWERED_CHANNEL_ID não configurado.")
        return
    try:
        channel = await client.fetch_channel(ANSWERED_QUERY_CHANNEL_ID)
        if not channel:
            print(f"ERRO: Canal de respostas com ID {ANSWERED_QUERY_CHANNEL_ID} não encontrado.")
            return
            
        requester_id = data.get('requester_discord_id')
        if not requester_id:
            print("AVISO: ID do Discord do solicitante não fornecido. Não é possível marcar o usuário.")
            # Envia mesmo assim, mas sem marcar
            requester_id = "Usuário (ID não encontrado)" 

        embed = discord.Embed(
            title="✅ Solicitação de Query Respondida!",
            description=f"**Solicitação Original:**\n```{data.get('description')}```",
            color=discord.Color.green()
        )
        embed.set_footer(text=f"Respondido por: {data.get('responder_name')}")
        
        message_content = f"Olá, <@{requester_id}>! Sua solicitação foi atendida."
        
        await channel.send(content=message_content, embed=embed)
        print(f"Notificação de resposta enviada para o canal #{channel.name}.")
    except Exception as e:
        print(f"ERRO ao enviar notificação de resposta: {e}")

# --- API PARA RECEBER COMANDOS DO APP.PY ---

@api.route('/notify_new_query', methods=['POST'])
def notify_new_query():
    data = request.get_json()
    if not data: return jsonify({'status': 'error', 'message': 'JSON inválido'}), 400
    asyncio.run_coroutine_threadsafe(send_new_query_notification(data), client.loop)
    return jsonify({'status': 'success'})

@api.route('/notify_answered_query', methods=['POST'])
def notify_answered_query():
    data = request.get_json()
    if not data: return jsonify({'status': 'error', 'message': 'JSON inválido'}), 400
    asyncio.run_coroutine_threadsafe(send_answered_notification(data), client.loop)
    return jsonify({'status': 'success'})

def run_api():
    print("* API Interna do Bot (Queries) rodando na porta 5003...") # Log atualizado
    api.run(host='0.0.0.0', port=5003)

# --- INICIALIZAÇÃO ---
if __name__ == '__main__':
    
    # --- VERIFICAÇÃO ADICIONADA ---
    if not BOT_TOKEN or not NEW_QUERY_CHANNEL_ID or not ANSWERED_QUERY_CHANNEL_ID:
        print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
        print("!!! ERRO: Configuração Incompleta do Bot de Queries.       !!!")
        if not BOT_TOKEN: print("!!!   - 'QUERY_BOT_TOKEN' não encontrado no .env.            !!!")
        if not NEW_QUERY_CHANNEL_ID: print("!!!   - 'QUERY_NEW_CHANNEL_ID' não encontrado no .env.       !!!")
        if not ANSWERED_QUERY_CHANNEL_ID: print("!!!   - 'QUERY_ANSWERED_CHANNEL_ID' não encontrado no .env.  !!!")
        print("!!!       Verifique seu .env e reinicie o bot.             !!!")
        print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
        sys.exit(1) # Impede o bot de iniciar
    # --- FIM DA VERIFICAÇÃO ---

    api_thread = Thread(target=run_api)
    api_thread.daemon = True
    print("Iniciando API do Bot de Queries...")
    api_thread.start()
    
    print("Iniciando Bot de Queries no Discord...")
    try:
        client.run(BOT_TOKEN)
    except discord.errors.LoginFailure:
        print("\nERRO CRÍTICO: O token (QUERY_BOT_TOKEN) é inválido. Verifique o .env e reinicie.")
    except Exception as e:
         print(f"\nOcorreu um erro ao tentar rodar o bot de queries: {e}")