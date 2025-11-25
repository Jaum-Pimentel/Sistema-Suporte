import os
import requests
import random
from flask import Flask, render_template, url_for, redirect, flash, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, TextAreaField, SelectField, TimeField
from wtforms.validators import DataRequired, Email, EqualTo, Length, ValidationError, Optional
from flask_login import UserMixin, login_user, LoginManager, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

# ------------------- CONFIGURAÇÃO DA APLICAÇÃO -------------------
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///site.db'
app.config['SECRET_KEY'] = 'uma-chave-secreta-muito-dificil-de-adivinhar'

# URL do Bot do Discord (configure se necessário)
DISCORD_BOT_URL = "http://127.0.0.1:5001/notify"
csrf = CSRFProtect(app)
db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# ------------------- MODELOS DO BANCO DE DADOS -------------------

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    discord_id = db.Column(db.String(50), nullable=True, unique=True)
    lunch_start = db.Column(db.Time, nullable=True)
    lunch_end = db.Column(db.Time, nullable=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Column(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    order = db.Column(db.Integer, nullable=False)

class Card(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    base = db.Column(db.String(50), nullable=True)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=True)
    link = db.Column(db.String(300), nullable=True)
    status = db.Column(db.String(20), default='pendente', nullable=False)
    column_id = db.Column(db.Integer, db.ForeignKey('column.id'), nullable=False)
    owner_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)

class PhoneQueueMember(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    position = db.Column(db.Integer, nullable=False)
    user = db.relationship('User')

class PhoneQueueState(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(50), unique=True, nullable=False)
    value = db.Column(db.String(50), nullable=False)

# --- NOVOS MODELOS PARA TICKETS DO DISCORD ---
class DiscordTicket(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    description = db.Column(db.Text, nullable=False)
    link = db.Column(db.String(300), nullable=False)
    status = db.Column(db.String(20), default='aberto', nullable=False) # aberto, resolvido
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    follow_ups = db.relationship('TicketFollowUp', backref='ticket', lazy=True, cascade="all, delete-orphan")

class TicketFollowUp(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    return_link = db.Column(db.String(300), nullable=False)
    ticket_id = db.Column(db.Integer, db.ForeignKey('discord_ticket.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    user = db.relationship('User')

# ------------------- FORMULÁRIOS (Flask-WTF) -------------------

class RegistrationForm(FlaskForm):
    name = StringField('Nome Completo', validators=[DataRequired(), Length(min=2, max=150)])
    username = StringField('Nome de Usuário (Login)', validators=[DataRequired(), Length(min=4, max=80)])
    email = StringField('Email', validators=[DataRequired(), Email()])
    discord_id = StringField('ID do Discord', validators=[Optional(), Length(min=17, max=20)])
    password = PasswordField('Senha', validators=[DataRequired(), Length(min=6)])
    confirm_password = PasswordField('Confirmar Senha', validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField('Criar Conta')

    def validate_username(self, username):
        user = User.query.filter_by(username=username.data).first()
        if user:
            raise ValidationError('Este nome de usuário já existe.')

    def validate_email(self, email):
        user = User.query.filter_by(email=email.data).first()
        if user:
            raise ValidationError('Este email já está cadastrado.')

    def validate_discord_id(self, discord_id):
        if discord_id.data:
            user = User.query.filter_by(discord_id=discord_id.data).first()
            if user:
                raise ValidationError('Este ID do Discord já está cadastrado.')

class LoginForm(FlaskForm):
    username = StringField('Nome de Usuário', validators=[DataRequired()])
    password = PasswordField('Senha', validators=[DataRequired()])
    submit = SubmitField('Entrar')

class CardForm(FlaskForm):
    base = StringField('Base', validators=[Optional(), Length(max=50)])
    title = TextAreaField('Texto Principal', validators=[DataRequired(), Length(max=200)])
    content = TextAreaField('Descrição Adicional', validators=[Optional()])
    link = StringField('Link', validators=[Optional(), Length(max=300)])
    status = SelectField('Status', choices=[
        ('pendente', 'Pendente'),
        ('urgente', 'Urgente'),
        ('resolvido', 'Resolvido')
    ], validators=[DataRequired()])
    submit = SubmitField('Salvar Ticket')

# ------------------- ROTAS / VIEWS (As Páginas) -------------------

@app.route('/')
@login_required
def index():
    return redirect(url_for('kanban_individual'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user and user.check_password(form.password.data):
            login_user(user)
            return redirect(url_for('index'))
        else:
            flash('Login inválido. Verifique seu usuário e senha.', 'danger')
    return render_template('login.html', title='Login', form=form)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    form = RegistrationForm()
    if form.validate_on_submit():
        user = User(
            name=form.name.data,
            username=form.username.data,
            email=form.email.data,
            discord_id=form.discord_id.data or None
        )
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()
        flash('Sua conta foi criada com sucesso! Você já pode fazer o login.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html', title='Registro', form=form)

@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('login'))

# --- ROTAS DO KANBAN ---

@app.route('/kanban/individual')
@login_required
def kanban_individual():
    columns = Column.query.order_by(Column.order).all()
    cards = Card.query.filter_by(owner_id=current_user.id).all()
    form = CardForm()
    return render_template('kanban_board.html', title="Minha Gestão", columns=columns, cards=cards, board_type='individual', form=form)

@app.route('/kanban/grupo')
@login_required
def kanban_grupo():
    columns = Column.query.order_by(Column.order).all()
    cards = Card.query.filter_by(owner_id=None).all()
    form = CardForm()
    return render_template('kanban_board.html', title="Gestão em Grupo", columns=columns, cards=cards, board_type='group', form=form)

# --- ROTAS DA API DO KANBAN ---

@app.route('/card/new/<int:column_id>/<board_type>', methods=['POST'])
@login_required
def add_card(column_id, board_type):
    form = CardForm()
    if form.validate_on_submit():
        owner = current_user.id if board_type == 'individual' else None
        new_card = Card(
            base=form.base.data,
            title=form.title.data,
            content=form.content.data,
            link=form.link.data,
            status=form.status.data,
            column_id=column_id,
            owner_id=owner
        )
        db.session.add(new_card)
        db.session.commit()
        flash('Ticket criado com sucesso!', 'success')
    else:
        error_message = next(iter(form.errors.values()))[0] if form.errors else 'Erro desconhecido.'
        flash(f'Erro ao criar o ticket: {error_message}', 'danger')
    
    return redirect(url_for('kanban_individual' if board_type == 'individual' else 'kanban_grupo'))

@app.route('/card/edit/<int:card_id>', methods=['POST'])
@login_required
def edit_card(card_id):
    card = Card.query.get_or_404(card_id)
    if not (card.owner_id is None or card.owner_id == current_user.id):
        flash('Você não tem permissão para editar este ticket.', 'danger')
        return redirect(request.referrer or url_for('index'))
    
    form = CardForm()
    if form.validate_on_submit():
        card.base = form.base.data
        card.title = form.title.data
        card.content = form.content.data
        card.link = form.link.data
        card.status = form.status.data
        db.session.commit()
        flash('Ticket atualizado com sucesso!', 'success')
    else:
        flash('Erro ao atualizar o ticket.', 'danger')

    return redirect(request.referrer or url_for('index'))

@app.route('/card/move', methods=['POST'])
@login_required
def move_card():
    data = request.get_json()
    card = Card.query.get(data.get('card_id'))
    if card and (card.owner_id is None or card.owner_id == current_user.id):
        card.column_id = data.get('new_column_id')
        db.session.commit()
        return jsonify({'success': True})
    return jsonify({'success': False, 'message': 'Permissão negada ou card não encontrado.'}), 403

@app.route('/card/details/<int:card_id>')
@login_required
def card_details(card_id):
    card = Card.query.get_or_404(card_id)
    if card.owner_id is None or card.owner_id == current_user.id:
        return jsonify({
            'id': card.id, 'base': card.base, 'title': card.title,
            'content': card.content, 'link': card.link, 'status': card.status
        })
    return jsonify({'error': 'Acesso negado'}), 403

@app.route('/card/delete/<int:card_id>', methods=['POST'])
@login_required
def delete_card(card_id):
    card = Card.query.get_or_404(card_id)
    if card.owner_id is None or card.owner_id == current_user.id:
        db.session.delete(card)
        db.session.commit()
        return jsonify({'success': True})
    return jsonify({'success': False, 'message': 'Permissão negada.'}), 403

# --- ROTAS DA FILA TELEFÔNICA ---

@app.route('/fila-telefonica')
@login_required
def fila_telefonica():
    queue_members = PhoneQueueMember.query.order_by(PhoneQueueMember.position).all()
    current_state = PhoneQueueState.query.filter_by(key='current_user_id').first()
    
    current_attendant_id = None
    if current_state and current_state.value.isdigit():
        current_attendant_id = int(current_state.value)
    elif queue_members:
        current_attendant_id = queue_members[0].user_id
    
    queue_user_ids = [member.user_id for member in queue_members]

    return render_template('fila_telefonica.html', 
                           title="Fila Telefônica", 
                           queue_members=queue_members, 
                           current_attendant_id=current_attendant_id,
                           queue_user_ids=queue_user_ids)

@app.route('/fila-telefonica/atender', methods=['POST'])
@login_required
def atender_telefone():
    queue_members = PhoneQueueMember.query.order_by(PhoneQueueMember.position).all()
    if not queue_members:
        flash("A fila telefônica está vazia.", "warning")
        return redirect(url_for('fila_telefonica'))

    atendente_que_atendeu = current_user
    flash(f"{atendente_que_atendeu.name} atendeu o telefone.", "info")

    current_index_list = [i for i, member in enumerate(queue_members) if member.user_id == atendente_que_atendeu.id]
    
    if not current_index_list:
        flash(f"{atendente_que_atendeu.name} atendeu, mas não estava na fila configurada. A fila não foi alterada.", "warning")
        return redirect(url_for('fila_telefonica'))
    
    current_index = current_index_list[0]
    
    next_index = (current_index + 1) % len(queue_members)
    next_member = queue_members[next_index]
    
    state = PhoneQueueState.query.filter_by(key='current_user_id').first()
    if not state:
        state = PhoneQueueState(key='current_user_id', value=str(next_member.user_id))
        db.session.add(state)
    else:
        state.value = str(next_member.user_id)
    db.session.commit()
            
    frases_divertidas = [
        "Atenção, marujo! O próximo navio (ligação) é seu!",
        "Acorda pra vida e reinicia o Zoiper, o próximo telefone é seu!",
        "Alôôôu! Já verifica o Zoiper, pois o próximo é seu.",
        "Sua hora chegou! Prepare-se, a próxima ligação é sua.",
        "Foguete não tem ré! A próxima chamada está na sua mira."
    ]
    
    mensagem_sorteada = random.choice(frases_divertidas)
    
    if next_member.user.discord_id:
        try:
            message_to_send = f"Olá {next_member.user.name}, {mensagem_sorteada}"
            payload = {'discord_id': next_member.user.discord_id, 'message': message_to_send}
            requests.post(DISCORD_BOT_URL, json=payload, timeout=3)
            flash(f"Notificação enviada para {next_member.user.name} no Discord!", "success")
        except requests.exceptions.RequestException:
            flash("A fila avançou, mas não foi possível notificar no Discord. O bot está online?", "danger")
    else:
        flash(f"A fila avançou para {next_member.user.name}, mas este usuário não tem um ID do Discord cadastrado.", "warning")
        
    return redirect(url_for('fila_telefonica'))

@app.route('/configurar-fila', methods=['GET', 'POST'])
@login_required
def configurar_fila():
    if request.method == 'POST':
        details_user_id = request.form.get('details_user_id')
        if details_user_id and details_user_id.isdigit():
            user_to_update = User.query.get(int(details_user_id))
            if user_to_update:
                discord_id_val = request.form.get('discord_id_details')
                user_to_update.discord_id = discord_id_val if discord_id_val else None
                
                lunch_start_str = request.form.get('lunch_start_details')
                lunch_end_str = request.form.get('lunch_end_details')
                user_to_update.lunch_start = datetime.strptime(lunch_start_str, '%H:%M').time() if lunch_start_str else None
                user_to_update.lunch_end = datetime.strptime(lunch_end_str, '%H:%M').time() if lunch_end_str else None

        PhoneQueueMember.query.delete()
        user_ids_in_order = request.form.get('queue_order', '').split(',')
        
        if user_ids_in_order and user_ids_in_order[0]:
            for i, user_id_str in enumerate(user_ids_in_order):
                if user_id_str.isdigit():
                    member = PhoneQueueMember(user_id=int(user_id_str), position=i)
                    db.session.add(member)
            
            state = PhoneQueueState.query.filter_by(key='current_user_id').first()
            if not state:
                state = PhoneQueueState(key='current_user_id', value=user_ids_in_order[0])
                db.session.add(state)
            else:
                state.value = user_ids_in_order[0]
        else:
            PhoneQueueState.query.filter_by(key='current_user_id').delete()

        db.session.commit()
        flash("Fila e dados dos usuários atualizados com sucesso!", "success")
        return redirect(url_for('configurar_fila'))

    all_users = User.query.all()
    queue_members = PhoneQueueMember.query.order_by(PhoneQueueMember.position).all()
    queue_user_ids = {member.user_id for member in queue_members}
    
    return render_template('configurar_fila.html', 
                           title="Configurar Fila", 
                           all_users=all_users, 
                           queue_members=queue_members,
                           queue_user_ids=queue_user_ids)

@app.route('/get_user_details/<int:user_id>')
@login_required
def get_user_details(user_id):
    user = User.query.get_or_404(user_id)
    return jsonify({
        'id': user.id,
        'discord_id': user.discord_id or '',
        'lunch_start': user.lunch_start.strftime('%H:%M') if user.lunch_start else '',
        'lunch_end': user.lunch_end.strftime('%H:%M') if user.lunch_end else ''
    })

# --- NOVAS ROTAS PARA TICKETS FRESHDESK ---

@app.route('/tickets-freshdesk')
@login_required
def tickets_freshdesk():
    tickets = DiscordTicket.query.filter_by(status='aberto').order_by(DiscordTicket.created_at.desc()).all()
    return render_template('tickets_freshdesk.html', title="Tickets Abertos", tickets=tickets)

@app.route('/tickets-retornar')
@login_required
def tickets_retornar():
    follow_ups = TicketFollowUp.query.filter_by(user_id=current_user.id).order_by(TicketFollowUp.id.desc()).all()
    
    abertos = [f for f in follow_ups if f.ticket.status == 'aberto']
    resolvidos = [f for f in follow_ups if f.ticket.status == 'resolvido']
    
    return render_template('tickets_retornar.html', title="Tickets para Retornar", abertos=abertos, resolvidos=resolvidos)

# --- NOVAS ROTAS DE API PARA O BOT E FRONTEND ---

@app.route('/api/new_discord_ticket', methods=['POST'])
def api_new_discord_ticket():
    data = request.json
    description = data.get('description')
    link = data.get('link')

    if not description or not link:
        return jsonify({'status': 'error', 'message': 'Descrição e link são obrigatórios'}), 400

    new_ticket = DiscordTicket(description=description, link=link)
    db.session.add(new_ticket)
    db.session.commit()
    
    return jsonify({'status': 'success', 'message': 'Ticket criado com sucesso'}), 201

@app.route('/ticket/resolver/<int:ticket_id>', methods=['POST'])
@login_required
def resolver_ticket(ticket_id):
    ticket = DiscordTicket.query.get_or_404(ticket_id)
    ticket.status = 'resolvido'
    db.session.commit()
    flash(f"Ticket #{ticket.id} marcado como resolvido!", "success")
    return redirect(url_for('tickets_freshdesk'))

@app.route('/ticket/acompanhar/<int:ticket_id>', methods=['POST'])
@login_required
def acompanhar_ticket(ticket_id):
    retorno_link = request.form.get('retorno_link')
    
    if not retorno_link:
        flash("O link de retorno é obrigatório para acompanhar um ticket.", "danger")
        return redirect(url_for('tickets_freshdesk'))

    new_follow_up = TicketFollowUp(
        return_link=retorno_link,
        ticket_id=ticket_id,
        user_id=current_user.id
    )
    db.session.add(new_follow_up)
    db.session.commit()
    
    flash(f"Você agora está acompanhando o ticket #{ticket_id} com um novo retorno.", "success")
    return redirect(url_for('tickets_freshdesk'))

@app.route('/followup/mark-seen/<int:followup_id>', methods=['POST'])
@login_required
def mark_followup_seen(followup_id):
    follow_up = TicketFollowUp.query.get_or_404(followup_id)
    if follow_up.user_id == current_user.id:
        # Assumindo que você adicionará uma coluna 'notified_seen' ao modelo TicketFollowUp
        # follow_up.notified_seen = True 
        db.session.commit()
    return redirect(url_for('tickets_retornar'))

# --- BLOCO PARA RODAR O SERVIDOR ---
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)