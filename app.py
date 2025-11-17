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
from sqlalchemy import extract
from flask_migrate import Migrate
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from datetime import datetime
from sqlalchemy import desc, asc
from datetime import datetime, timedelta
import pandas as pd
from flask import send_file
import io
from flask_login import current_user, login_required
from flask_wtf.csrf import CSRFProtect
from wtforms.fields import DateField
from flask_mail import Mail, Message
import string
import random
import uuid # Para gerar nomes de arquivo únicos
from werkzeug.utils import secure_filename # Para limpar nomes de arquivos
import markdown # <-- ADICIONE ESTA
from markupsafe import Markup #
from sqlalchemy.orm import joinedload
from functools import wraps
from wtforms import StringField, PasswordField, SubmitField, TextAreaField, SelectField, TimeField, BooleanField # <-- ADICIONE BooleanField
from wtforms.validators import DataRequired, Email, EqualTo, Length, ValidationError, Optional
# ------------------- 1. CONFIGURAÇÃO DA APLICAÇÃO -------------------
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///site.db'
app.config['SECRET_KEY'] = 'uma-chave-secreta-muito-dificil-de-adivinhar'
BOT_RESOLVED_NOTIFICATION_URL = "http://127.0.0.1:8080/notify-resolved"
DISCORD_BOT_URL = "http://127.0.0.1:5001/notify" 
QUERY_BOT_URL = "http://127.0.0.1:5003"
GENERAL_NOTIFICATION_BOT_URL = "http://127.0.0.1:5005/notify" # Bot para Guias, Links, etc.
# --- Configuração para Dúvidas ---
DUVIDAS_BOT_URL = os.getenv("DUVIDAS_BOT_URL", "http://127.0.0.1:5006/criar-topico-duvida") # Ex: porta 5006
API_SECRET_KEY = os.getenv("FLASK_API_SECRET", "mude-para-algo-bem-secreto-e-dificil") # Mude isso! Use variável de ambiente!
# --- Fim Configuração Dúvidas ---

# --- CONFIGURAÇÃO DO FLASK-MAIL ---
# ATENÇÃO: Use variáveis de ambiente para isso no futuro!
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'envioemailelev@gmail.com'  # <-- SEU E-MAIL DO GMAIL
app.config['MAIL_PASSWORD'] = 'vvrr gppy likp iqgz'      # <-- SUA SENHA DE APP (veja abaixo)


mail = Mail(app)
# --- FIM DA CONFIGURAÇÃO ---


db = SQLAlchemy(app)
migrate = Migrate(app, db)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

CATEGORIAS_COMPORTAMENTO = [
    'Tarefa', 'Equipamento', 'Cliente', 'Produto', 'Colaborador', 
    'Financeiro', 'PMOC', 'Auvodesk', 'Auvochat','Orçamento', 'Relatorio', 'Projeto', 
    'Configurações gerais', 'Check-list', 'Mapa', 'Integração', 'Outros'
]
# --- ADICIONE PERTO DE CATEGORIAS_COMPORTAMENTO ---
# Lista dos tipos de eventos que queremos registrar
TIPOS_DE_EVENTO = [
    'Desligar/Reiniciar Aparelho',
    'Encerrar App (Forçar Parada)',
    'Errar Login',
    'Limpar Cache',
    'Sync Descida Manual',
    'Sync Subida Manual',
    'Cálculo de pendência Web'
]

# ------------------- FUNÇÕES AUXILIARES E PROCESSADORES DE CONTEXTO -------------------
def get_favicon_url(target_url):
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(target_url, headers=headers, timeout=5, allow_redirects=True)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'lxml')
        icon_link = soup.find('link', rel='apple-touch-icon') or \
                    soup.find('link', rel='icon') or \
                    soup.find('link', rel='shortcut icon')
        if icon_link and icon_link.get('href'):
            return urljoin(response.url, icon_link['href'])
        else:
            fallback_url = urljoin(response.url, '/favicon.ico')
            if requests.get(fallback_url, headers=headers, timeout=3).status_code == 200:
                return fallback_url
    except requests.exceptions.RequestException as e:
        print(f"Erro ao buscar o favicon para {target_url}: {e}")
    return None

def calculate_average_time(records):
    if not records: return "00:00"
    total_seconds = sum(r.time_in_seconds for r in records)
    avg_seconds = total_seconds / len(records)
    avg_minutes = int(avg_seconds // 60)
    avg_remaining_seconds = int(avg_seconds % 60)
    return f"{avg_minutes:02d}:{avg_remaining_seconds:02d}"

@app.context_processor
def inject_now():
    return {'now': datetime.utcnow()}

@app.template_filter('brt')
def format_datetime_brt(dt):
    """Converte um datetime UTC para string formatada em BRT (UTC-3)."""
    if not dt:
        return "N/A"
    try:
        dt_brt = dt - timedelta(hours=3)
        return dt_brt.strftime('%d/%m/%Y às %H:%M')
    except Exception:
        return "Data Inválida"
# ------------------- 2. MODELOS DO BANCO DE DADOS -------------------
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
    is_admin = db.Column(db.Boolean, nullable=False, default=False)
    manager_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True) # <<< ADICIONADO AQUI
    lunch_start = db.Column(db.Time, nullable=True)
    lunch_end = db.Column(db.Time, nullable=True)
    def set_password(self, password): self.password_hash = generate_password_hash(password)
    def check_password(self, password): return check_password_hash(self.password_hash, password)

# Em app.py, na seção FORMULÁRIOS

class AdminEditUserForm(FlaskForm):
    # Armazena o ID do usuário original para validação
    original_username = StringField('Username Original', validators=[DataRequired()])
    original_email = StringField('Email Original', validators=[DataRequired()])
    
    # Campos editáveis
    name = StringField('Nome Completo', validators=[DataRequired(), Length(min=2, max=150)])
    username = StringField('Nome de Usuário (Login)', validators=[DataRequired(), Length(min=4, max=80)])
    email = StringField('Email', validators=[DataRequired(), Email()])
    discord_id = StringField('ID do Discord', validators=[Optional(), Length(min=17, max=20)])
    
    # Checkbox para status de admin
    is_admin = BooleanField('É Administrador?')
    
    # Opção de resetar senha (admin não deve ver a senha antiga)
    password = PasswordField('Nova Senha (Opcional)', validators=[Optional(), Length(min=6)])
    confirm_password = PasswordField('Confirmar Nova Senha', validators=[EqualTo('password', message='As senhas não coincidem.')])
    
    submit = SubmitField('Salvar Alterações')

    # Validador customizado para username (checa se já existe, ignorando o usuário atual)
    def validate_username(self, username):
        if username.data != self.original_username.data and User.query.filter_by(username=username.data).first():
            raise ValidationError('Este nome de usuário já está em uso por outra conta.')

    # Validador customizado para email
    def validate_email(self, email):
        if email.data != self.original_email.data and User.query.filter_by(email=email.data).first():
            raise ValidationError('Este email já está em uso por outra conta.')

class RequestResetForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    submit = SubmitField('Redefinir Senha')

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

class ServiceTime(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    time_in_seconds = db.Column(db.Integer, nullable=False)
    date_recorded = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    user = db.relationship('User', backref='service_times')

class DiscordTicket(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    description = db.Column(db.Text, nullable=False)
    link = db.Column(db.String(300), nullable=False)
    status = db.Column(db.String(20), default='aberto', nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    follow_ups = db.relationship('TicketFollowUp', backref='ticket', lazy=True, cascade="all, delete-orphan")
    

class TicketFollowUp(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    return_link = db.Column(db.String(300), nullable=False)
    ticket_id = db.Column(db.Integer, db.ForeignKey('discord_ticket.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    user = db.relationship('User')

class QueryRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    description = db.Column(db.Text, nullable=False)
    sql_query = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(20), default='Pendente', nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    answered_at = db.Column(db.DateTime, nullable=True)
    requester_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    responder_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    requester = db.relationship('User', foreign_keys=[requester_id])
    responder = db.relationship('User', foreign_keys=[responder_id])

class Guia(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    titulo = db.Column(db.String(200), nullable=False)
    conteudo = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    author_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    author = db.relationship('User')

class Comportamento(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    titulo = db.Column(db.String(200), nullable=False)
    conteudo = db.Column(db.Text, nullable=False)
    categoria = db.Column(db.String(100), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    author_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    author = db.relationship('User')
    

class QuickLink(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    url = db.Column(db.String(500), nullable=False)
    icon_url = db.Column(db.String(500), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Reminder(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    reminder_type = db.Column(db.String(50), nullable=False)
    description = db.Column(db.Text, nullable=True)
    link = db.Column(db.String(500), nullable=True)
    reminder_datetime = db.Column(db.DateTime, nullable=False)
    is_sent = db.Column(db.Boolean, default=False, nullable=False) # Para o bot saber se já notificou
    notification_status = db.Column(db.String(100), nullable=True) 
    created_at = db.Column(db.DateTime, default=db.func.now())
    # Relação para que possamos fazer `reminder.user.name`
    user = db.relationship('User', backref=db.backref('reminders', lazy=True))
    def __repr__(self):
        return f'<Reminder {self.id} for {self.user.username}>'
 # --- NOVOS MODELOS PARA REGISTRO DE EVENTOS ---
class EventType(db.Model):
    """Armazena os nomes dos eventos que podem ser registrados."""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    
    logs = db.relationship('EventLog', backref='event_type', lazy=True, cascade="all, delete-orphan")
    
    def __repr__(self):
        return f'<EventType {self.name}>'

class EventLog(db.Model):
    """Registra cada ocorrência de um evento."""
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)
    
    # Chave estrangeira para o usuário que registrou
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    # Chave estrangeira para o tipo de evento
    event_type_id = db.Column(db.Integer, db.ForeignKey('event_type.id'), nullable=False)
    
    # Relacionamentos
    user = db.relationship('User', backref='event_logs')
    # event_type já definido pelo backref
    
    def __repr__(self):
        return f'<EventLog {self.id} por {self.user_id} em {self.timestamp}>'
# --- FIM DOS NOVOS MODELOS ---   
# --- DECORADOR DE ADMIN ---
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            flash('Você não tem permissão para acessar esta página.', 'danger')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function
# --- FIM DO DECORADOR ---
# --- Modelos de Dúvidas ---
class Duvida(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    titulo = db.Column(db.String(200), nullable=False, index=True)
    descricao = db.Column(db.Text, nullable=False)
    categoria = db.Column(db.String(100), nullable=False, index=True)
    status = db.Column(db.String(20), default='Aberta', nullable=False, index=True) # Status: Aberta, Respondida
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    author_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    discord_message_id = db.Column(db.String(50), nullable=True) # ID da msg principal no Discord
    discord_thread_id = db.Column(db.String(50), nullable=True) # ID do tópico no Discord

    author = db.relationship('User', backref='duvidas') # Backref adiciona user.duvidas
    respostas = db.relationship('Resposta', backref='duvida', lazy='dynamic', cascade="all, delete-orphan") # lazy='dynamic' para queries

    def __repr__(self):
        return f'<Duvida {self.id}: {self.titulo}>'

class Resposta(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    conteudo = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    # Guarda o ID Discord do autor da resposta, não um FK para User local
    author_discord_id = db.Column(db.String(50), nullable=True)
    duvida_id = db.Column(db.Integer, db.ForeignKey('duvida.id'), nullable=False)

    def __repr__(self):
        return f'<Resposta {self.id} para Dúvida {self.duvida_id}>'
# --- Fim Modelos de Dúvidas ---

# ------------------- 3. FORMULÁRIOS (Flask-WTF) -------------------
class RegistrationForm(FlaskForm):
    name = StringField('Nome Completo', validators=[DataRequired(), Length(min=2, max=150)])
    username = StringField('Nome de Usuário (Login)', validators=[DataRequired(), Length(min=4, max=80)])
    email = StringField('Email', validators=[DataRequired(), Email()])
    discord_id = StringField('ID do Discord', validators=[Optional(), Length(min=17, max=20)])
    password = PasswordField('Senha', validators=[DataRequired(), Length(min=6)])
    confirm_password = PasswordField('Confirmar Senha', validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField('Criar Conta')
    def validate_username(self, username):
        if User.query.filter_by(username=username.data).first(): raise ValidationError('Este nome de usuário já existe.')
    def validate_email(self, email):
        if User.query.filter_by(email=email.data).first(): raise ValidationError('Este email já está cadastrado.')
    def validate_discord_id(self, discord_id):
        if discord_id.data and User.query.filter_by(discord_id=discord_id.data).first(): raise ValidationError('Este ID do Discord já está cadastrado.')

class LoginForm(FlaskForm):
    username = StringField('Nome de Usuário', validators=[DataRequired()])
    password = PasswordField('Senha', validators=[DataRequired()])
    submit = SubmitField('Entrar')

class CardForm(FlaskForm):
    base = StringField('Base', validators=[Optional(), Length(max=50)])
    title = TextAreaField('Texto Principal', validators=[DataRequired(), Length(max=200)])
    content = TextAreaField('Descrição Adicional', validators=[Optional()])
    link = StringField('Link', validators=[Optional(), Length(max=300)])
    status = SelectField('Status', choices=[('pendente', 'Pendente'), ('urgente', 'Urgente'), ('resolvido', 'Resolvido')], validators=[DataRequired()])
    submit = SubmitField('Salvar Ticket')

class ProfileForm(FlaskForm):
    name = StringField('Nome Completo', validators=[DataRequired(), Length(min=2, max=150)])
    username = StringField('Nome de Usuário (Login)', validators=[DataRequired(), Length(min=4, max=80)]) # <-- Verifique se está aqui
    email = StringField('Email', validators=[DataRequired(), Email()])
    discord_id = StringField('ID do Discord', validators=[Optional(), Length(min=17, max=20)])
    password = PasswordField('Nova Senha', validators=[Optional(), Length(min=6)])
    confirm_password = PasswordField('Confirmar Nova Senha', validators=[EqualTo('password')])
    submit = SubmitField('Salvar Alterações')
    
    # Validador para username
    def validate_username(self, username): # <-- Verifique se está aqui
        if username.data != current_user.username and User.query.filter_by(username=username.data).first(): 
            raise ValidationError('Este nome de usuário já está em uso.')
    
    # Validadores existentes
    def validate_email(self, email):
        if email.data != current_user.email and User.query.filter_by(email=email.data).first(): 
            raise ValidationError('Este email já está cadastrado.')
    def validate_discord_id(self, discord_id):
        if discord_id.data and discord_id.data != current_user.discord_id and User.query.filter_by(discord_id=discord_id.data).first(): 
            raise ValidationError('Este ID do Discord já está cadastrado.')
        
class EventExportForm(FlaskForm):
    start_date = DateField('Data de Início', format='%Y-%m-%d', validators=[DataRequired(message="Data inicial é obrigatória.")])
    end_date = DateField('Data Final', format='%Y-%m-%d', validators=[DataRequired(message="Data final é obrigatória.")])
    submit = SubmitField('Exportar para Excel')

class LogTimeForm(FlaskForm):
    user_id = SelectField('Usuário', coerce=int, validators=[DataRequired()])
    time_str = StringField('Tempo de Atendimento (MM:SS)', validators=[DataRequired()])
    manager_password = PasswordField('Senha do Gestor', validators=[DataRequired()])
    submit = SubmitField('Lançar Tempo')

class QueryRequestForm(FlaskForm):
    description = TextAreaField('Descrição da Query', validators=[DataRequired(), Length(min=10)])
    submit = SubmitField('Solicitar Query')

class QueryAnswerForm(FlaskForm):
    sql_query = TextAreaField('Código SQL da Query', validators=[DataRequired(), Length(min=5)])
    submit = SubmitField('Responder')

class GuiaForm(FlaskForm):
    titulo = StringField('Descrição / Título', validators=[DataRequired(), Length(max=200)])
    conteudo = TextAreaField('Passo a Passo', validators=[DataRequired()])
    submit = SubmitField('Salvar Guia')

class ComportamentoForm(FlaskForm):
    titulo = StringField('Descrição / Título', validators=[DataRequired(), Length(max=200)])
    categoria = SelectField('Categoria', choices=CATEGORIAS_COMPORTAMENTO, validators=[DataRequired()])
    conteudo = TextAreaField('Passo a Passo (Comportamento)', validators=[DataRequired()])
    submit = SubmitField('Salvar Comportamento')

class QuickLinkForm(FlaskForm):
    title = StringField('Título do Link', validators=[DataRequired(), Length(max=100)])
    url = StringField('URL Completa', validators=[DataRequired(), Length(max=500)])
    submit = SubmitField('Salvar Link')

class EditTimeForm(FlaskForm):
    date_recorded = DateField('Nova Data', format='%Y-%m-%d', validators=[DataRequired()])
    time_str = StringField('Novo Tempo (MM:SS)', validators=[DataRequired()])
    submit = SubmitField('Salvar Alterações')

# --- Formulário de Dúvidas ---
class DuvidaForm(FlaskForm):
    titulo = StringField('Título da Dúvida*', validators=[DataRequired(), Length(min=10, max=200)])
    # Reutiliza as categorias definidas globalmente
    categoria = SelectField('Categoria*', choices=CATEGORIAS_COMPORTAMENTO, validators=[DataRequired()])
    descricao = TextAreaField('Descreva sua dúvida detalhadamente*', validators=[DataRequired(), Length(min=20)])
    submit = SubmitField('Enviar Dúvida e Criar Tópico')
# --- Fim Formulário de Dúvidas ---

# ------------------- 4. ROTAS / VIEWS (As Páginas) -------------------
@app.route('/')
@login_required
def index():
    return redirect(url_for('kanban_individual'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated: return redirect(url_for('index'))
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
    if current_user.is_authenticated: return redirect(url_for('index'))
    form = RegistrationForm()
    if form.validate_on_submit():
        user = User(name=form.name.data, username=form.username.data, email=form.email.data, discord_id=form.discord_id.data or None)
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

@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    form = ProfileForm()
    
    if form.validate_on_submit():
        current_user.name = form.name.data
        current_user.username = form.username.data # <-- Garanta que esta linha esteja aqui
        current_user.email = form.email.data
        current_user.discord_id = form.discord_id.data or None
        
        password_changed = False 
        if form.password.data:
            # A validação EqualTo já deve garantir isso, mas verificamos de novo
            if form.password.data == form.confirm_password.data:
                current_user.set_password(form.password.data)
                password_changed = True
            else:
                 # Se chegou aqui, algo está errado com EqualTo, mas damos feedback
                 flash('As senhas digitadas não coincidem.', 'danger')
                 # Não continua para o commit
                 return render_template('profile.html', title='Editar Perfil', form=form)

        try:
            db.session.commit() # Salva todas as alterações (nome, username, email, discord_id, senha)
            if password_changed:
                flash('Sua senha foi alterada com sucesso!', 'success')
            flash('Seu perfil foi atualizado com sucesso!', 'success')
            return redirect(url_for('profile')) 
        except Exception as e:
            db.session.rollback() 
            flash(f'Erro ao salvar no banco de dados: {e}', 'danger')

    # Se a validação POST falhou, mostra os erros
    elif request.method == 'POST': 
        for field, errors in form.errors.items():
            for error in errors:
                field_label = getattr(getattr(form, field, None), 'label', None)
                field_name = field_label.text if field_label else field.capitalize()
                flash(f"Erro no campo '{field_name}': {error}", 'danger')

    # Lógica GET: Pré-preenche o formulário
    if request.method == 'GET':
        form.name.data = current_user.name
        form.username.data = current_user.username # <-- Esta linha pré-preenche
        form.email.data = current_user.email
        form.discord_id.data = current_user.discord_id
        
    # Renderiza o template (para GET ou falha no POST)
    return render_template('profile.html', title='Editar Perfil', form=form) # Não precisa passar current_user aqui, Flask-Login já faz

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

@app.route('/card/new/<int:column_id>/<board_type>', methods=['POST'])
@login_required
def add_card(column_id, board_type):
    form = CardForm()
    if form.validate_on_submit():
        owner = current_user.id if board_type == 'individual' else None
        new_card = Card(base=form.base.data, title=form.title.data, content=form.content.data, link=form.link.data, status=form.status.data, column_id=column_id, owner_id=owner)
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
        return jsonify({'id': card.id, 'base': card.base, 'title': card.title, 'content': card.content, 'link': card.link, 'status': card.status})
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
    return render_template('fila_telefonica.html', title="Fila Telefônica", queue_members=queue_members, current_attendant_id=current_attendant_id, queue_user_ids=queue_user_ids)

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
    frases_divertidas = ["Atenção, marujo! O próximo navio (ligação) é seu!", "Acorda pra vida e reinicia o Zoiper, o próximo telefone é seu!", "Alôôôu! Já verifica o Zoiper, pois o próximo é seu.", "Sua hora chegou! Prepare-se, a próxima ligação é sua.", "Foguete não tem ré! A próxima chamada está na sua mira."]
    mensagem_sorteada = random.choice(frases_divertidas)
    if next_member.user.discord_id:
        try:
            payload = {'discord_id': next_member.user.discord_id, 'message': f"Olá {next_member.user.name}, {mensagem_sorteada}"}
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
                user_to_update.discord_id = request.form.get('discord_id_details') or None
                lunch_start_str = request.form.get('lunch_start_details')
                lunch_end_str = request.form.get('lunch_end_details')
                user_to_update.lunch_start = datetime.strptime(lunch_start_str, '%H:%M').time() if lunch_start_str else None
                user_to_update.lunch_end = datetime.strptime(lunch_end_str, '%H:%M').time() if lunch_end_str else None
        PhoneQueueMember.query.delete()
        user_ids_in_order = request.form.get('queue_order', '').split(',')
        if user_ids_in_order and user_ids_in_order[0]:
            for i, user_id_str in enumerate(user_ids_in_order):
                if user_id_str.isdigit():
                    db.session.add(PhoneQueueMember(user_id=int(user_id_str), position=i))
            state = PhoneQueueState.query.filter_by(key='current_user_id').first()
            if not state:
                db.session.add(PhoneQueueState(key='current_user_id', value=user_ids_in_order[0]))
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
    return render_template('configurar_fila.html', title="Configurar Fila", all_users=all_users, queue_members=queue_members, queue_user_ids=queue_user_ids)

# Adicione esta nova rota em qualquer lugar no seu app.py

@app.route('/fila/notificar-atual', methods=['POST'])
@login_required
def notificar_atendente_atual():
    """
    Envia uma notificação para o usuário que está atualmente na vez na fila,
    sem avançar a fila.
    """
    # 1. Encontra o ID do usuário atual
    current_attendant_id = None
    state = PhoneQueueState.query.filter_by(key='current_user_id').first()
    
    if state and state.value.isdigit():
        current_attendant_id = int(state.value)
    else:
        # Se não houver estado salvo, pega o primeiro da fila configurada
        first_in_queue = PhoneQueueMember.query.order_by(PhoneQueueMember.position).first()
        if first_in_queue:
            current_attendant_id = first_in_queue.user_id

    # 2. Se encontrou um usuário, busca os dados dele
    if current_attendant_id:
        atendente_atual = User.query.get(current_attendant_id)
        
        if atendente_atual and atendente_atual.discord_id:
            try:
                # 3. Monta e envia a notificação via bot
                mensagem = "Lembrete: Você é o(a) próximo(a) na fila de atendimento telefônico! 📞"
                payload = {'discord_id': atendente_atual.discord_id, 'message': mensagem}
                
                # Usa a mesma URL do bot da fila telefônica
                requests.post(DISCORD_BOT_URL, json=payload, timeout=3)
                
                flash(f"Notificação de lembrete enviada para {atendente_atual.name} no Discord!", "success")
            except requests.exceptions.RequestException:
                flash("Não foi possível notificar no Discord. O bot da fila está online?", "danger")
        elif atendente_atual:
            flash(f"O atendente da vez ({atendente_atual.name}) não possui ID do Discord cadastrado.", "warning")
        else:
            flash("Não foi possível encontrar o atendente da vez no banco de dados.", "danger")
    else:
        flash("A fila telefônica parece estar vazia. Nenhuma notificação foi enviada.", "info")

    # 4. Redireciona de volta para a página de configuração
    return redirect(url_for('configurar_fila'))

@app.route('/get_user_details/<int:user_id>')
@login_required
def get_user_details(user_id):
    user = User.query.get_or_404(user_id)
    return jsonify({'id': user.id, 'discord_id': user.discord_id or '', 'lunch_start': user.lunch_start.strftime('%H:%M') if user.lunch_start else '', 'lunch_end': user.lunch_end.strftime('%H:%M') if user.lunch_end else ''})

# --- ROTAS DE TICKETS ---
@app.route('/tickets-freshdesk')
@login_required
def tickets_freshdesk():
    # Pega o termo de busca da URL, se existir
    search_term = request.args.get('search', '')
    
    # Inicia a query base
    tickets_query = DiscordTicket.query.filter_by(status='aberto')
    
    # Se houver um termo de busca, adiciona o filtro na descrição
    if search_term:
        tickets_query = tickets_query.filter(DiscordTicket.description.ilike(f'%{search_term}%'))
        
    # Executa a query final
    tickets = tickets_query.order_by(DiscordTicket.created_at.desc()).all()
    
    return render_template('tickets_freshdesk.html', 
                           title="Tickets Abertos", 
                           tickets=tickets, 
                           search_term=search_term) # Passa o termo de volta para o template

@app.route('/tickets-retornar')
@login_required
def tickets_retornar():
    follow_ups = TicketFollowUp.query.filter_by(user_id=current_user.id).order_by(TicketFollowUp.id.desc()).all()
    abertos = [f for f in follow_ups if f.ticket.status == 'aberto']
    resolvidos = [f for f in follow_ups if f.ticket.status == 'resolvido']
    return render_template('tickets_retornar.html', title="Tickets para Retornar", abertos=abertos, resolvidos=resolvidos)

@app.route('/api/new_discord_ticket', methods=['POST'])
def api_new_discord_ticket():
    data = request.json
    if not data.get('description') or not data.get('link'):
        return jsonify({'status': 'error', 'message': 'Descrição e link são obrigatórios'}), 400
    new_ticket = DiscordTicket(description=data['description'], link=data['link'])
    db.session.add(new_ticket)
    db.session.commit()
    return jsonify({'status': 'success', 'message': 'Ticket criado com sucesso'}), 201

@app.route('/ticket/resolver/<int:ticket_id>', methods=['POST'])
@login_required
def resolver_ticket(ticket_id):
    ticket = DiscordTicket.query.get_or_404(ticket_id)
    ticket.status = 'resolvido'
    for followup in ticket.follow_ups:
        user_que_acompanha = followup.user
        if user_que_acompanha and user_que_acompanha.discord_id:
            payload = {'discord_user_id': user_que_acompanha.discord_id, 'ticket_description': ticket.description, 'ticket_link': followup.return_link}
            try:
                requests.post(BOT_RESOLVED_NOTIFICATION_URL, json=payload, timeout=5)
                flash(f"Notificação de resolução enviada para {user_que_acompanha.name} no Discord.", "info")
            except requests.RequestException as e:
                flash(f"Não foi possível notificar {user_que_acompanha.name} no Discord. O bot está online?", "warning")
                print(f"Erro ao notificar o bot: {e}")
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
    new_follow_up = TicketFollowUp(return_link=retorno_link, ticket_id=ticket_id, user_id=current_user.id)
    db.session.add(new_follow_up)
    db.session.commit()
    flash(f"Você agora está acompanhando o ticket #{ticket_id} com um novo retorno.", "success")
    return redirect(url_for('tickets_freshdesk'))

@app.route('/followup/mark-seen/<int:followup_id>', methods=['POST'])
@login_required
def mark_followup_seen(followup_id):
    follow_up = TicketFollowUp.query.get_or_404(followup_id)
    if follow_up.user_id == current_user.id:
        db.session.commit()
    return redirect(url_for('tickets_retornar'))

@app.route('/acompanhamento/remover/<int:followup_id>', methods=['POST'])
@login_required
def remover_acompanhamento(followup_id):
    # 1. Encontra o acompanhamento no banco de dados
    follow_up = TicketFollowUp.query.get_or_404(followup_id)

    # 2. Garante que o usuário só pode remover seus próprios acompanhamentos
    if follow_up.user_id != current_user.id:
        flash('Você não tem permissão para remover este acompanhamento.', 'danger')
        return redirect(url_for('tickets_retornar'))
    
    # 3. Deleta o registro e salva a alteração
    db.session.delete(follow_up)
    db.session.commit()
    
    flash('Acompanhamento removido com sucesso!', 'success')
    
    # 4. Redireciona de volta para a mesma página
    return redirect(url_for('tickets_retornar'))

# --- NOVA ROTA DE EXPORTAÇÃO ---
@app.route('/export/tickets')
@login_required
def export_tickets():
    # Garanta que estes imports estão no topo do seu app.py
    # import pandas as pd
    # import io
    # from flask import send_file

    # Pega o termo de busca da URL para garantir que a exportação corresponda ao filtro
    search_term = request.args.get('search', '')
    
    # --- 1. ALTERAÇÃO PRINCIPAL ---
    # Removemos o filtro 'filter_by(status='aberto')' para pegar TODOS os tickets
    tickets_query = DiscordTicket.query
    
    # O filtro por descrição continua funcionando normalmente
    if search_term:
        tickets_query = tickets_query.filter(DiscordTicket.description.ilike(f'%{search_term}%'))
        
    tickets = tickets_query.order_by(DiscordTicket.created_at.desc()).all()

    # Prepara os dados para a planilha
    data_for_export = {
        "ID": [t.id for t in tickets],
        # --- 2. NOVA COLUNA "STATUS" ADICIONADA ---
        "Status": [t.status.capitalize() for t in tickets], # Deixa a primeira letra maiúscula (ex: Aberto)
        "Descrição": [t.description for t in tickets],
        # --- 3. COLUNA "SOLICITANTE" REMOVIDA ---
        "Link Original": [t.link for t in tickets],
        "Data de Abertura": [t.created_at.strftime('%d/%m/%Y %H:%M') for t in tickets]
    }
    df = pd.DataFrame(data_for_export)

    # Cria o arquivo Excel em memória
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Todos_os_Tickets')
        
        # Bônus: Auto-ajusta a largura das colunas para melhor visualização
        worksheet = writer.sheets['Todos_os_Tickets']
        for column in worksheet.columns:
            max_length = 0
            column_letter = column[0].column_letter
            # Calcula o tamanho máximo do conteúdo na coluna
            for cell in column:
                try:
                    if len(str(cell.value)) > max_length:
                        max_length = len(str(cell.value))
                except:
                    pass
            # Adiciona um pouco de espaço extra
            adjusted_width = (max_length + 2)
            worksheet.column_dimensions[column_letter].width = adjusted_width

    output.seek(0)

    # Envia o arquivo para download com um novo nome
    return send_file(
        output,
        as_attachment=True,
        download_name='relatorio_completo_tickets.xlsx',
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )

# --- ROTAS DE QUERIES ---
# --- ROTAS DE QUERIES (ATUALIZADAS) ---

@app.route('/queries', methods=['GET', 'POST'])
@login_required
def list_queries():
    request_form = QueryRequestForm()
    answer_form = QueryAnswerForm()

    # --- Lógica de POST (quando uma nova query é solicitada) ---
    if request_form.validate_on_submit():
        new_query_request = QueryRequest(description=request_form.description.data, requester_id=current_user.id)
        db.session.add(new_query_request)
        db.session.commit()
        flash('Sua solicitação de query foi enviada!', 'success')

        # Lógica de notificação para o bot de queries
        try:
            payload = {
                'description': new_query_request.description,
                'requester_name': current_user.name
            }
            requests.post(f"{QUERY_BOT_URL}/notify_new_query", json=payload, timeout=3)
        except requests.exceptions.RequestException:
            flash('Não foi possível notificar no Discord. O bot de queries está online?', 'warning')

        return redirect(url_for('list_queries'))
    
    # --- Lógica de GET (quando a página é carregada e filtrada) ---
    search_term = request.args.get('search', '')
    show_mine = request.args.get('show_mine') # << NOVO: Pega o parâmetro do checkbox

    pending_queries_query = QueryRequest.query.filter_by(status='Pendente')
    answered_queries_query = QueryRequest.query.filter_by(status='Respondida')

    # Aplica filtro por texto, se existir
    if search_term:
        pending_queries_query = pending_queries_query.filter(QueryRequest.description.ilike(f'%{search_term}%'))
        answered_queries_query = answered_queries_query.filter(QueryRequest.description.ilike(f'%{search_term}%'))

    # << NOVO: Aplica filtro "Somente minhas", se o checkbox estiver marcado
    if show_mine:
        pending_queries_query = pending_queries_query.filter(QueryRequest.requester_id == current_user.id)
        answered_queries_query = answered_queries_query.filter(QueryRequest.requester_id == current_user.id)

    # Executa as queries
    pending_queries = pending_queries_query.order_by(QueryRequest.created_at.desc()).all()
    answered_queries = answered_queries_query.order_by(QueryRequest.answered_at.desc()).all()

    return render_template('queries.html',
                           title="Solicitação de Queries",
                           request_form=request_form,
                           answer_form=answer_form,
                           pending_queries=pending_queries,
                           answered_queries=answered_queries,
                           search_term=search_term,
                           show_mine=show_mine) # << NOVO: Envia o estado do checkbox para o template

@app.route('/query/answer/<int:query_id>', methods=['POST'])
@login_required
def answer_query(query_id):
    query = QueryRequest.query.get_or_404(query_id)
    form = QueryAnswerForm()
    if form.validate_on_submit():
        query.sql_query = form.sql_query.data
        query.status = 'Respondida'
        query.responder_id = current_user.id
        query.answered_at = datetime.utcnow()
        db.session.commit()
        flash('Query respondida com sucesso!', 'success')

        # <<< INÍCIO DA ALTERAÇÃO >>>
        if query.requester.discord_id:
            try:
                payload = {
                    'requester_discord_id': query.requester.discord_id,
                    'responder_name': current_user.name,
                    'description': query.description
                }
                requests.post(f"{QUERY_BOT_URL}/notify_answered_query", json=payload, timeout=3)
            except requests.exceptions.RequestException:
                flash('Não foi possível notificar o solicitante no Discord. O bot de queries está online?', 'warning')
        else:
            flash('Solicitante não possui ID do Discord cadastrado para ser notificado.', 'info')
        # <<< FIM DA ALTERAÇÃO >>>

    else:
        flash('Ocorreu um erro ao enviar sua resposta.', 'danger')
    return redirect(url_for('list_queries'))

# --- ROTAS DE METAS E TEMPO ---
@app.route('/minhas-metas', methods=['GET'])
@login_required
def minhas_metas():
    now = datetime.utcnow()
    search_date_str = request.args.get('search_date')
    query = ServiceTime.query.filter(ServiceTime.user_id == current_user.id, extract('year', ServiceTime.date_recorded) == now.year, extract('month', ServiceTime.date_recorded) == now.month)
    if search_date_str:
        try:
            selected_date = datetime.strptime(search_date_str, '%Y-%m-%d')
            query = query.filter(db.func.date(ServiceTime.date_recorded) == selected_date.date())
        except ValueError:
            flash("Formato de data inválido.", "warning")
    my_records = query.order_by(ServiceTime.date_recorded.desc()).all()
    all_my_monthly_records = ServiceTime.query.filter(ServiceTime.user_id == current_user.id, extract('year', ServiceTime.date_recorded) == now.year, extract('month', ServiceTime.date_recorded) == now.month).all()
    my_average_time = calculate_average_time(all_my_monthly_records)
    return render_template('minhas_metas.html', title="Minhas Metas", my_average_time=my_average_time, my_records=my_records, all_my_monthly_records_count=len(all_my_monthly_records), search_date=search_date_str, now=now)



# Em app.py, substitua a função lancar_tempo inteira por esta:

@app.route('/lancar-tempo', methods=['GET', 'POST'])
@login_required
def lancar_tempo():
    form = LogTimeForm()
    edit_form = EditTimeForm()
    all_users = User.query.order_by('name').all()
    form.user_id.choices = [(u.id, u.name) for u in all_users]

    # Lógica para o formulário de lançamento INDIVIDUAL
    if form.validate_on_submit():
        if form.manager_password.data == 'Auvo123':
            try:
                minutes, seconds = map(int, form.time_str.data.split(':'))
                total_seconds = (minutes * 60) + seconds
                new_record = ServiceTime(time_in_seconds=total_seconds, user_id=form.user_id.data)
                db.session.add(new_record)
                db.session.commit()
                flash('Tempo registrado com sucesso!', 'success')
            except ValueError:
                flash('Formato de tempo inválido. Use MM:SS.', 'danger')
        else:
            flash('Senha de gestor incorreta.', 'danger')
        # Redireciona de volta, informando para manter a aba 'individual' ativa
        return redirect(url_for('lancar_tempo', active_tab='individual'))

    # Lógica de GET (busca)
    search_results = []
    search_user_id = request.args.get('search_user_id', type=int)
    
    # << NOVA LÓGICA: Lê qual aba deve estar ativa a partir da URL >>
    # Se nenhuma for especificada, o padrão é 'individual'
    active_tab = request.args.get('active_tab', 'individual')

    if search_user_id:
        search_results = ServiceTime.query.filter(ServiceTime.user_id == search_user_id).order_by(ServiceTime.date_recorded.desc()).all()
    
    return render_template('lancar_tempo.html',
                           title="Gerenciar Metas Diárias",
                           form=form,
                           edit_form=edit_form,
                           search_results=search_results,
                           search_user_id=search_user_id,
                           all_users=all_users,
                           active_tab=active_tab) # << Envia a aba ativa para o template

@app.route('/lancar-tempo/massa', methods=['POST'])
@login_required
def lancar_tempo_massa():
    # Pega os dados do formulário
    mass_data = request.form.get('mass_data')
    manager_password = request.form.get('manager_password_mass')
    record_date_str = request.form.get('record_date_mass') # << NOVO: Pega a data do formulário

    # Validações iniciais
    if manager_password != 'Auvo123':
        flash('Senha de gestor incorreta para o lançamento em massa.', 'danger')
        return redirect(url_for('lancar_tempo'))
    if not mass_data:
        flash('Nenhum dado foi inserido para o lançamento em massa.', 'warning')
        return redirect(url_for('lancar_tempo'))
    
    # << NOVO: Validação da data
    if not record_date_str:
        flash('A data do registro é obrigatória para o lançamento em massa.', 'danger')
        return redirect(url_for('lancar_tempo'))

    try:
        # Converte a string da data para um objeto datetime
        record_date_obj = datetime.strptime(record_date_str, '%Y-%m-%d')
    except ValueError:
        flash('Formato de data inválido.', 'danger')
        return redirect(url_for('lancar_tempo'))

    success_count = 0
    error_lines = []
    all_users_from_db = User.query.all()

    lines = mass_data.strip().split(';')
    for i, line in enumerate(lines):
        line = line.strip()
        if not line: continue

        try:
            full_name_str, time_str = line.split(':', 1)
            full_name_str = full_name_str.strip().lower()
            time_str = time_str.strip()

            found_user = None
            for user in all_users_from_db:
                if user.name.lower() in full_name_str:
                    found_user = user
                    break
            
            if found_user:
                minutes, seconds = map(int, time_str.split(':'))
                total_seconds = (minutes * 60) + seconds

                # << MUDANÇA CRUCIAL: Usa a data fornecida pelo gestor
                new_record = ServiceTime(
                    time_in_seconds=total_seconds,
                    user_id=found_user.id,
                    date_recorded=record_date_obj 
                )
                db.session.add(new_record)
                success_count += 1
            else:
                error_lines.append(f"Linha {i+1}: Nenhum usuário correspondente a '{full_name_str.title()}' foi encontrado.")
        except Exception as e:
            error_lines.append(f"Linha {i+1}: Formato inválido ('{line}'). Verifique o formato 'Nome: MM:SS'.")

    db.session.commit()

    if success_count > 0:
        flash(f'{success_count} registros de tempo para o dia {record_date_str} foram lançados com sucesso!', 'success')
    if error_lines:
        flash('Alguns registros não puderam ser lançados:', 'danger')
        for error in error_lines:
            flash(error, 'danger')

    return redirect(url_for('lancar_tempo'))

@app.route('/remover-tempo/<int:record_id>', methods=['POST'])
@login_required
def remover_tempo(record_id):
    record_to_delete = ServiceTime.query.get_or_404(record_id)
    manager_password = request.form.get('manager_password')
    search_user_id = record_to_delete.user_id # Guarda o ID para o redirect

    # 1. VERIFICA A SENHA DO GESTOR
    if manager_password != 'Auvo123':
        flash('Senha de gestor incorreta.', 'danger')
    else:
        # 2. Se a senha estiver correta, prossegue com a remoção
        db.session.delete(record_to_delete)
        db.session.commit()
        flash('Registro de tempo removido com sucesso!', 'success')

    # Redireciona de volta, mantendo o filtro de busca
    return redirect(url_for('lancar_tempo', search_user_id=search_user_id, active_tab='remover'))

# Em app.py, na seção de ROTAS

@app.route('/editar-tempo/<int:record_id>', methods=['POST'])
@login_required
def editar_tempo(record_id):
    record = ServiceTime.query.get_or_404(record_id)
    # Pega a senha enviada pelo formulário do modal
    manager_password = request.form.get('manager_password')

    # 1. VERIFICA A SENHA DO GESTOR
    if manager_password != 'Auvo123':
        flash('Senha de gestor incorreta.', 'danger')
    else:
        # 2. Se a senha estiver correta, prossegue com a edição
        form = EditTimeForm()
        if form.validate_on_submit():
            try:
                minutes, seconds = map(int, form.time_str.data.split(':'))
                total_seconds = (minutes * 60) + seconds
                record.date_recorded = form.date_recorded.data
                record.time_in_seconds = total_seconds
                db.session.commit()
                flash('Registro de tempo atualizado com sucesso!', 'success')
            except ValueError:
                flash('Formato de tempo inválido. Use MM:SS.', 'danger')
        else:
            flash('Erro na validação do formulário de edição.', 'danger')

    # Redireciona de volta para a página, mantendo o filtro de busca
    return redirect(url_for('lancar_tempo', search_user_id=record.user_id, active_tab='editar'))


# --- ROTAS DE GUIAS ---
@app.route('/guias', methods=['GET', 'POST'])
@login_required
def listar_guias():
    form = GuiaForm()
    if form.validate_on_submit():
        novo_guia = Guia(titulo=form.titulo.data, conteudo=form.conteudo.data, author_id=current_user.id)
        db.session.add(novo_guia)
        db.session.commit()
        flash('Guia criado com sucesso!', 'success')

        # --- INÍCIO DA NOTIFICAÇÃO ---
        try:
            mensagem = (
                f"**Novo Guia Criado!** :scroll:\n"
                f"**Título:** {novo_guia.titulo}\n"
                f"**Criado por:** {current_user.name}"
            )
            payload = {'message': mensagem}
            requests.post(GENERAL_NOTIFICATION_BOT_URL, json=payload, timeout=3)
        except requests.exceptions.RequestException:
            flash('Não foi possível notificar no Discord. O bot de notificações está online?', 'warning')
        # --- FIM DA NOTIFICAÇÃO ---
            
        return redirect(url_for('listar_guias'))
    
    query = request.args.get('q', '')
    if query:
        guias = Guia.query.filter(Guia.titulo.ilike(f'%{query}%')).order_by(Guia.created_at.desc()).all()
    else:
        guias = Guia.query.order_by(Guia.created_at.desc()).all()
    return render_template('guias.html', title="Guias", guias=guias, query=query, form=form)

@app.route('/guias/deletar/<int:guia_id>', methods=['POST'])
@login_required
def deletar_guia(guia_id):
    guia = Guia.query.get_or_404(guia_id)
    db.session.delete(guia)
    db.session.commit()
    flash('Guia removido com sucesso!', 'success')
    return redirect(url_for('listar_guias'))


# --- CONFIGURAÇÃO ADICIONAL PARA UPLOAD ---
# Pasta onde as imagens dos guias serão salvas
UPLOAD_FOLDER_GUIAS = os.path.join(app.static_folder, 'uploads', 'guias')
# Extensões permitidas
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

# Garante que a pasta de upload exista
os.makedirs(UPLOAD_FOLDER_GUIAS, exist_ok=True) 

def allowed_file(filename):
    """Verifica se a extensão do arquivo é permitida."""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS
# --- ROTA PARA EDITAR UM GUIA ---
@app.route('/guias/editar/<int:guia_id>', methods=['GET', 'POST'])
@login_required
def editar_guia(guia_id):
    guia = Guia.query.get_or_404(guia_id)
    # Opcional: Verificar se o usuário atual é o autor (se necessário)
    # if guia.author_id != current_user.id:
    #     flash('Você não tem permissão para editar este guia.', 'danger')
    #     return redirect(url_for('listar_guias'))

    form = GuiaForm() # Reutilizamos o mesmo formulário

    if form.validate_on_submit(): # Se o formulário foi enviado (POST) e é válido
        guia.titulo = form.titulo.data
        guia.conteudo = form.conteudo.data
        try:
            db.session.commit() # Salva as alterações no banco
            flash('Guia atualizado com sucesso!', 'success')
            return redirect(url_for('listar_guias')) # Volta para a lista
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao atualizar o guia: {e}', 'danger')

    elif request.method == 'GET': # Se a página está sendo carregada pela primeira vez
        # Preenche o formulário com os dados atuais do guia
        form.titulo.data = guia.titulo
        form.conteudo.data = guia.conteudo

    # Renderiza o template de edição (para GET ou se a validação POST falhar)
    return render_template('editar_guia.html', title="Editar Guia", form=form, guia=guia)

# --- FIM DA ROTA DE EDIÇÃO ---


# --- NOVA ROTA PARA UPLOAD DE IMAGEM DO GUIA ---
@app.route('/upload/guia-imagem', methods=['POST'])
@login_required 
def upload_guia_imagem():
    if 'file' not in request.files:
        return jsonify({'error': 'Nenhum arquivo enviado'}), 400
    
    file = request.files['file']
    
    if file.filename == '':
        return jsonify({'error': 'Nenhum arquivo selecionado'}), 400
        
    if file and allowed_file(file.filename):
        filename_secure = secure_filename(file.filename)
        ext = filename_secure.rsplit('.', 1)[1].lower()
        unique_filename = f"{uuid.uuid4()}.{ext}"
        
        save_path = os.path.join(UPLOAD_FOLDER_GUIAS, unique_filename)
        
        try:
            file.save(save_path)
            
            # --- CORREÇÃO APLICADA AQUI ---
            # Construir o caminho relativo para url_for usando barras normais '/'
            relative_path_for_url = f"uploads/guias/{unique_filename}" 
            file_url = url_for('static', filename=relative_path_for_url) 
            # --- FIM DA CORREÇÃO ---

            print(f"Imagem salva: {save_path}, URL: {file_url}") # Log para debug
            return jsonify({'imageUrl': file_url}), 200
        except Exception as e:
            print(f"Erro ao salvar imagem: {e}") # Log para debug
            return jsonify({'error': f'Erro ao salvar arquivo: {e}'}), 500
            
    else:
        return jsonify({'error': 'Tipo de arquivo não permitido'}), 400

# --- FIM DA NOVA ROTA ---

@app.template_filter('render_markdown') # Nome do filtro que usaremos no HTML
def render_markdown(text):
    """Renders Markdown text to HTML."""
    if text: # Verifica se o texto não é None ou vazio
         # Converte Markdown para HTML e marca como seguro para o Jinja
        return Markup(markdown.markdown(text, extensions=['fenced_code', 'tables'])) 
    return '' # Retorna string vazia se o input for None/vazio
# --- ROTAS DE COMPORTAMENTOS ---
@app.route('/comportamentos', methods=['GET', 'POST'])
@login_required
def listar_comportamentos():
    form = ComportamentoForm()
    
    # Processamento do Formulário POST (Adicionar Novo Comportamento)
    if form.validate_on_submit():
        novo_comportamento = Comportamento(
            titulo=form.titulo.data, 
            conteudo=form.conteudo.data, 
            categoria=form.categoria.data, 
            author_id=current_user.id
        )
        db.session.add(novo_comportamento)
        db.session.commit()
        flash('Comportamento salvo com sucesso!', 'success')

        # --- INÍCIO DA NOTIFICAÇÃO ---
        try:
            mensagem = (
                f"**Novo Comportamento Registrado!** :clipboard:\n"
                f"**Título:** {novo_comportamento.titulo}\n"
                f"**Categoria:** {novo_comportamento.categoria}\n"
                f"**Registrado por:** {current_user.name}"
            )
            payload = {'message': mensagem}
            requests.post(GENERAL_NOTIFICATION_BOT_URL, json=payload, timeout=3)
        except requests.exceptions.RequestException:
            flash('Não foi possível notificar no Discord. O bot de notificações está online?', 'warning')
        # --- FIM DA NOTIFICAÇÃO ---

        return redirect(url_for('listar_comportamentos'))
    
    # Processamento da Busca/Filtro (Requisição GET)
    # UNIFICANDO OS NOMES DAS VARIÁVEIS PARA 'q' E 'categoria'
    q = request.args.get('q', '')
    current_category = request.args.get('categoria', '') 
    
    query = Comportamento.query
    
    # Aplica filtro por título
    if q:
        query = query.filter(Comportamento.titulo.ilike(f'%{q}%'))
    
    # Aplica filtro por categoria
    if current_category:
        query = query.filter(Comportamento.categoria == current_category)
        
    comportamentos = query.order_by(Comportamento.created_at.desc()).all()
    
    # Pega a lista de categorias do formulário para o dropdown
    categorias_choices = form.categoria.choices
        
    return render_template(
        'comportamentos.html', 
        title="Comportamentos do Sistema", 
        comportamentos=comportamentos, 
        form=form, 
        categorias=categorias_choices, 
        # Enviando as variáveis com os nomes corretos para o HTML
        q=q, 
        current_category=current_category
    )

@app.route('/comportamentos/editar/<int:comportamento_id>', methods=['GET', 'POST'])
@login_required
def editar_comportamento(comportamento_id):
    comportamento = Comportamento.query.get_or_404(comportamento_id)
    form = ComportamentoForm(obj=comportamento)
    if form.validate_on_submit():
        comportamento.titulo = form.titulo.data
        comportamento.conteudo = form.conteudo.data
        comportamento.categoria = form.categoria.data
        db.session.commit()
        flash('Comportamento atualizado com sucesso!', 'success')
        return redirect(url_for('listar_comportamentos'))
    return render_template('editar_comportamento.html', title="Editar Comportamento", form=form)

@app.route('/comportamentos/deletar/<int:comportamento_id>', methods=['POST'])
@login_required
def deletar_comportamento(comportamento_id):
    comportamento = Comportamento.query.get_or_404(comportamento_id)
    db.session.delete(comportamento)
    db.session.commit()
    flash('Comportamento removido com sucesso!', 'success')
    return redirect(url_for('listar_comportamentos'))

# --- ROTAS DE LINKS ÚTEIS ---
@app.route('/links', methods=['GET', 'POST'])
@login_required
def links_uteis():
    form = QuickLinkForm()
    if form.validate_on_submit():
        icon_url = get_favicon_url(form.url.data)
        novo_link = QuickLink(title=form.title.data, url=form.url.data, icon_url=icon_url)
        db.session.add(novo_link)
        db.session.commit()
        flash('Link rápido salvo com sucesso!', 'success')
        
        # --- INÍCIO DA NOTIFICAÇÃO ---
        try:
            mensagem = (
                f"**Novo Link Útil Adicionado!** :link:\n"
                f"**Título:** {novo_link.title}\n"
                f"**URL:** {novo_link.url}\n"
                f"**Adicionado por:** {current_user.name}"
            )
            payload = {'message': mensagem}
            requests.post(GENERAL_NOTIFICATION_BOT_URL, json=payload, timeout=3)
        except requests.exceptions.RequestException:
            flash('Não foi possível notificar no Discord. O bot de notificações está online?', 'warning')
        # --- FIM DA NOTIFICAÇÃO ---
            
        return redirect(url_for('links_uteis'))
    
    links = QuickLink.query.order_by(QuickLink.created_at.desc()).all()
    return render_template('links_uteis.html', title="Links Úteis", links=links, form=form)


# --- FUNÇÕES DE AJUDA PARA RESETAR SENHA ---

def generate_random_password(length=10):
    """Gera uma senha aleatória com letras e números."""
    characters = string.ascii_letters + string.digits
    return ''.join(random.choice(characters) for i in range(length))

def send_password_reset_email(user, new_password):
    """Envia o e-mail com a nova senha."""
    msg = Message('Sua Nova Senha do Sistema',
                  sender='seu-email@gmail.com',  # <-- SEU E-MAIL (o mesmo do MAIL_USERNAME)
                  recipients=[user.email])
    msg.body = f"""Olá {user.name},

Uma nova senha foi solicitada para sua conta.

Sua nova senha é: {new_password}

Recomendamos que você faça login e altere esta senha no seu perfil.

Atenciosamente,
Sistema de Gestão
"""
    try:
        mail.send(msg)
    except Exception as e:
        print(f"Erro ao enviar e-mail: {e}")
        flash('Não foi possível enviar o e-mail de redefinição. Contate o administrador.', 'danger')

# --- NOVA ROTA PARA SOLICITAR A SENHA ---

@app.route('/resetar_senha', methods=['GET', 'POST'])
def reset_request():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    form = RequestResetForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user:
            # 1. Gera uma nova senha
            new_password = generate_random_password()
            # 2. Salva a nova senha (hash) no banco
            user.set_password(new_password)
            db.session.commit()
            # 3. Envia a nova senha (texto puro) por e-mail
            send_password_reset_email(user, new_password)
            
            flash('Uma nova senha foi enviada para o seu e-mail. Verifique sua caixa de entrada.', 'success')
            return redirect(url_for('login'))
        else:
            # Não revele que o usuário não existe por segurança
            flash('Se o e-mail estiver correto, uma nova senha será enviada. Verifique sua caixa de entrada.', 'info')
            return redirect(url_for('login'))
            
    return render_template('reset_request.html', title='Resetar Senha', form=form)

@app.route('/links/deletar/<int:link_id>', methods=['POST'])
@login_required
def deletar_link(link_id):
    link = QuickLink.query.get_or_404(link_id)
    db.session.delete(link)
    db.session.commit()
    flash('Link removido com sucesso!', 'success')
    return redirect(url_for('links_uteis'))

# --- ROTAS DE LEMBRETES (ADICIONADO) ---
# --- ROTAS DE LEMBRETES ---
# Em app.py

# Em app.py, substitua TODAS as suas rotas de lembrete por estas:

@app.route('/reminders')
@login_required
def list_reminders():
    # Define a hora UTC atual
    now_utc = datetime.utcnow()
    
    # Define a hora local de Brasília (UTC-3)
    now_brasilia = datetime.utcnow() - timedelta(hours=3)

    # Busca lembretes que o usuário logado criou
    # Compara a hora do lembrete (que foi salva como local) com a hora local
    upcoming_reminders = Reminder.query.filter(
        Reminder.user_id == current_user.id,
        Reminder.reminder_datetime > now_brasilia 
    ).order_by(asc(Reminder.reminder_datetime)).all()

    past_reminders = Reminder.query.filter(
        Reminder.user_id == current_user.id,
        Reminder.reminder_datetime <= now_brasilia
    ).order_by(desc(Reminder.reminder_datetime)).all()

    return render_template(
        'reminders.html',
        title="Meus Lembretes",
        upcoming=upcoming_reminders,
        past=past_reminders
    )

@app.route('/reminders/new', methods=['GET', 'POST'])
@login_required
def create_reminder():
    if request.method == 'POST':
        reminder_type = request.form.get('reminder_type')
        description = request.form.get('description')
        link = request.form.get('link')
        reminder_datetime_str = request.form.get('reminder_datetime')

        if not reminder_type or not reminder_datetime_str:
            flash('Tipo e Data/Hora são obrigatórios.', 'danger')
            # Retorna o template em vez de redirect, para não perder dados do form
            return render_template('create_reminder.html', title="Agendar Novo Lembrete", form_data=request.form), 400

        try:
            reminder_datetime_obj = datetime.strptime(reminder_datetime_str, '%Y-%m-%dT%H:%M')
            
            # --- CORREÇÃO APLICADA AQUI ---
            # Compara a hora digitada com a hora atual de Brasília (UTC-3)
            now_brasilia = datetime.utcnow() - timedelta(hours=3)
            if reminder_datetime_obj <= now_brasilia:
                 flash('A data e hora do lembrete devem estar no futuro.', 'warning')
                 return render_template('create_reminder.html', title="Agendar Novo Lembrete", form_data=request.form), 400
            # --- FIM DA CORREÇÃO ---

        except ValueError:
            flash('Formato de data e hora inválido.', 'danger')
            return render_template('create_reminder.html', title="Agendar Novo Lembrete", form_data=request.form), 400

        # Cria a nova instância do lembrete
        new_rem = Reminder(
            user_id=current_user.id,
            reminder_type=reminder_type,
            description=description,
            link=link,
            reminder_datetime=reminder_datetime_obj, # Salva a hora local digitada
            is_sent=False,
            notification_status=None
        )
        db.session.add(new_rem)
        db.session.commit()

        flash('Lembrete agendado com sucesso!', 'success')
        return redirect(url_for('list_reminders'))

    # Se for GET, apenas mostra a página com o formulário
    return render_template('create_reminder.html', title="Agendar Novo Lembrete")

# --- ROTA NOVA PARA DUPLICAR (CORRIGIDA) ---
@app.route('/reminder/duplicate/<int:reminder_id>', methods=['POST'])
@login_required
def duplicate_reminder(reminder_id):
    """Duplica um lembrete existente com uma nova data/hora."""
    
    original_reminder = Reminder.query.get_or_404(reminder_id)

    if original_reminder.user_id != current_user.id:
        flash('Você não tem permissão para duplicar este lembrete.', 'danger')
        return redirect(url_for('list_reminders'))

    new_datetime_str = request.form.get('new_datetime')
    if not new_datetime_str:
        flash('Nova data e hora são obrigatórias para duplicar.', 'danger')
        return redirect(url_for('list_reminders'))

    try:
        new_datetime_obj = datetime.strptime(new_datetime_str, '%Y-%m-%dT%H:%M')
        
        # --- CORREÇÃO APLICADA AQUI ---
        # Compara a nova hora com a hora atual de Brasília (UTC-3)
        now_brasilia = datetime.utcnow() - timedelta(hours=3)
        if new_datetime_obj <= now_brasilia:
             flash('A data e hora do novo lembrete devem estar no futuro.', 'warning')
             return redirect(url_for('list_reminders'))
        # --- FIM DA CORREÇÃO ---

    except ValueError:
        flash('Formato de data e hora inválido.', 'danger')
        return redirect(url_for('list_reminders'))

    # 4. Cria o novo lembrete (cópia)
    new_rem = Reminder(
        user_id=current_user.id,
        reminder_type=original_reminder.reminder_type,
        description=original_reminder.description,
        link=original_reminder.link,
        reminder_datetime=new_datetime_obj, # Usa a nova data/hora
        is_sent=False,
        notification_status=None
    )

    try:
        db.session.add(new_rem)
        db.session.commit()
        flash('Lembrete duplicado e reagendado com sucesso!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao salvar o lembrete duplicado: {e}', 'danger')

    return redirect(url_for('list_reminders'))
# --- FIM DA NOVA ROTA ---


@app.route('/reminder/delete/<int:reminder_id>', methods=['POST'])
@login_required
def delete_reminder(reminder_id):
    """Rota para deletar um lembrete específico."""
    reminder_to_delete = Reminder.query.get_or_404(reminder_id)

    if reminder_to_delete.user_id != current_user.id:
        flash('Você não tem permissão para remover este lembrete.', 'danger')
        return redirect(url_for('list_reminders'))

    try:
        db.session.delete(reminder_to_delete)
        db.session.commit()
        flash('Lembrete removido com sucesso!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Ocorreu um erro ao remover o lembrete: {e}', 'danger')

    return redirect(url_for('list_reminders'))

@app.route('/duvidas', methods=['GET'])
@login_required
def listar_duvidas():
    """Lista as dúvidas abertas e respondidas, com busca."""
    search_term = request.args.get('search', '').strip()
    # Base queries ordenadas + Eager Loading do autor
    query_abertas = Duvida.query.options(joinedload(Duvida.author)).filter_by(status='Aberta').order_by(Duvida.created_at.desc())
    query_respondidas = Duvida.query.options(joinedload(Duvida.author)).filter_by(status='Respondida').order_by(Duvida.created_at.desc())
    if search_term:
        search_filter = (Duvida.titulo.ilike(f'%{search_term}%') | Duvida.descricao.ilike(f'%{search_term}%') | Duvida.categoria.ilike(f'%{search_term}%'))
        query_abertas = query_abertas.filter(search_filter)
        query_respondidas = query_respondidas.filter(search_filter)
    duvidas_abertas = query_abertas.all()
    duvidas_respondidas = query_respondidas.all()
    return render_template('duvidas.html', title="Consultar Dúvidas", duvidas_abertas=duvidas_abertas, duvidas_respondidas=duvidas_respondidas, search_term=search_term)

@app.route('/duvidas/nova', methods=['GET', 'POST'])
@login_required
def nova_duvida():
    """Exibe o formulário e processa a criação de uma nova dúvida, notificando o bot."""
    form = DuvidaForm()
    if form.validate_on_submit():
        nova_duvida_db = Duvida(titulo=form.titulo.data, categoria=form.categoria.data, descricao=form.descricao.data, author_id=current_user.id, status='Aberta')
        db.session.add(nova_duvida_db)
        try:
            db.session.commit()
            duvida_id_criada = nova_duvida_db.id
            payload = {'duvida_id': duvida_id_criada, 'titulo': form.titulo.data, 'categoria': form.categoria.data, 'descricao': form.descricao.data, 'author_name': current_user.name}
            try:
                print(f"[Flask->Bot] Enviando dados para {DUVIDAS_BOT_URL}: {payload}")
                response = requests.post(DUVIDAS_BOT_URL, json=payload, timeout=15)
                response.raise_for_status()
                try:
                    response_data = response.json()
                    thread_id = response_data.get('thread_id'); message_id = response_data.get('message_id')
                    if thread_id:
                        duvida_a_atualizar = db.session.get(Duvida, duvida_id_criada)
                        if duvida_a_atualizar:
                            duvida_a_atualizar.discord_thread_id = str(thread_id)
                            if message_id: duvida_a_atualizar.discord_message_id = str(message_id)
                            db.session.commit()
                            print(f"[Flask] IDs Discord salvos para dúvida {duvida_id_criada}")
                except Exception as e_resp: print(f"[Flask WARN] Bot OK, erro processar IDs: {e_resp}")
                flash('Dúvida enviada! Um tópico foi criado no Discord para acompanhamento.', 'success')
            except requests.exceptions.Timeout: print(f"[Flask ERRO] Timeout bot dúvidas: {DUVIDAS_BOT_URL}"); flash('Sua dúvida foi salva, mas o bot demorou muito para responder.', 'warning')
            except requests.exceptions.RequestException as e: status_code = e.response.status_code if e.response is not None else "Rede"; print(f"[Flask ERRO] Erro {status_code} bot ({DUVIDAS_BOT_URL}): {e}"); flash(f'Sua dúvida foi salva, mas houve erro ({status_code}) ao criar tópico. Avise admin.', 'warning')
            return redirect(url_for('listar_duvidas'))
        except Exception as e_db: db.session.rollback(); print(f"[Flask ERRO DB] Salvar dúvida: {e_db}"); flash('Erro interno ao salvar dúvida.', 'danger')
    return render_template('nova_duvida.html', title="Enviar Nova Dúvida", form=form)

@app.route('/duvidas/<int:duvida_id>', methods=['GET'])
@login_required
def ver_duvida(duvida_id):
    """Mostra os detalhes de uma dúvida e suas respostas associadas."""
    
    # Carrega a dúvida e seu autor
    duvida = Duvida.query.options(
        joinedload(Duvida.author) 
    ).get_or_404(duvida_id)
    
    # --- CORREÇÃO APLICADA AQUI ---
    # Busca e ordena as respostas AQUI, no backend
    respostas_ordenadas = duvida.respostas.order_by(Resposta.created_at.asc()).all()
    # --- FIM DA CORREÇÃO ---
    
    return render_template('ver_duvida.html', 
                           title=f"Dúvida #{duvida.id}", 
                           duvida=duvida,
                           respostas=respostas_ordenadas) # Passa a lista ordenada para o template

@app.route('/api/resposta_duvida', methods=['POST'])
def api_receber_resposta():
    """API para o bot do Discord enviar a resposta marcada como correta."""
    api_key = request.headers.get('X-Api-Key')
    if not api_key or api_key != API_SECRET_KEY: print(f"[API Resposta ERRO 403] Key inválida de {request.remote_addr}"); return jsonify({'status': 'error', 'message': 'Não autorizado'}), 403
    data = request.json
    if not data: print("[API Resposta ERRO 400] No JSON."); return jsonify({'status': 'error', 'message': 'JSON requerido'}), 400
    duvida_id = data.get('duvida_id'); conteudo_resposta = data.get('conteudo_resposta'); author_discord_id = data.get('author_discord_id')
    if not all([duvida_id, conteudo_resposta]): print(f"[API Resposta ERRO 400] Dados incompletos: {data}"); return jsonify({'status': 'error', 'message': 'duvida_id e conteudo_resposta obrigatórios'}), 400
    duvida = db.session.get(Duvida, duvida_id)
    if not duvida: print(f"[API Resposta ERRO 404] Dúvida {duvida_id} não encontrada."); return jsonify({'status': 'error', 'message': f'Dúvida {duvida_id} não encontrada'}), 404
    try:
        nova_resposta = Resposta(conteudo=conteudo_resposta, author_discord_id=str(author_discord_id) if author_discord_id else None, duvida_id=duvida_id)
        db.session.add(nova_resposta)
        duvida.status = 'Respondida'
        db.session.commit()
        print(f"[API Resposta OK] Resposta p/ dúvida {duvida_id} salva.")
        return jsonify({'status': 'success', 'message': 'Resposta salva'}), 201
    except Exception as e: db.session.rollback(); print(f"[API Resposta ERRO 500] Erro salvar resposta {duvida_id}: {e}"); return jsonify({'status': 'error', 'message': 'Erro interno ao salvar'}), 500
# --- FIM ROTAS DE DÚVIDAS ---
# --- ROTA PARA DELETAR UMA DÚVIDA ---
@app.route('/duvidas/deletar/<int:duvida_id>', methods=['POST'])
@login_required
def deletar_duvida(duvida_id):
    duvida = db.session.get(Duvida, duvida_id) # Usar db.session.get é mais eficiente
    
    if not duvida:
        flash("Dúvida não encontrada.", "danger")
        return redirect(url_for('listar_duvidas'))

    # Opcional: Adicionar verificação de permissão (ex: só o autor ou admin pode deletar)
    # if duvida.author_id != current_user.id:
    #     flash("Você não tem permissão para apagar esta dúvida.", "danger")
    #     return redirect(url_for('listar_duvidas'))

    try:
        # Nota: Isso deleta a dúvida do SEU sistema, mas não deleta o tópico no Discord.
        # O tópico no Discord permanecerá, mas as novas respostas não serão salvas.
        db.session.delete(duvida)
        db.session.commit()
        flash('Dúvida removida com sucesso!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f"Erro ao remover a dúvida: {e}", 'danger')
    
    return redirect(url_for('listar_duvidas'))
# --- FIM DA ROTA DE EXCLUSÃO ---

# --- ROTAS PARA REGISTRO DE EVENTOS ---

@app.route('/eventos', methods=['GET'])
@login_required
def listar_eventos():
    """Página principal de registro e visualização de eventos."""
    
    # 1. Buscar os tipos de evento para os botões de registro
    tipos_de_evento = EventType.query.order_by(EventType.name).all()
    
    # 2. Buscar os logs de eventos recentes (últimos 50)
    logs_recentes = EventLog.query.options(
        joinedload(EventLog.user), # Carrega o usuário junto
        joinedload(EventLog.event_type) # Carrega o tipo de evento junto
    ).order_by(EventLog.timestamp.desc()).limit(50).all()
    
    # 3. Preparar dados para o Dashboard (Contagem de HOJE em BRT)
    
    # Define o início e o fim de "hoje" em Brasília (UTC-3)
    now_utc = datetime.utcnow()
    hoje_brt = (now_utc - timedelta(hours=3)).date() # Data de hoje em BRT
    
    # Converte a data de hoje em BRT de volta para UTC para a query
    inicio_dia_utc = datetime(hoje_brt.year, hoje_brt.month, hoje_brt.day, 3, 0, 0) # 00:00 BRT = 03:00 UTC
    fim_dia_utc = inicio_dia_utc + timedelta(days=1)
    
    # Query que conta eventos de hoje
    contagem_hoje = db.session.query(
        EventType.name, 
        db.func.count(EventLog.id)
    ).join(EventLog, EventType.id == EventLog.event_type_id)\
     .filter(
        EventLog.timestamp >= inicio_dia_utc,
        EventLog.timestamp < fim_dia_utc
    ).group_by(EventType.name).all() # Ex: [('Errar Login', 5), ('Limpar Cache', 2)]
    
    # Prepara dados para o Chart.js
    dashboard_data = {
        'labels': [evento[0] for evento in contagem_hoje],
        'counts': [evento[1] for evento in contagem_hoje]
    }

    return render_template('eventos.html', 
                           title="Registro de Eventos do App",
                           tipos_de_evento=tipos_de_evento,
                           logs_recentes=logs_recentes,
                           dashboard_data=dashboard_data)


@app.route('/eventos/registrar/<int:event_type_id>', methods=['POST'])
@login_required
def registrar_evento(event_type_id):
    """Registra uma nova ocorrência de um evento."""
    
    # Verifica se o tipo de evento existe
    tipo_evento = db.session.get(EventType, event_type_id)
    if not tipo_evento:
        flash("Tipo de evento inválido.", "danger")
        return redirect(url_for('listar_eventos'))
        
    try:
        # Cria o novo registro de log
        novo_log = EventLog(
            user_id=current_user.id,
            event_type_id=event_type_id
            # timestamp é definido por 'default=datetime.utcnow'
        )
        db.session.add(novo_log)
        db.session.commit()
        flash(f"Evento '{tipo_evento.name}' registrado com sucesso!", 'success')
    except Exception as e:
        db.session.rollback()
        flash(f"Erro ao registrar evento: {e}", 'danger')
        
    return redirect(url_for('listar_eventos'))

# --- ROTAS DO PAINEL DE ADMINISTRAÇÃO ---

@app.route('/admin')
@login_required
@admin_required
def admin_dashboard():
    """Página principal do painel admin."""
    export_form = EventExportForm() 
    
    # --- Busca de Logs de Eventos (Existente) ---
    all_logs = EventLog.query.options(
        joinedload(EventLog.user),
        joinedload(EventLog.event_type)
    ).order_by(EventLog.timestamp.desc()).all()
    
    # ============================================
    # === ADIÇÃO: Busca Queries Pendentes ===
    pending_queries = QueryRequest.query.options(
        joinedload(QueryRequest.requester) # Carrega dados do solicitante
    ).filter_by(status='Pendente').order_by(QueryRequest.created_at.desc()).all()
    
    # === ADIÇÃO: Busca Queries Respondidas ===
    answered_queries = QueryRequest.query.options(
        joinedload(QueryRequest.requester), # Carrega solicitante
        joinedload(QueryRequest.responder)  # Carrega quem respondeu
    ).filter_by(status='Respondida').order_by(QueryRequest.answered_at.desc()).all()
    # ============================================

    return render_template('admin.html', 
                           title="Painel Admin", 
                           all_logs=all_logs,
                           export_form=export_form,
                           pending_queries=pending_queries,   # <-- Passa para o template
                           answered_queries=answered_queries  # <-- Passa para o template
                          )

@app.route('/admin/event/delete/<int:log_id>', methods=['POST'])
@login_required
@admin_required # Protege a rota
def admin_delete_event(log_id):
    """Rota para deletar um registro de log de evento."""
    
    log_to_delete = db.session.get(EventLog, log_id)
    if not log_to_delete:
        flash("Log de evento não encontrado.", "danger")
        return redirect(url_for('admin_dashboard'))
        
    try:
        db.session.delete(log_to_delete)
        db.session.commit()
        flash("Registro de evento removido com sucesso.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Erro ao remover o registro: {e}", "danger")
        
    return redirect(url_for('admin_dashboard'))

# --- FIM DAS ROTAS ADMIN ---
# --- FIM DAS ROTAS DE EVENTOS ---

@app.route('/admin/fila/pular', methods=['POST'])
@login_required
@admin_required
def admin_pular_fila():
    """
    Função de admin para forçar a fila a pular para o próximo atendente.
    """
    # 1. Carrega todos os membros da fila em ordem, com dados do usuário
    queue_members = PhoneQueueMember.query.options(
        joinedload(PhoneQueueMember.user)
    ).order_by(PhoneQueueMember.position).all()
    
    if not queue_members:
        flash("A fila telefônica está vazia. Ninguém para pular.", "warning")
        return redirect(url_for('admin_dashboard'))

    # 2. Descobre quem é o atendente ATUAL
    state = PhoneQueueState.query.filter_by(key='current_user_id').first()
    current_attendant_id = None
    
    if state and state.value.isdigit():
        current_attendant_id = int(state.value)
    else:
        # Se não houver estado, assume o primeiro da fila
        current_attendant_id = queue_members[0].user_id

    # 3. Encontra o índice (posição) do atendente ATUAL na lista
    current_index = -1
    for i, member in enumerate(queue_members):
        if member.user_id == current_attendant_id:
            current_index = i
            break
            
    if current_index == -1:
        # Isso acontece se o atendente atual foi removido da fila
        # Vamos apenas definir o próximo como o primeiro da lista
        next_member = queue_members[0]
        flash(f"Atendente atual (ID: {current_attendant_id}) não está mais na fila. Pulando para o primeiro.", "info")
    else:
        # 4. Calcula o PRÓXIMO atendente (mesma lógica do 'atender_telefone')
        next_index = (current_index + 1) % len(queue_members)
        next_member = queue_members[next_index]

    # 5. Atualiza o estado no banco de dados
    if not state:
        state = PhoneQueueState(key='current_user_id', value=str(next_member.user_id))
        db.session.add(state)
    else:
        state.value = str(next_member.user_id)
    
    try:
        db.session.commit()
        flash(f"Fila pulada com sucesso. O próximo atendente é {next_member.user.name}.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Erro ao pular a fila: {e}", "danger")
        return redirect(url_for('admin_dashboard'))

    # 6. Envia a notificação para o PRÓXIMO (copiado da sua rota)
    frases_divertidas = ["Atenção, marujo! O próximo navio (ligação) é seu!", "Acorda pra vida e reinicia o Zoiper, o próximo telefone é seu!", "Alôôôu! Já verifica o Zoiper, pois o próximo é seu.", "Sua hora chegou! Prepare-se, a próxima ligação é sua.", "Foguete não tem ré! A próxima chamada está na sua mira."]
    mensagem_sorteada = random.choice(frases_divertidas)
    
    if next_member.user and next_member.user.discord_id:
        try:
            payload = {'discord_id': next_member.user.discord_id, 'message': f"Olá {next_member.user.name}, {mensagem_sorteada} (Forçado pelo Admin)"}
            requests.post(DISCORD_BOT_URL, json=payload, timeout=3)
            flash(f"Notificação enviada para {next_member.user.name} no Discord!", "info")
        except requests.exceptions.RequestException:
            flash("Não foi possível notificar o próximo no Discord. O bot está online?", "danger")
    elif next_member.user:
        flash(f"A fila avançou para {next_member.user.name}, mas este usuário não tem um ID do Discord.", "warning")

    return redirect(url_for('admin_dashboard'))

# Em app.py, adicione esta nova rota:

@app.route('/api/eventos/recentes')
@login_required
def api_eventos_recentes():
    """
    Uma rota de API que retorna eventos mais recentes que um determinado ID.
    O JavaScript vai chamar isso a cada X segundos.
    """
    # Pega o ID do último evento que o cliente já tem (via query string)
    last_known_id = request.args.get('since_id', 0, type=int)
    
    # Busca no banco por logs MAIS NOVOS que o último ID conhecido
    # Carrega o usuário e o tipo de evento para evitar N+1 queries
    logs_novos = EventLog.query.options(
        joinedload(EventLog.user),
        joinedload(EventLog.event_type)
    ).filter(
        EventLog.id > last_known_id
    ).order_by(EventLog.id.desc()).all() # Pega os mais novos primeiro
    
    # Prepara os dados para enviar como JSON
    eventos_json = []
    for log in logs_novos:
        # Formata a data para BRT (UTC-3), já que o filtro 'brt' não funciona aqui
        timestamp_brt = (log.timestamp - timedelta(hours=3)).strftime('%d/%m/%Y às %H:%M')
        
        eventos_json.append({
            'id': log.id,
            'event_name': log.event_type.name,
            'user_name': log.user.name,
            'timestamp_brt': timestamp_brt
        })
        
    # Retorna a lista de novos eventos
    # O `jsonify` transforma o dicionário Python em uma resposta JSON
    return jsonify(novos_eventos=eventos_json)

# --- NOVA ROTA DE EXPORTAÇÃO DE EVENTOS ---
@app.route('/admin/exportar-eventos', methods=['POST'])
@login_required
@admin_required
def exportar_eventos_log():
    form = EventExportForm() # Valida os dados do formulário
    
    if form.validate_on_submit():
        # 1. Pegar datas do formulário (já são objetos date)
        start_date_brt = form.start_date.data
        end_date_brt = form.end_date.data

        # 2. Converter datas BRT (UTC-3) para UTC (UTC+0) para a query
        # Início do dia (00:00 BRT) -> 03:00 UTC
        start_datetime_utc = datetime(start_date_brt.year, start_date_brt.month, start_date_brt.day, 0, 0, 0) + timedelta(hours=3)
        # Fim do dia (23:59:59 BRT) -> 02:59:59 UTC do dia seguinte
        end_datetime_utc = datetime(end_date_brt.year, end_date_brt.month, end_date_brt.day, 23, 59, 59) + timedelta(hours=3)

        # 3. Buscar os logs detalhados no período
        logs_detalhados = EventLog.query.options(
            joinedload(EventLog.user),
            joinedload(EventLog.event_type)
        ).filter(
            EventLog.timestamp >= start_datetime_utc,
            EventLog.timestamp <= end_datetime_utc
        ).order_by(EventLog.timestamp.asc()).all()

        if not logs_detalhados:
            flash("Nenhum evento encontrado para o período selecionado.", "info")
            return redirect(url_for('admin_dashboard'))

        # 4. Calcular os totais
        # db.func.count(EventLog.id) é o "COUNT(*)" do SQL
        contagem_total = db.session.query(
            EventType.name, 
            db.func.count(EventLog.id).label('total')
        ).join(EventLog, EventType.id == EventLog.event_type_id)\
         .filter(
            EventLog.timestamp >= start_datetime_utc,
            EventLog.timestamp <= end_datetime_utc
        ).group_by(EventType.name).order_by(db.func.count(EventLog.id).desc()).all()

        # 5. Criar o Excel em memória
        try:
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                
                # --- Planilha 1: Resumo de Totais ---
                if contagem_total:
                    df_resumo = pd.DataFrame(contagem_total, columns=['Evento', 'Total de Ocorrências'])
                    df_resumo.to_excel(writer, sheet_name='Resumo de Totais', index=False)
                    # Adiciona a soma total no final
                    total_geral = df_resumo['Total de Ocorrências'].sum()
                    df_total = pd.DataFrame([{'Evento': 'TOTAL GERAL', 'Total de Ocorrências': total_geral}])
                    df_total.to_excel(writer, sheet_name='Resumo de Totais', startrow=len(df_resumo) + 2, index=False, header=False)
                else:
                    pd.DataFrame([{'Info': 'Nenhum evento para resumir'}]).to_excel(writer, sheet_name='Resumo de Totais', index=False)

                # --- Planilha 2: Log Detalhado ---
                logs_data = [{
                    'ID do Log': log.id,
                    'Evento': log.event_type.name,
                    'Usuário (Registrou)': log.user.name,
                    # Converte o timestamp UTC do banco para BRT (UTC-3)
                    'Data/Hora (BRT)': (log.timestamp - timedelta(hours=3)).strftime('%d/%m/%Y %H:%M:%S')
                } for log in logs_detalhados]
                
                df_logs = pd.DataFrame(logs_data)
                df_logs.to_excel(writer, sheet_name='Log Detalhado', index=False)
                
                # Auto-ajustar largura das colunas
                for sheet_name in writer.sheets:
                    worksheet = writer.sheets[sheet_name]
                    for column_cells in worksheet.columns:
                        max_length = 0
                        column_letter = column_cells[0].column_letter
                        for cell in column_cells:
                            if cell.value:
                                cell_len = len(str(cell.value))
                                if cell_len > max_length:
                                    max_length = cell_len
                        adjusted_width = (max_length + 2) * 1.2
                        worksheet.column_dimensions[column_letter].width = adjusted_width

            output.seek(0)
            
            # 6. Enviar o arquivo
            filename = f"relatorio_eventos_{start_date_brt.strftime('%Y%m%d')}_a_{end_date_brt.strftime('%Y%m%d')}.xlsx"
            return send_file(
                output,
                as_attachment=True,
                download_name=filename,
                mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            )

        except Exception as e_excel:
            print(f"Erro ao gerar Excel de eventos: {e_excel}")
            flash(f"Erro ao gerar o arquivo Excel: {e_excel}", "danger")

    else:
        # Se o formulário não for válido (ex: datas faltando)
        for field, errors in form.errors.items():
            for error in errors:
                flash(f"Erro na exportação: {error}", 'danger')
                
    return redirect(url_for('admin_dashboard'))


# Em app.py, na seção ROTAS DO PAINEL DE ADMINISTRAÇÃO

@app.route('/admin/usuarios')
@login_required
@admin_required
def admin_listar_usuarios():
    """Lista todos os usuários para gerenciamento."""
    # Paginação (opcional, mas bom para muitos usuários)
    page = request.args.get('page', 1, type=int)
    users = User.query.order_by(User.name).paginate(page=page, per_page=15) # 15 usuários por página
    return render_template('admin_usuarios.html', title="Gerenciar Usuários", users=users)

@app.route('/admin/usuario/editar/<int:user_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_editar_usuario(user_id):
    """Edita o perfil de um usuário específico."""
    user = db.session.get(User, user_id)
    if not user:
        flash("Usuário não encontrado.", "danger")
        return redirect(url_for('admin_listar_usuarios'))

    form = AdminEditUserForm()

    if form.validate_on_submit():
        # Atualiza os dados do usuário
        user.name = form.name.data
        user.username = form.username.data
        user.email = form.email.data
        user.discord_id = form.discord_id.data or None
        user.is_admin = form.is_admin.data
        
        # Atualiza a senha se o admin digitou uma nova
        if form.password.data:
            user.set_password(form.password.data)
            flash(f'Senha do usuário {user.username} foi redefinida.', 'info')
            
        try:
            db.session.commit()
            flash(f'Perfil de {user.username} atualizado com sucesso!', 'success')
            return redirect(url_for('admin_listar_usuarios'))
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao salvar o perfil: {e}', 'danger')

    elif request.method == 'GET':
        # Preenche o formulário com os dados atuais do usuário
        form.name.data = user.name
        form.username.data = user.username
        form.email.data = user.email
        form.discord_id.data = user.discord_id
        form.is_admin.data = user.is_admin
        # Armazena os valores originais para a validação (campos hidden)
        form.original_username.data = user.username
        form.original_email.data = user.email

    return render_template('admin_editar_usuario.html', 
                           title=f"Editar Usuário: {user.username}", 
                           form=form, 
                           user=user)
                           
# --- NOVA ROTA DE ADMIN PARA DELETAR QUERIES ---
@app.route('/admin/query/delete/<int:query_id>', methods=['POST'])
@login_required
@admin_required
def admin_delete_query(query_id):
    """Rota de admin para deletar uma solicitação de query."""
    
    # Busca a query pelo ID
    query_to_delete = db.session.get(QueryRequest, query_id)
    
    if not query_to_delete:
        flash("Solicitação de query não encontrada.", "danger")
        return redirect(url_for('admin_dashboard'))

    try:
        # Deleta a query do banco de dados
        db.session.delete(query_to_delete)
        db.session.commit()
        flash("Solicitação de query removida com sucesso.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Erro ao remover a solicitação de query: {e}", "danger")
        
    return redirect(url_for('admin_dashboard'))
# --- FIM DA NOVA ROTA ---
# ... (Mantenha suas outras rotas de admin: /admin, /admin/event/delete, /admin/fila/pular, /admin/exportar-eventos) ...
# ------------------- 5. BLOCO DE EXECUÇÃO -------------------
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)