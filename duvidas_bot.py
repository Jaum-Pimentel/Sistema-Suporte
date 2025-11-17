import discord
import asyncio
from flask import Flask, request, jsonify
import requests
import threading
import logging
import sys
import os # Para usar variáveis de ambiente
from dotenv import load_dotenv # <-- ADICIONADO

load_dotenv() # <-- ADICIONADO (Carrega variáveis do .env)

# --- CONFIGURAÇÃO (Modificada para ler do .env) ---
# 1. TOKEN DO BOT
BOT_TOKEN = os.getenv("DUVIDAS_BOT_TOKEN") 

# 2. ID DO CANAL
channel_id_str = os.getenv("DUVIDAS_CHANNEL_ID")
DUVIDAS_CHANNEL_ID = None
if channel_id_str:
    try:
        DUVIDAS_CHANNEL_ID = int(channel_id_str)
    except ValueError:
        print(f"ERRO: DUVIDAS_CHANNEL_ID ('{channel_id_str}') no .env não é um número válido.")

# 3. URL da API do app.py (sem mudança)
FLASK_API_URL = os.getenv("FLASK_API_URL", "http://127.0.0.1:5000/api/resposta_duvida") 

# 4. CHAVE SECRETA (lê do .env, igual ao app.py)
API_SECRET_KEY = os.getenv("FLASK_API_SECRET", "mude-para-algo-bem-secreto-e-dificil")

# 5. Emoji (sem mudança)
CORRECT_ANSWER_EMOJI = '✅' 

# 6. ID DO CARGO PERMITIDO
role_id_str = os.getenv("ALLOWED_ROLE_ID")
ALLOWED_ROLE_ID = None
if role_id_str:
    try:
        ALLOWED_ROLE_ID = int(role_id_str)
    except ValueError:
        print(f"ERRO: ALLOWED_ROLE_ID ('{role_id_str}') no .env não é um número válido.")
# --- FIM DA CONFIGURAÇÃO ---


# --- Estado do Bot ---
duvida_thread_map = {} 

# --- Setup do Flask (API interna do Bot) ---
api = Flask(__name__)
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR) # Esconde logs do Flask

@api.route('/criar-topico-duvida', methods=['POST'])
def handle_criar_topico():
    data = request.json
    required = ['duvida_id', 'titulo', 'categoria', 'descricao', 'author_name']
    if not data or not all(field in data for field in required):
        print("[API Bot ERRO] Dados incompletos recebidos.")
        return jsonify({'status': 'error', 'message': 'Dados incompletos'}), 400

    future = asyncio.run_coroutine_threadsafe(
        create_duvida_thread(data), client.loop
    )
    
    try:
        result = future.result(timeout=20) 
        status_code = 201 if result.get('status') == 'success' else 500
        print(f"[API Bot Resp] Status: {result.get('status')}, Msg: {result.get('message')}")
        return jsonify(result), status_code
    except asyncio.TimeoutError:
         print("[API Bot ERRO] Timeout esperando criação do tópico.")
         return jsonify({'status': 'error', 'message': 'Timeout ao criar tópico'}), 504
    except Exception as e:
         print(f"[API Bot ERRO] Exceção ao esperar resultado: {e}")
         return jsonify({'status': 'error', 'message': f'Erro inesperado: {e}'}), 500

def run_api_server():
    print(f"* API Interna do Bot rodando na porta 5006...")
    try:
         api.run(host='127.0.0.1', port=5006) 
    except Exception as e:
        print(f"ERRO FATAL ao iniciar API interna: {e}")

# --- Setup do Bot Discord ---
intents = discord.Intents.default()
intents.message_content = True 
intents.guilds = True
intents.guild_reactions = True 

client = discord.Client(intents=intents)

async def create_duvida_thread(data):
    """Cria a mensagem inicial e o tópico no Discord."""
    duvida_id = data['duvida_id']
    titulo = data['titulo']
    categoria = data['categoria']
    descricao = data['descricao']
    author_name = data['author_name']
    image_url = data.get('image_url') 
    
    if not DUVIDAS_CHANNEL_ID: # Checagem de segurança
        print("ERRO: create_duvida_thread chamado mas DUVIDAS_CHANNEL_ID é None.")
        return {'status': 'error', 'message': 'Bot não configurado com ID de canal'}

    try:
        channel = client.get_channel(DUVIDAS_CHANNEL_ID)
        if not channel:
            channel = await client.fetch_channel(DUVIDAS_CHANNEL_ID)
        
        if not isinstance(channel, discord.TextChannel):
             print(f"ERRO: ID {DUVIDAS_CHANNEL_ID} não é um canal de texto.")
             return {'status': 'error', 'message': 'ID de canal inválido'}

        embed = discord.Embed(
            title=f"❓ Nova Dúvida #{duvida_id}",
            description=f"**{titulo}**\n\n{descricao}",
            color=discord.Color.blue() 
        )
        embed.add_field(name="Categoria", value=categoria, inline=True)
        embed.add_field(name="Enviada por", value=author_name, inline=True)
        embed.set_footer(text=f"ID Sistema: {duvida_id}")

        if image_url:
            print(f"[Bot] Adicionando imagem ao embed: {image_url}")
            embed.set_image(url=image_url)

        message = await channel.send(embed=embed)
        
        thread_name = f"Dúvida {duvida_id}: {titulo}"[:100] 
        thread = await message.create_thread(name=thread_name) 

        mensagem_topico = f"@here\n> O seguimento dessa dúvida deve ser feito aqui dentro desse tópico."
        await thread.send(mensagem_topico)

        duvida_thread_map[thread.id] = duvida_id
        print(f"Tópico criado: {thread.id} -> Dúvida {duvida_id}")

        return {'status': 'success', 'message': 'Tópico criado', 'thread_id': thread.id, 'message_id': message.id}

    except discord.Forbidden:
        print(f"ERRO: Bot sem permissão no canal {DUVIDAS_CHANNEL_ID}.")
        return {'status': 'error', 'message': 'Bot sem permissão'}
    except discord.NotFound:
         print(f"ERRO: Canal {DUVIDAS_CHANNEL_ID} não encontrado.")
         return {'status': 'error', 'message': 'Canal não encontrado'}
    except Exception as e:
        print(f"ERRO inesperado ao criar tópico: {e}")
        return {'status': 'error', 'message': f'Erro inesperado: {e}'}

@client.event
async def on_ready():
    """Chamado quando o bot conecta."""
    print("==================================================")
    print(f">>> Bot de Dúvidas LIGADO!")
    print(f"Logado como: {client.user.name}")
    if DUVIDAS_CHANNEL_ID:
        try:
            await client.fetch_channel(DUVIDAS_CHANNEL_ID)
            print(f"Canal de Dúvidas (ID: {DUVIDAS_CHANNEL_ID}) OK.")
        except Exception as e:
            print(f"!!! ATENÇÃO: ERRO ao acessar Canal de Dúvidas (ID: {DUVIDAS_CHANNEL_ID}): {e}")
    else:
        print("!!! ATENÇÃO: NENHUM ID de Canal de Dúvidas configurado.")
    print("==================================================")
    await client.change_presence(activity=discord.Activity(type=discord.ActivityType.listening, name="Fala dai chefia"))

@client.event
async def on_reaction_add(reaction: discord.Reaction, user: discord.User | discord.Member):
    """Chamado quando uma reação é adicionada."""
    
    if user.bot or str(reaction.emoji) != CORRECT_ANSWER_EMOJI:
        return

    message = reaction.message
    
    if isinstance(message.channel, discord.Thread) and message.channel.id in duvida_thread_map:
        thread_id = message.channel.id
        duvida_id = duvida_thread_map[thread_id]
        
        print(f"Reação '{CORRECT_ANSWER_EMOJI}' detectada em msg {message.id} no tópico {thread_id} (Dúvida {duvida_id}) por {user.name}")

        if not ALLOWED_ROLE_ID:
            print("[CONFIG ERRO] ALLOWED_ROLE_ID não definido. Reação ignorada.")
            return

        if isinstance(user, discord.Member): 
            allowed = any(role.id == ALLOWED_ROLE_ID for role in user.roles)
            if not allowed:
                print(f"[Permissão Negada] {user.name} não tem o cargo {ALLOWED_ROLE_ID}.")
                return
        else:
             print(f"[Permissão Negada] Não foi possível verificar cargos de {user.name}.")
             return

        print(f"[Ação] Usuário {user.name} marcou resposta para Dúvida {duvida_id}.")

        payload = {
            'duvida_id': duvida_id,
            'conteudo_resposta': message.content, 
            'author_discord_id': str(message.author.id) 
        }
        headers = {'Content-Type': 'application/json', 'X-Api-Key': API_SECRET_KEY }

        try:
            response = requests.post(FLASK_API_URL, json=payload, headers=headers, timeout=10)
            response.raise_for_status() 
            print(f"[Bot->Flask OK] Resposta da dúvida {duvida_id} enviada.")
            await message.add_reaction('👍') 
        except requests.exceptions.RequestException as e:
            print(f"[Bot->Flask ERRO] Falha ao enviar resposta para {FLASK_API_URL}: {e}")
            if e.response is not None: print(f"[DEBUG] Resposta Flask: {e.response.text}")
            await message.add_reaction('⚠️') 
        except discord.Forbidden:
             print("[Bot ERRO] Sem permissão para adicionar reação 👍 ou ⚠️.")
        except Exception as e:
            print(f"[Bot ERRO] Erro inesperado ao processar/enviar resposta: {e}")
            try: await message.add_reaction('⚠️') 
            except: pass 

# --- INICIALIZAÇÃO ---
if __name__ == '__main__':
    
    # --- Verificação inicial CORRIGIDA ---
    # Verifica se as variáveis foram carregadas corretamente
    if not BOT_TOKEN or not DUVIDAS_CHANNEL_ID or not ALLOWED_ROLE_ID:
        print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
        print("!!! ERRO: Configuração Incompleta.                                        !!!")
        if not BOT_TOKEN: print("!!!   - 'DUVIDAS_BOT_TOKEN' não encontrado no .env.                       !!!")
        if not DUVIDAS_CHANNEL_ID: print("!!!   - 'DUVIDAS_CHANNEL_ID' não encontrado ou inválido no .env.          !!!")
        if not ALLOWED_ROLE_ID: print("!!!   - 'ALLOWED_ROLE_ID' não encontrado ou inválido no .env.             !!!")
        print("!!! Verifique seu arquivo .env e reinicie o bot.                          !!!")
        print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
        sys.exit(1) # Sai do script se não configurado
    # --- Fim da Verificação ---

    print("Iniciando Bot de Dúvidas...")
    api_thread = threading.Thread(target=run_api_server, daemon=True)
    api_thread.start()
    
    print("Conectando ao Discord...")
    try:
        client.run(BOT_TOKEN)
    except discord.errors.LoginFailure:
        print("\n!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
        print("!!! ERRO CRÍTICO: Login falhou. O BOT_TOKEN é inválido?")
        print("!!! Verifique o 'DUVIDAS_BOT_TOKEN' no .env e as Intents no Portal Dev.")
        print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
    except discord.errors.PrivilegedIntentsRequired:
         print("\n!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
         print("!!! ERRO CRÍTICO: Intents Privilegiadas         !!!")
         print("!!!   necessárias (Message Content / Members)   !!!")
         print("!!!   não estão ativadas no Portal Dev Discord. !!!")
         print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
    except Exception as e:
        print(f"\nErro inesperado ao rodar o bot: {e}")