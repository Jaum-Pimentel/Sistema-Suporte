import sys
from app import app, db, User

def delete_user():
    """
    Script para remover um usuário do banco de dados de forma segura.
    """
    if len(sys.argv) < 2:
        print("ERRO: Você precisa especificar o nome de usuário que deseja remover.")
        print("Uso: python delete_user.py <username>")
        return

    username_to_delete = sys.argv[1]

    with app.app_context():
        # Busca o usuário no banco de dados (ignorando maiúsculas/minúsculas)
        user = User.query.filter(db.func.lower(User.username) == db.func.lower(username_to_delete)).first()

        if not user:
            print(f"ERRO: Usuário '{username_to_delete}' não encontrado.")
            return

        print(f"Usuário encontrado: {user.username} (ID: {user.id})")
        
        # --- ETAPA DE CONFIRMAÇÃO ---
        # Esta é a parte mais importante para evitar acidentes!
        confirm = input(f"Você tem CERTEZA ABSOLUTA que deseja remover o usuário '{user.username}'? \nEsta ação não pode ser desfeita. Digite 'S' para confirmar ou 'N' para cancelar: ")

        if confirm.lower() != 's':
            print("Operação cancelada.")
            return

        try:
            # Remove o usuário da sessão do banco de dados
            db.session.delete(user)
            # Efetiva a remoção no banco de dados
            db.session.commit()
            print(f"Sucesso! O usuário '{user.username}' foi removido permanentemente.")
        except Exception as e:
            db.session.rollback() # Desfaz a tentativa em caso de erro
            print(f"Ocorreu um erro ao tentar remover o usuário: {e}")
            print("Isso pode acontecer se o usuário for 'dono' de outros registros no sistema (como tickets ou posições na fila). Verifique as dependências.")


if __name__ == '__main__':
    delete_user()