import requests
import time
from datetime import datetime, timedelta

# Importa a aplicação e os modelos do seu arquivo principal
from app import app, db, Reminder, EventType, EventLog

# URL para onde o agendador vai enviar os comandos DE LEMBRETE
REMINDER_BOT_URL = "http://127.0.0.1:5002/notify_reminder"
# ID do canal de gestão para LEMBRETES
GESTOR_CHANNEL_ID = 1427677426720313446

# --- CONFIGURAÇÃO PARA O RESUMO DE EVENTOS ---
RESUMO_BOT_URL = "http://127.0.0.1:5005/notify"
# ID do canal onde o RESUMO DIÁRIO DE EVENTOS será postado
RESUMO_CHANNEL_ID = 1429493985851998331 # (Canal de publicações, por exemplo)
# --- FIM DA CONFIGURAÇÃO ---


# --- Variável global para rastrear o último dia que o resumo foi enviado ---
ultimo_resumo_enviado = None
# --- Fim da variável ---


def check_and_send_reminders():
    """
    Verifica e envia lembretes pendentes. (Função corrigida)
    """
    try:
        with app.app_context():
            
            # ==========================================================
            # === CORREÇÃO APLICADA AQUI ===
            # Compara datetime com datetime para a query
            now_brasilia = datetime.utcnow() - timedelta(hours=3)
            # ==========================================================

            reminders_to_send = Reminder.query.filter(
                # Compara a coluna datetime com o objeto datetime 'now_brasilia'
                Reminder.reminder_datetime <= now_brasilia, 
                Reminder.is_sent == False
            ).all()

            if not reminders_to_send:
                print(f"[{now_brasilia.strftime('%H:%M:%S')}] Nenhum lembrete para enviar.")
                return

            print(f"[{now_brasilia.strftime('%H:%M:%S')}] Encontrados {len(reminders_to_send)} lembretes!")
            
            for rem in reminders_to_send:
                # Verificação extra para garantir que user está carregado
                if not rem.user:
                    print(f"  -> ERRO: Lembrete {rem.id} não possui usuário associado. Pulando.")
                    continue
                    
                print(f"  -> Enviando lembrete ID {rem.id} para o usuário {rem.user.name}...")
                
                reminder_display_time = rem.reminder_datetime.strftime('%d/%m/%Y às %H:%M')

                embed_data = {
                    "title": f"🔔 Lembrete: {rem.reminder_type}",
                    "description": rem.description or "Nenhuma descrição informada.",
                    "color": 16766720, # Dourado
                    "fields": [
                        {"name": "Agendado para", "value": reminder_display_time, "inline": False}
                    ],
                    "footer": {"text": f"ID Lembrete: {rem.id}"}
                }
                if rem.link:
                    embed_data["fields"].append(
                        {"name": "Link de Referência", "value": f"[Acessar Link]({rem.link})", "inline": False}
                    )

                payload = {
                    "creator_discord_id": rem.user.discord_id,
                    "gestor_channel_id": GESTOR_CHANNEL_ID, # Envia o ID do canal do gestor
                    "embed": embed_data
                }

                try:
                    response = requests.post(REMINDER_BOT_URL, json=payload, timeout=5)
                    if response.status_code == 200:
                        print(f"  -> Comando enviado com sucesso para o bot.")
                        rem.is_sent = True
                        db.session.commit() # Commita a cada sucesso
                    else:
                        print(f"  -> ERRO: O bot retornou status {response.status_code}")
                except requests.exceptions.RequestException as e:
                    print(f"  -> ERRO CRÍTICO: Não foi possível conectar ao bot de lembretes ({REMINDER_BOT_URL}). Ele está rodando? Erro: {e}")
    except Exception as e:
        print(f"ERRO GERAL no check_and_send_reminders: {e}")
        db.session.rollback() # Garante rollback em caso de falha


# --- FUNÇÃO PARA O RESUMO DIÁRIO DE EVENTOS (Sem alterações) ---
def check_and_send_daily_summary():
    """
    Verifica se são 18:10 (BRT) ou mais e envia o resumo diário de eventos.
    """
    global ultimo_resumo_enviado
    
    try:
        now_brasilia = datetime.utcnow() - timedelta(hours=3)
        hoje_data = now_brasilia.date() 

        # 1. Verifica se já enviamos o resumo hoje OU se ainda não deu 18:10
        if (ultimo_resumo_enviado == hoje_data) or (now_brasilia.hour < 18) or (now_brasilia.hour == 18 and now_brasilia.minute < 15):
            return
            
        print(f"[{now_brasilia.strftime('%H:%M:%S')}] Hora de enviar o resumo diário (18:10+)! Gerando contagem...")

        # 2. Define o período de "hoje" (00:00:00 até 23:59:59 em BRT)
        inicio_dia_utc = datetime(hoje_data.year, hoje_data.month, hoje_data.day, 3, 0, 0) # 00:00 BRT
        fim_dia_utc = inicio_dia_utc + timedelta(days=1) # 00:00 BRT do dia seguinte

        # 3. Executa a query
        with app.app_context():
            contagem_hoje = db.session.query(
                EventType.name, 
                db.func.count(EventLog.id)
            ).join(EventLog, EventType.id == EventLog.event_type_id)\
             .filter(
                EventLog.timestamp >= inicio_dia_utc,
                EventLog.timestamp < fim_dia_utc
            ).group_by(EventType.name).order_by(db.func.count(EventLog.id).desc()).all()

        # 4. Monta a mensagem
        if not contagem_hoje:
            mensagem_discord = f"**📊 Resumo de Eventos do App - {hoje_data.strftime('%d/%m/%Y')}**\n\nNenhum evento foi registrado hoje."
        else:
            mensagem_discord = f"**📊 Resumo de Eventos do App - {hoje_data.strftime('%d/%m/%Y')}**\n\n"
            total_eventos = 0
            for evento, contagem in contagem_hoje:
                mensagem_discord += f"• **{contagem}x** - {evento}\n"
                total_eventos += contagem
            mensagem_discord += f"\n**Total de Eventos:** {total_eventos}"

        # 5. Envia para o bot de notificações (porta 5005)
        # Assumindo que o bot 5005 usa um webhook ou tem um canal fixo
        payload = { 'message': mensagem_discord }
        
        # Se o bot 5005 precisar de um ID de canal, use este payload:
        # payload = {'channel_id': RESUMO_CHANNEL_ID, 'message': mensagem_discord}
        
        response = requests.post(RESUMO_BOT_URL, json=payload, timeout=5)
        response.raise_for_status() 
        
        print(f"  -> Resumo diário enviado com sucesso para {RESUMO_BOT_URL}.")
        
        # 6. Marca como enviado para hoje
        ultimo_resumo_enviado = hoje_data

    except requests.exceptions.RequestException as e:
        print(f"  -> ERRO CRÍTICO: Não foi possível conectar ao bot de resumo ({RESUMO_BOT_URL}). Ele está rodando? Erro: {e}")
    except Exception as e:
        print(f"ERRO GERAL no check_and_send_daily_summary: {e}")
        # Se a query falhar, o app_context já lida com o session
        # db.session.rollback() # Não é necessário fora do 'with'

# --- FIM DA NOVA FUNÇÃO ---


if __name__ == "__main__":
    print("Iniciando o Agendador (Verifica a cada 60s)...")
    # Zera o 'ultimo_resumo_enviado' ao iniciar, para garantir que envie 
    # no primeiro dia se o scheduler for reiniciado depois das 18:10
    ultimo_resumo_enviado = (datetime.utcnow() - timedelta(hours=3, days=1)).date() # Marca como se tivesse enviado "ontem"
    print(f"Último resumo marcado como 'ontem' ({ultimo_resumo_enviado}) para forçar o envio hoje.")

    while True:
        try:
            # 1. Verifica lembretes pendentes
            check_and_send_reminders()
            
            # 2. Verifica se é hora do resumo diário
            check_and_send_daily_summary()

        except Exception as e_loop:
            print(f"ERRO INESPERADO NO LOOP PRINCIPAL DO SCHEDULER: {e_loop}")
        
        # Espera 60 segundos
        time.sleep(60)