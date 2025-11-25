import discord
from flask import Flask, request, jsonify
import asyncio
from threading import Thread
import os
from dotenv import load_dotenv
import sys

load_dotenv()

# --- CONFIGURAÇÃO ---
BOT_TOKEN = os.getenv("HUBSPOT_BOT_TOKEN") # Crie esse token no .env ou use o mesmo se o bot for o mesmo
CHANNEL_ID = 1433175022553534606 # <--- COLOQUE AQUI O ID DO CANAL DE NOTIFICAÇÃO (Ex: #financeiro ou #cs)

# IDs do Discord para marcar a pessoa (Pegue clicando com botão direito no usuario -> Copiar ID)
DISCORD_IDS = {
    'Matheus Vilela': '1181597947553644717',
    'Cauã': '694934329725288549',
    'Ana Vitoria': '1069778846490042399'
}

intents = discord.Intents.default()
client = discord.Client(intents=intents)
api = Flask(__name__)

@client.event
async def on_ready():
    print(f'Bot Hubspot {client.user} online!')

async def send_hubspot_alert(data):
    tipo = data.get('tipo')
    responsavel_nome = data.get('responsavel')
    link_hub = data.get('link_hub')
    link_chat = data.get('link_chat')
    autor = data.get('autor')
    
    # Pega o ID do discord para marcar, se existir
    responsavel_id = DISCORD_IDS.get(responsavel_nome)
    mention = f"<@{responsavel_id}>" if responsavel_id else f"**{responsavel_nome}**"
    
    # Define a cor lateral baseada no tipo
    color = 15158332 # Vermelho (Cancelamento/Downgrade)
    if 'Treinamento' in tipo:
        color = 3447003 # Azul (Treinamento)
    elif 'Reajuste' in tipo:
        color = 15844367 # Dourado (Reajuste)

    embed = discord.Embed(
        title=f"📢 Nova Solicitação: {tipo}",
        description=f"Uma nova demanda foi aberta e atribuída a você, {mention}.",
        color=color
    )
    
    embed.add_field(name="📄 Ticket HubSpot", value=f"[Acessar Ticket]({link_hub})", inline=False)
    embed.add_field(name="💬 Chat Original", value=f"[Ver Conversa]({link_chat})", inline=False)
    embed.add_field(name="👤 Aberto por", value=autor, inline=True)
    embed.set_footer(text="Auvo SUP - Sistema de Solicitações")

    try:
        channel = await client.fetch_channel(CHANNEL_ID)
        if channel:
            # Envia a mensagem marcando a pessoa no texto para notificar
            await channel.send(content=f"Atenção {mention}!", embed=embed)
            print(f"Notificação Hubspot enviada para {responsavel_nome}")
        else:
            print(f"Canal {CHANNEL_ID} não encontrado.")
    except Exception as e:
        print(f"Erro ao enviar notificação: {e}")

@api.route('/notify_hubspot', methods=['POST'])
def notify_hubspot():
    data = request.get_json()
    asyncio.run_coroutine_threadsafe(send_hubspot_alert(data), client.loop)
    return jsonify({'success': True})

def run_api():
    api.run(host='0.0.0.0', port=5015)

if __name__ == '__main__':
    api_thread = Thread(target=run_api)
    api_thread.daemon = True
    api_thread.start()
    client.run(BOT_TOKEN)

