from flask import Blueprint, render_template, redirect, url_for, flash
from flask_login import login_required, current_user
# REMOVIDO: from app import db, TutorialModule, ... (Isso causava o erro)

# Cria o "Mini-App"
tutorial_bp = Blueprint('tutorial', __name__, template_folder='templates')

@tutorial_bp.route('/academy')
@login_required
def index():
    # IMPORTAÇÃO TARDIA (DENTRO DA FUNÇÃO) PARA EVITAR CICLO
    from app import db, TutorialModule, TutorialLesson, UserProgress
    
    modules = TutorialModule.query.order_by(TutorialModule.order).all()
    
    # Calcula progresso total
    total_lessons = TutorialLesson.query.count()
    completed_lessons = UserProgress.query.filter_by(user_id=current_user.id, completed=True).count()
    progress_percent = int((completed_lessons / total_lessons) * 100) if total_lessons > 0 else 0
    
    return render_template('tutorial/index.html', 
                           title="Auvo Academy", 
                           modules=modules, 
                           progress=progress_percent)

@tutorial_bp.route('/academy/aula/<int:lesson_id>')
@login_required
def view_lesson(lesson_id):
    from app import db, TutorialModule, TutorialLesson, UserProgress
    
    lesson = db.session.get(TutorialLesson, lesson_id)
    if not lesson:
        flash('Aula não encontrada', 'danger')
        return redirect(url_for('tutorial.index'))
        
    modules = TutorialModule.query.order_by(TutorialModule.order).all()
    
    # Verifica se já completou
    progress = UserProgress.query.filter_by(user_id=current_user.id, lesson_id=lesson.id).first()
    is_completed = progress.completed if progress else False
    
    return render_template('tutorial/view_lesson.html', 
                           title=lesson.title, 
                           current_lesson=lesson, 
                           modules=modules, 
                           is_completed=is_completed)

@tutorial_bp.route('/academy/concluir/<int:lesson_id>', methods=['POST'])
@login_required
def mark_complete(lesson_id):
    from app import db, TutorialModule, TutorialLesson, UserProgress
    
    progress = UserProgress.query.filter_by(user_id=current_user.id, lesson_id=lesson_id).first()
    
    if not progress:
        progress = UserProgress(user_id=current_user.id, lesson_id=lesson_id, completed=True)
        db.session.add(progress)
    else:
        progress.completed = True
        
    db.session.commit()
    flash('Aula concluída! Parabéns.', 'success')
    
    # Tenta achar a próxima aula
    current_lesson = db.session.get(TutorialLesson, lesson_id)
    next_lesson = TutorialLesson.query.filter(
        TutorialLesson.module_id == current_lesson.module_id, 
        TutorialLesson.order > current_lesson.order
    ).order_by(TutorialLesson.order).first()
    
    if next_lesson:
        return redirect(url_for('tutorial.view_lesson', lesson_id=next_lesson.id))
    else:
        return redirect(url_for('tutorial.index'))