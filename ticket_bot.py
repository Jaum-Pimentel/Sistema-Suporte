import discord
import requests
import asyncio
import threading # NOVO: Para rodar o servidor web em paralelo
import os                 # <-- ADICIONADO
from dotenv import load_dotenv # <-- ADICIONADO
import sys                # <-- ADICIONADO

# NOVO: Importações para o servidor web embutido
from aiohttp import web

load_dotenv() # <-- ADICIONADO (Carrega variáveis do .env)

# --- CONFIGURAÇÃO (Modificada para ler do .env) ---
BOT_TOKEN = os.getenv("TICKET_BOT_TOKEN")

# Helper para carregar IDs de canal do .env como números
def get_env_int(key):
    val_str = os.getenv(key)
    if val_str:
        try:
            return int(val_str)
        except ValueError:
            print(f"ERRO: {key} ('{val_str}') no .env não é um número válido.")
    return None

WATCH_CHANNEL_ID = get_env_int("TICKET_WATCH_CHANNEL_ID")
RESOLVED_CHANNEL_ID = get_env_int("TICKET_RESOLVED_CHANNEL_ID")
# --- FIM DA CONFIGURAÇÃO ---


# O endereço da API do seu sistema principal para criar tickets
APP_API_URL = "http://127.0.0.1:5000/api/new_discord_ticket"

# NOVO: Porta em que o bot vai escutar por notificações do Flask
BOT_API_PORT = 8080

# Configura as 'intenções' do bot
intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)


# NOVO: Função que será chamada pelo servidor web para enviar a notificação
async def send_resolved_notification(user_id, description, link):
    """Envia uma mensagem para o canal de resolvidos, mencionando o usuário."""
    if not RESOLVED_CHANNEL_ID:
        print("ERRO: Tentativa de enviar notif. resolvida, mas RESOLVED_CHANNEL_ID não configurado.")
        return
    try:
        channel = client.get_channel(RESOLVED_CHANNEL_ID)
        if not channel:
            channel = await client.fetch_channel(RESOLVED_CHANNEL_ID)
        
        if not channel:
            print(f"ERRO: Canal de resolvidos com ID {RESOLVED_CHANNEL_ID} não encontrado.")
            return

        # Busca o objeto do usuário para garantir que ele exista
        user = await client.fetch_user(user_id)
        if not user:
            print(f"ERRO: Usuário do Discord com ID {user_id} não encontrado.")
            user_mention = f"Usuário (ID: {user_id})" # Fallback
        else:
            user_mention = f"<@{user_id}>"

        # Formata a mensagem final
        message_content = (
            f"Ai sim {user_mention}! O ticket **{description}** foi resolvido.\n"
            f"Lembre de retornar ao link: {link}"
        )

        await channel.send(message_content)
        print(f"Notificação de resolução enviada para o usuário {user_id}.")

    except Exception as e:
        print(f"Ocorreu um erro ao enviar a notificação de resolução: {e}")


# NOVO: O manipulador de requisições do nosso servidor web
async def handle_notify_resolved(request):
    """Recebe a notificação do Flask e agenda o envio da mensagem no Discord."""
    try:
        data = await request.json()
        user_id = data.get('discord_user_id')
        description = data.get('ticket_description')
        link = data.get('ticket_link')

        if not all([user_id, description, link]):
            return web.Response(text="Dados incompletos", status=400)

        # Agenda a execução da função de envio no event loop principal do bot
        client.loop.create_task(send_resolved_notification(user_id, description, link))
        
        return web.Response(text="Notificação recebida com sucesso!", status=200)

    except Exception as e:
        print(f"Erro ao processar a requisição de notificação: {e}")
        return web.Response(text="Erro interno", status=500)


# NOVO: Função para configurar e rodar o servidor web
async def run_web_server():
    """Inicia o servidor AIOHTTP."""
    app = web.Application()
    app.router.add_post('/notify-resolved', handle_notify_resolved)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', BOT_API_PORT)
    print(f"Servidor de notificações do Bot (Tickets) escutando em http://0.0.0.0:{BOT_API_PORT}")
    await site.start()


@client.event
async def on_ready():
    """Evento que é acionado quando o bot se conecta com sucesso ao Discord."""
    print(f'Bot {client.user} (Tickets) conectado e pronto!')
    
    if WATCH_CHANNEL_ID: print(f'Monitorando o canal de criação: {WATCH_CHANNEL_ID}')
    else: print('ERRO: TICKET_WATCH_CHANNEL_ID não configurado!')
    
    if RESOLVED_CHANNEL_ID: print(f'Enviando retornos para o canal: {RESOLVED_CHANNEL_ID}')
    else: print('ERRO: TICKET_RESOLVED_CHANNEL_ID não configurado!')
    
    # NOVO: Inicia o servidor web em uma task de fundo
    client.loop.create_task(run_web_server())
    

@client.event
async def on_message(message):
    """
    Evento que é acionado toda vez que uma nova mensagem é postada.
    """
    if message.author == client.user:
        return
    
    if not WATCH_CHANNEL_ID: return # Não faz nada se o canal não estiver configurado

    if message.channel.id == WATCH_CHANNEL_ID:
        print(f"\nNova mensagem detectada no canal '{message.channel.name}':")
        print(f"Autor: {message.author.name} (ID: {message.author.id})")
        
        content = message.content.strip()
        lines = content.split('\n')

        if len(lines) >= 2:
            description = lines[0].strip()
            link = lines[1].strip()
            
            print(f"  - Descrição extraída: {description}")
            print(f"  - Link extraído: {link}")

            payload = {
                'description': description,
                'link': link,
                'requester_discord_id': message.author.id # ID de quem criou o ticket
            }

            try:
                response = requests.post(APP_API_URL, json=payload, timeout=5)
                if response.status_code == 201:
                    print("  -> Ticket enviado com sucesso para o sistema principal!")
                    await message.add_reaction('✅')
                else:
                    print(f"  -> ERRO ao enviar ticket: O sistema respondeu com status {response.status_code}")
                    await message.add_reaction('❌')
            except requests.exceptions.RequestException as e:
                print(f"  -> ERRO de conexão: Não foi possível se conectar a {APP_API_URL}.")
                await message.add_reaction('🔥')
        else:
            print("  - A mensagem não tem o formato esperado (Descrição\\nLink). Ignorando.")


if __name__ == '__main__':
    print("Iniciando o bot de tickets...")
    
    # --- VERIFICAÇÃO ADICIONADA ---
    if not BOT_TOKEN or not WATCH_CHANNEL_ID or not RESOLVED_CHANNEL_ID:
        print("\n\n!!! ATENÇÃO: Configuração incompleta para o Bot de Tickets !!!")
        if not BOT_TOKEN: print("!!! - TICKET_BOT_TOKEN não encontrado no .env")
        if not WATCH_CHANNEL_ID: print("!!! - TICKET_WATCH_CHANNEL_ID não encontrado no .env")
        if not RESOLVED_CHANNEL_ID: print("!!! - TICKET_RESOLVED_CHANNEL_ID não encontrado no .env")
        print("!!! Verifique seu .env e reinicie. !!!")
        sys.exit(1) # Sai do script
    # --- FIM DA VERIFICAÇÃO ---
    
    try:
        client.run(BOT_TOKEN)
    except discord.errors.LoginFailure:
        print("\nERRO CRÍTICO: Token do bot (TICKET_BOT_TOKEN) é inválido.")
    except Exception as e:
        print(f"\nOcorreu um erro ao rodar o bot: {e}")