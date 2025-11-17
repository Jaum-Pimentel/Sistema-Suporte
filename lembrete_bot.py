import discord
from flask import Flask, request, jsonify
import asyncio
from threading import Thread
import os                 # <-- ADICIONADO
from dotenv import load_dotenv # <-- ADICIONADO
import sys                # <-- ADICIONADO

load_dotenv() # <-- ADICIONADO (Carrega variáveis do .env)

# --- CONFIGURAÇÃO (Modificada para ler do .env) ---
BOT_TOKEN = os.getenv("LEMBRETE_BOT_TOKEN")

# Carrega o ID do canal e converte para int
channel_id_str = os.getenv("LEMBRETE_NOTIFY_CHANNEL_ID")
CHANNEL_ID = None
if channel_id_str:
    try:
        CHANNEL_ID = int(channel_id_str)
    except ValueError:
        print(f"ERRO: LEMBRETE_NOTIFY_CHANNEL_ID ('{channel_id_str}') no .env não é um número válido.")

# SERVER_ID não era usado, foi removido.
# --- FIM DA CONFIGURAÇÃO ---


# Configura as 'intenções' do bot (permissões)
intents = discord.Intents.default()
intents.members = True # Necessário para encontrar usuários para a DM
client = discord.Client(intents=intents)
api = Flask(__name__)

# --- LÓGICA DO BOT ---

@client.event
async def on_ready():
    """Evento que é acionado quando o bot se conecta com sucesso ao Discord."""
    print(f'Bot de Lembretes {client.user} conectado e pronto para receber comandos!')
    
    if not CHANNEL_ID:
        print("AVISO: LEMBRETE_NOTIFY_CHANNEL_ID (para rota /notify) não foi carregado. Rota /notify pode falhar.")
        return # Não é um erro fatal, pois /notify_reminder ainda funciona
        
    # Tenta encontrar o canal para garantir que a configuração está correta
    try:
        channel = await client.fetch_channel(CHANNEL_ID)
        print(f'Canal de notificação genérico "{channel.name}" (rota /notify) encontrado.')
    except discord.NotFound:
        print(f'ERRO: O canal (LEMBRETE_NOTIFY_CHANNEL_ID) com ID {CHANNEL_ID} não foi encontrado.')
    except discord.Forbidden:
        print(f'ERRO: O bot não tem permissão para ver o canal com ID {CHANNEL_ID}.')
    except Exception as e:
        print(f"Ocorreu um erro inesperado ao buscar o canal: {e}")


async def send_channel_message(discord_id, message):
    """Função (usada pela rota /notify) que envia para o canal global CHANNEL_ID."""
    if not CHANNEL_ID:
        print("ERRO: Rota /notify chamada, mas LEMBRETE_NOTIFY_CHANNEL_ID não está configurado no .env")
        return

    try:
        channel = await client.fetch_channel(CHANNEL_ID)
        if channel:
            full_message = f"<@{discord_id}> {message}\n{'-'*70}"
            await channel.send(full_message)
            print(f"Mensagem (via /notify) enviada para o canal {channel.name} marcando o usuário {discord_id}")
        else:
            print(f"ERRO: Canal com ID {CHANNEL_ID} não encontrado ao tentar enviar mensagem.")
    except Exception as e:
        print(f"ERRO ao tentar enviar mensagem para o canal (via /notify): {e}")

async def send_reminder_notification(data):
    """Função (usada pela rota /notify_reminder) que envia DM e msg para canal de gestão."""
    creator_id = data.get('creator_discord_id')
    gestor_channel_id_str = data.get('gestor_channel_id')
    embed_data = data.get('embed')

    if not embed_data:
        print("ERRO: Nenhum 'embed' recebido na notificação de lembrete.")
        return

    # Cria o objeto Embed a partir dos dados JSON
    try:
        embed = discord.Embed.from_dict(embed_data)
    except Exception as e:
        print(f"ERRO: Falha ao criar Embed a partir dos dados: {e}")
        return

    # 1. Envia a DM para o criador do lembrete
    if creator_id:
        try:
            user = await client.fetch_user(int(creator_id))
            await user.send(embed=embed)
            print(f"  -> DM de lembrete enviada com sucesso para {user.name}")
        except Exception as e:
            print(f"  -> ERRO ao enviar DM para o usuário ID {creator_id}: {e}")
    else:
        print("  -> Aviso: creator_discord_id não fornecido. Pulando envio de DM.")


    # 2. Envia a mensagem para o canal do gestor
    if gestor_channel_id_str:
        try:
            gestor_channel_id = int(gestor_channel_id_str)
            channel = await client.fetch_channel(gestor_channel_id)
            if channel:
                gestor_message_content = f"**Lembrete para:** <@{creator_id}>" if creator_id else "**Lembrete (Usuário sem ID Discord):**"
                await channel.send(content=gestor_message_content, embed=embed)
                print(f"  -> Lembrete enviado para o canal de gestão #{channel.name}")
            else:
                print(f"  -> ERRO: Canal de gestão com ID {gestor_channel_id} não encontrado.")
        except Exception as e:
            print(f"  -> ERRO ao enviar mensagem para o canal de gestão (ID: {gestor_channel_id_str}): {e}")
    else:
        print("  -> Aviso: gestor_channel_id não fornecido. Pulando envio para canal de gestão.")


# --- API PARA RECEBER COMANDOS DO APP.PY ---

@api.route('/notify', methods=['POST'])
def notify():
    """Rota genérica que envia para o CHANNEL_ID global."""
    data = request.get_json()
    discord_id = data.get('discord_id')
    message = data.get('message')

    if not discord_id or not message:
        return jsonify({'error': 'discord_id e message são obrigatórios'}), 400

    asyncio.run_coroutine_threadsafe(send_channel_message(discord_id, message), client.loop)
    return jsonify({'success': True, 'message': 'Notificação (genérica) enviada para a fila.'})


@api.route('/notify_reminder', methods=['POST'])
def notify_reminder():
    """Rota específica que o scheduler.py chama."""
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Requisição sem dados'}), 400

    asyncio.run_coroutine_threadsafe(send_reminder_notification(data), client.loop)
    return jsonify({'success': True, 'message': 'Lembrete enviado para a fila de tarefas do bot.'})

def run_api():
    """Função para rodar o servidor Flask em uma thread separada."""
    print("* API Interna do Bot (Lembretes) rodando na porta 5002...")
    api.run(host='0.0.0.0', port=5002)

# --- INICIALIZAÇÃO ---

if __name__ == '__main__':
    
    # --- VERIFICAÇÃO ADICIONADA ---
    if not BOT_TOKEN:
        print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
        print("!!! ERRO: LEMBRETE_BOT_TOKEN não encontrado no .env.       !!!")
        print("!!!       Verifique seu .env e reinicie o bot.             !!!")
        print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
        sys.exit(1) # Impede o bot de iniciar
    # --- FIM DA VERIFICAÇÃO ---

    api_thread = Thread(target=run_api)
    api_thread.daemon = True
    print("Iniciando o servidor da API do Bot de Lembretes...")
    api_thread.start()
    
    print("Iniciando o bot de Lembretes...")
    try:
        client.run(BOT_TOKEN)
    except discord.errors.LoginFailure:
        print("\nERRO CRÍTICO: O token do bot (LEMBRETE_BOT_TOKEN) é inválido. Verifique o .env e reinicie.")
    except Exception as e:
        print(f"\nOcorreu um erro ao tentar rodar o bot de lembretes: {e}")