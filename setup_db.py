import os
from app import app, db, User, Column, Card, PhoneQueueMember, PhoneQueueState

print("Iniciando o script de setup do banco de dados...")

with app.app_context():
    # 1. Cria as tabelas se não existirem
    db.create_all()
    print("Tabelas verificadas/criadas.")

    # 2. Cria as Colunas do Kanban (se não existirem)
    if Column.query.count() == 0:
        colunas_kanban = [
            "Procedimentos a fazer", "Comportamento para analisar", "Pedir ajuda",
            "Abrir ticket", "Rascunho", "Resolvidos"
        ]
        print("Criando colunas padrão do Kanban...")
        for i, nome_coluna in enumerate(colunas_kanban):
            nova_coluna = Column(name=nome_coluna, order=i)
            db.session.add(nova_coluna)
        db.session.commit()
        print("Colunas do Kanban criadas.")
    else:
        print("Colunas do Kanban já existem.")

    # 3. CRIAÇÃO DA FILA TELEFÔNICA
    # =====================================================================

    # Lista com os seus NOMES DE USUÁRIO (login) na ordem desejada
    ORDEM_DA_FILA = ["Erick123", "Gerson123", "Jaum1.", "Vinicius.ferreira", "Arlen123", "Carol123", "Caio"]
    
    print("\n--- Configurando a Fila Telefônica ---")

    # Limpa a fila antiga para garantir que começaremos do zero
    PhoneQueueMember.query.delete()
    PhoneQueueState.query.delete()
    print("Fila antiga apagada.")

    usuarios_encontrados = []
    for username in ORDEM_DA_FILA:
        # Busca o usuário ignorando maiúsculas/minúsculas
        user = User.query.filter(db.func.lower(User.username) == db.func.lower(username)).first()
        if user:
            usuarios_encontrados.append(user)
            print(f"Usuário '{user.username}' encontrado.")
        else:
            print(f"ATENÇÃO: Usuário '{username}' não encontrado no banco. Ele será pulado.")

    if not usuarios_encontrados:
        print("Nenhum usuário da lista foi encontrado. A fila não será criada.")
    else:
        # Adiciona os usuários na fila na ordem definida
        for i, user in enumerate(usuarios_encontrados):
            novo_membro = PhoneQueueMember(user_id=user.id, position=i)
            db.session.add(novo_membro)
        
        # Define o primeiro usuário da lista como o atendente atual
        primeiro_da_fila_id = str(usuarios_encontrados[0].id)
        estado_atual = PhoneQueueState(key='current_user_id', value=primeiro_da_fila_id)
        db.session.add(estado_atual)
        
        db.session.commit()
        print(f"Fila criada com sucesso com {len(usuarios_encontrados)} membros!")
        print(f"O primeiro a atender é: '{usuarios_encontrados[0].username}'.")

print("\nScript de setup finalizado com sucesso!")

