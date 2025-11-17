import discord
import asyncio
from flask import Flask, request, jsonify
import requests
import threading
import logging
import sys
import os # <-- ADICIONADO
from dotenv import load_dotenv # <-- ADICIONADO

load_dotenv() # <-- ADICIONADO (Lê o arquivo .env)

# --- CONFIGURAÇÃO DO BOT (MODIFICADO) ---

# 1. Pega o token do .env
BOT_TOKEN = os.getenv("NOTIFICACOES_BOT_TOKEN") 

# 2. Pega o ID do canal do .env
NOTIFY_CHANNEL_ID = os.getenv("NOTIFICACOES_CHANNEL_ID")

# REMOVIDO: A URL da API e os Headers serão criados dentro da função
# DISCORD_API_URL = f"https://discord.com/api/v10/channels/{NOTIFY_CHANNEL_ID}/messages"
# HEADERS = { ... }

# --- FIM DA CONFIGURAÇÃO ---


# --- 1. DEFINIÇÃO DO SERVIDOR FLASK (O OUVINTE) ---

app = Flask(__name__)
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

@app.route('/notify', methods=['POST'])
def notify_general():
    """Esta rota recebe a notificação do app.py e a envia para o Discord."""
    
    # --- ADICIONADO: Define URLs e Headers aqui ---
    # Isso garante que as variáveis BOT_TOKEN e NOTIFY_CHANNEL_ID já foram carregadas
    if not BOT_TOKEN or not NOTIFY_CHANNEL_ID:
        print("[ERRO] Token ou ID do Canal não encontrado. Verifique seu arquivo .env")
        return jsonify({'status': 'error', 'message': 'Bot não configurado'}), 500
        
    DISCORD_API_URL = f"https://discord.com/api/v10/channels/{NOTIFY_CHANNEL_ID}/messages"
    HEADERS = {
        "Authorization": f"Bot {BOT_TOKEN}"
    }
    # --- FIM DA ADIÇÃO ---
    
    try:
        data = request.json
        message = data.get('message')

        if not message:
            return jsonify({'status': 'error', 'message': 'Mensagem não encontrada'}), 400

        discord_payload = {
            'content': message
        }

        # Envia a mensagem para o Discord usando a API e o TOKEN
        response = requests.post(DISCORD_API_URL, headers=HEADERS, json=discord_payload)
        response.raise_for_status() 
        
        print(f"[OK] Notificação enviada para o canal {NOTIFY_CHANNEL_ID}!")
        return jsonify({'status': 'success'})

    except Exception as e:
        print(f"[ERRO] Falha ao enviar notificação: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"[DEBUG] Resposta do Discord: {e.response.text}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

def run_flask_server():
    """Função que será executada na thread separada para o servidor."""
    print(f"* Servidor Flask (Ouvinte) rodando na porta 5005...")
    app.run(host='127.0.0.1', port=5005)

# --- 2. DEFINIÇÃO DO BOT DO DISCORD (A PRESENÇA ONLINE) ---

intents = discord.Intents.default()
client = discord.Client(intents=intents)

@client.event
async def on_ready():
    """Chamado quando o bot se conecta com sucesso ao Discord."""
    print(f"* Presença Online ATIVADA!")
    print(f"* Logado como: {client.user.name}")
    print("==================================================")
    
    game = discord.Game(name="Notificações do Sistema")
    await client.change_presence(status=discord.Status.online, activity=game)

# --- 3. INICIALIZAÇÃO (Onde a mágica acontece) ---

if __name__ == '__main__':
    
    # --- BLOCO DE VERIFICAÇÃO ATUALIZADO ---
    # Verifica se as variáveis foram carregadas do .env
    if not BOT_TOKEN or not NOTIFY_CHANNEL_ID:
        print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
        print("!!! ERRO: Bot não configurado.                 !!!")
        print("!!! Verifique se 'NOTIFICACOES_BOT_TOKEN' e    !!!")
        print("!!! 'NOTIFICACOES_CHANNEL_ID' estão no .env.   !!!")
        print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
        sys.exit(1) # Sai do script
    # --- FIM DA VERIFICAÇÃO ---
    else:
        print("==================================================")
        print(">>> Bot de Notificações Gerais (Completo) <<<")
        print(f"Enviando mensagens para o Canal ID: {NOTIFY_CHANNEL_ID}")
        
        flask_thread = threading.Thread(target=run_flask_server, daemon=True)
        flask_thread.start()
        
        print("* Conectando ao Discord para ficar ONLINE...")
        try:
            client.run(BOT_TOKEN) # Usa a variável carregada
        except discord.errors.LoginFailure:
            print("\n!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
            print("!!! ERRO: Login falhou. O BOT_TOKEN está     !!!")
            print("!!! incorreto ou não tem as permissões certas. !!!")
            print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
        except Exception as e:
            print(f"Erro ao iniciar o bot do Discord: {e}")