from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import os

app = Flask(__name__)
app.secret_key = 'lightfree_secret_key_2026_super_secret'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///lightfree.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# ==================== НАСТРОЙКИ ====================
COMMISSION_PERCENT = 10
ADMIN_CARD = "5536092301335542"
MAIN_DEVELOPER = "razrab"

# ==================== МОДЕЛИ ====================
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    full_name = db.Column(db.String(100), default='')
    phone = db.Column(db.String(20), default='')
    card_number = db.Column(db.String(20), default='')
    bank_name = db.Column(db.String(100), default='')
    balance = db.Column(db.Float, default=0.0)
    is_developer = db.Column(db.Boolean, default=False)
    is_blocked = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Service(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    price = db.Column(db.Float, nullable=False)
    category = db.Column(db.String(50), nullable=False)
    seller_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime, nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    seller = db.relationship('User', foreign_keys=[seller_id])

class ServiceOrder(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    service_id = db.Column(db.Integer, db.ForeignKey('service.id'), nullable=False)
    buyer_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    seller_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    commission = db.Column(db.Float, nullable=False)
    seller_gets = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), default='pending')
    payment_confirmed = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    service = db.relationship('Service', backref='orders')
    buyer = db.relationship('User', foreign_keys=[buyer_id])
    seller = db.relationship('User', foreign_keys=[seller_id])

class Task(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    price = db.Column(db.Float, nullable=False)
    category = db.Column(db.String(50), nullable=False)
    client_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    executor_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    status = db.Column(db.String(20), default='open')
    expires_at = db.Column(db.DateTime, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    client = db.relationship('User', foreign_keys=[client_id])
    executor = db.relationship('User', foreign_keys=[executor_id])

class TaskOrder(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    task_id = db.Column(db.Integer, db.ForeignKey('task.id'), nullable=False)
    client_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    executor_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    commission = db.Column(db.Float, nullable=False)
    executor_gets = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), default='pending')
    payment_confirmed = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    task = db.relationship('Task', backref='orders')
    client = db.relationship('User', foreign_keys=[client_id])
    executor = db.relationship('User', foreign_keys=[executor_id])

class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, nullable=False)
    order_type = db.Column(db.String(20), default='service')
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    text = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    sender = db.relationship('User', foreign_keys=[sender_id])

class AdminBalance(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    total_commission = db.Column(db.Float, default=0.0)
    last_updated = db.Column(db.DateTime, default=datetime.utcnow)

# ==================== СОЗДАНИЕ БД (БЕЗ УДАЛЕНИЯ) ====================
with app.app_context():
    db.create_all()
    print("✅ База данных LightFree готова")
    
    if not AdminBalance.query.first():
        admin = AdminBalance(total_commission=0.0)
        db.session.add(admin)
        db.session.commit()
        print("✅ Создан баланс платформы")
    
    main_dev = User.query.filter_by(username=MAIN_DEVELOPER).first()
    if not main_dev:
        dev = User(
            username=MAIN_DEVELOPER,
            password=generate_password_hash('Vadim06.04.2012'),
            email='dev@lightfree.ru',
            full_name='Главный разработчик',
            is_developer=True,
            is_blocked=False,
            balance=0.0
        )
        db.session.add(dev)
        db.session.commit()
        print(f"✅ Создан разработчик: {MAIN_DEVELOPER} (пароль: Vadim06.04.2012)")

# ==================== ФУНКЦИИ ====================
def delete_expired_services():
    now = datetime.utcnow()
    expired = Service.query.filter(Service.is_active == True, Service.expires_at <= now).all()
    for s in expired:
        s.is_active = False
        db.session.delete(s)
    if expired:
        db.session.commit()

def delete_expired_tasks():
    now = datetime.utcnow()
    expired = Task.query.filter(Task.status == 'open', Task.expires_at <= now).all()
    for t in expired:
        t.status = 'cancelled'
    if expired:
        db.session.commit()

# ==================== ДЕКОРАТОРЫ ====================
def login_required(f):
    def wrapper(*args, **kwargs):
        if 'user_id' not in session:
            flash('❌ Пожалуйста, войдите в аккаунт')
            return redirect(url_for('login'))
        
        user = User.query.get(session['user_id'])
        if not user:
            session.clear()
            flash('❌ Сессия устарела, войдите заново')
            return redirect(url_for('login'))
        
        if user.is_blocked:
            session.clear()
            flash('❌ Ваш аккаунт заблокирован')
            return redirect(url_for('login'))
        
        return f(*args, **kwargs)
    wrapper.__name__ = f.__name__
    return wrapper

def developer_required(f):
    def wrapper(*args, **kwargs):
        if 'user_id' not in session:
            flash('❌ Пожалуйста, войдите в аккаунт')
            return redirect(url_for('login'))
        
        user = User.query.get(session['user_id'])
        if not user or not user.is_developer:
            flash('❌ Доступ только для разработчиков')
            return redirect(url_for('index'))
        
        return f(*args, **kwargs)
    wrapper.__name__ = f.__name__
    return wrapper

# ==================== МАРШРУТЫ ====================
@app.route('/')
def index():
    delete_expired_services()
    delete_expired_tasks()
    
    services = Service.query.filter_by(is_active=True).order_by(Service.created_at.desc()).limit(6).all()
    tasks = Task.query.filter_by(status='open').order_by(Task.created_at.desc()).limit(6).all()
    
    categories = db.session.query(Service.category).distinct().all()
    categories = [cat[0] for cat in categories if cat[0]]
    
    return render_template('index.html', services=services, tasks=tasks, categories=categories)

# ==================== УСЛУГИ ====================
@app.route('/services')
def services_list():
    delete_expired_services()
    services = Service.query.filter_by(is_active=True).all()
    return render_template('services.html', services=services, title='Все услуги')

@app.route('/services/category/<category>')
def services_by_category(category):
    delete_expired_services()
    services = Service.query.filter_by(category=category, is_active=True).all()
    return render_template('services.html', services=services, title=f'Услуги: {category}')

@app.route('/service/<int:service_id>')
@login_required
def service_detail(service_id):
    user = User.query.get(session['user_id'])
    service = Service.query.get_or_404(service_id)
    
    if service.is_active and service.expires_at <= datetime.utcnow():
        service.is_active = False
        db.session.delete(service)
        db.session.commit()
        flash('❌ Срок действия услуги истёк')
        return redirect(url_for('index'))
    
    return render_template('service_detail.html', service=service, user=user)

@app.route('/create-service', methods=['GET', 'POST'])
@login_required
def create_service():
    user = User.query.get(session['user_id'])
    
    if request.method == 'POST':
        title = request.form['title']
        description = request.form['description']
        price = float(request.form['price'])
        category = request.form['category']
        
        days_str = request.form.get('days', '0')
        hours_str = request.form.get('hours', '0')
        minutes_str = request.form.get('minutes', '0')
        
        days = int(days_str) if days_str and days_str.strip() else 0
        hours = int(hours_str) if hours_str and hours_str.strip() else 0
        minutes = int(minutes_str) if minutes_str and minutes_str.strip() else 0
        
        expires_at = datetime.utcnow() + timedelta(days=days, hours=hours, minutes=minutes)
        
        service = Service(
            title=title, description=description, price=price,
            category=category, seller_id=user.id, expires_at=expires_at
        )
        db.session.add(service)
        db.session.commit()
        flash('✅ Услуга создана!')
        return redirect(url_for('index'))
    
    return render_template('create_service.html')

@app.route('/buy-service/<int:service_id>')
@login_required
def buy_service(service_id):
    user = User.query.get(session['user_id'])
    service = Service.query.get_or_404(service_id)
    
    if service.seller_id == user.id:
        flash('❌ Нельзя купить свою услугу')
        return redirect(url_for('index'))
    
    if service.expires_at <= datetime.utcnow():
        flash('❌ Срок действия услуги истёк')
        return redirect(url_for('index'))
    
    existing = ServiceOrder.query.filter_by(service_id=service.id, buyer_id=user.id, status='pending').first()
    if existing:
        return redirect(url_for('service_payment', order_id=existing.id))
    
    commission = service.price * COMMISSION_PERCENT / 100
    seller_gets = service.price - commission
    
    order = ServiceOrder(
        service_id=service.id, buyer_id=user.id, seller_id=service.seller_id,
        amount=service.price, commission=commission, seller_gets=seller_gets, status='pending'
    )
    db.session.add(order)
    db.session.commit()
    return redirect(url_for('service_payment', order_id=order.id))

@app.route('/service-payment/<int:order_id>')
@login_required
def service_payment(order_id):
    user = User.query.get(session['user_id'])
    order = ServiceOrder.query.get_or_404(order_id)
    if order.buyer_id != user.id:
        flash('❌ Это не ваш заказ')
        return redirect(url_for('index'))
    seller = User.query.get(order.seller_id)
    return render_template('service_payment.html', order=order, seller=seller)

@app.route('/confirm-service-payment/<int:order_id>', methods=['POST'])
@login_required
def confirm_service_payment(order_id):
    user = User.query.get(session['user_id'])
    order = ServiceOrder.query.get_or_404(order_id)
    if order.buyer_id != user.id:
        return jsonify({'error': 'Доступ запрещён'}), 403
    
    order.payment_confirmed = True
    order.status = 'paid'
    db.session.commit()
    
    admin = AdminBalance.query.first()
    admin.total_commission += order.commission
    db.session.commit()
    
    flash(f'✅ Оплата подтверждена! Комиссия 10% ({order.commission:.2f} ₽) зачислена.')
    return redirect(url_for('service_order_detail', order_id=order.id))

@app.route('/complete-service-order/<int:order_id>', methods=['POST'])
@login_required
def complete_service_order(order_id):
    user = User.query.get(session['user_id'])
    order = ServiceOrder.query.get_or_404(order_id)
    if order.seller_id != user.id:
        return jsonify({'error': 'Доступ запрещён'}), 403
    
    order.status = 'completed'
    service = Service.query.get(order.service_id)
    service.is_active = False
    db.session.commit()
    flash('✅ Работа выполнена! Заказ завершён.')
    return redirect(url_for('service_order_detail', order_id=order.id))

@app.route('/service-order/<int:order_id>')
@login_required
def service_order_detail(order_id):
    user = User.query.get(session['user_id'])
    order = ServiceOrder.query.get_or_404(order_id)
    if order.buyer_id != user.id and order.seller_id != user.id:
        flash('❌ Доступ запрещён')
        return redirect(url_for('index'))
    
    messages = Message.query.filter_by(order_id=order_id, order_type='service').order_by(Message.created_at).all()
    seller = User.query.get(order.seller_id)
    return render_template('service_order_detail.html', order=order, messages=messages, seller=seller)

# ==================== ЗАДАНИЯ ====================
@app.route('/tasks')
def tasks_list():
    delete_expired_tasks()
    tasks = Task.query.filter_by(status='open').all()
    return render_template('tasks.html', tasks=tasks, title='Все задания')

@app.route('/tasks/category/<category>')
def tasks_by_category(category):
    delete_expired_tasks()
    tasks = Task.query.filter_by(category=category, status='open').all()
    return render_template('tasks.html', tasks=tasks, title=f'Задания: {category}')

@app.route('/task/<int:task_id>')
@login_required
def task_detail(task_id):
    user = User.query.get(session['user_id'])
    task = Task.query.get_or_404(task_id)
    
    if task.status == 'open' and task.expires_at <= datetime.utcnow():
        task.status = 'cancelled'
        db.session.commit()
        flash('❌ Срок выполнения задания истёк')
        return redirect(url_for('index'))
    
    return render_template('task_detail.html', task=task, user=user)

@app.route('/create-task', methods=['GET', 'POST'])
@login_required
def create_task():
    user = User.query.get(session['user_id'])
    
    if request.method == 'POST':
        title = request.form['title']
        description = request.form['description']
        price = float(request.form['price'])
        category = request.form['category']
        
        days_str = request.form.get('days', '0')
        hours_str = request.form.get('hours', '0')
        minutes_str = request.form.get('minutes', '0')
        
        days = int(days_str) if days_str and days_str.strip() else 0
        hours = int(hours_str) if hours_str and hours_str.strip() else 0
        minutes = int(minutes_str) if minutes_str and minutes_str.strip() else 0
        
        expires_at = datetime.utcnow() + timedelta(days=days, hours=hours, minutes=minutes)
        
        task = Task(
            title=title, description=description, price=price,
            category=category, client_id=user.id, expires_at=expires_at
        )
        db.session.add(task)
        db.session.commit()
        flash('✅ Задание создано! Ожидайте исполнителей.')
        return redirect(url_for('index'))
    
    return render_template('create_task.html')

@app.route('/take-task/<int:task_id>')
@login_required
def take_task(task_id):
    user = User.query.get(session['user_id'])
    task = Task.query.get_or_404(task_id)
    
    if task.client_id == user.id:
        flash('❌ Нельзя взять своё задание')
        return redirect(url_for('index'))
    
    if task.status != 'open':
        flash('❌ Задание уже не доступно')
        return redirect(url_for('index'))
    
    if task.expires_at <= datetime.utcnow():
        flash('❌ Срок выполнения истёк')
        return redirect(url_for('index'))
    
    task.executor_id = user.id
    task.status = 'in_progress'
    db.session.commit()
    
    flash('✅ Вы взяли задание! Свяжитесь с заказчиком.')
    return redirect(url_for('task_order_detail', task_id=task.id))

@app.route('/task-order/<int:task_id>')
@login_required
def task_order_detail(task_id):
    user = User.query.get(session['user_id'])
    task = Task.query.get_or_404(task_id)
    
    if task.client_id != user.id and task.executor_id != user.id:
        flash('❌ Доступ запрещён')
        return redirect(url_for('index'))
    
    messages = Message.query.filter_by(order_id=task_id, order_type='task').order_by(Message.created_at).all()
    return render_template('task_order_detail.html', task=task, messages=messages)

@app.route('/complete-task/<int:task_id>', methods=['POST'])
@login_required
def complete_task(task_id):
    user = User.query.get(session['user_id'])
    task = Task.query.get_or_404(task_id)
    
    if task.client_id != user.id:
        flash('❌ Только заказчик может завершить задание')
        return redirect(url_for('index'))
    
    if task.status != 'in_progress':
        flash('❌ Задание не в работе')
        return redirect(url_for('index'))
    
    task.status = 'completed'
    
    commission = task.price * COMMISSION_PERCENT / 100
    executor_gets = task.price - commission
    
    order = TaskOrder(
        task_id=task.id,
        client_id=task.client_id,
        executor_id=task.executor_id,
        amount=task.price,
        commission=commission,
        executor_gets=executor_gets,
        status='completed',
        payment_confirmed=True
    )
    db.session.add(order)
    
    admin = AdminBalance.query.first()
    admin.total_commission += commission
    db.session.commit()
    
    flash(f'✅ Задание завершено! Исполнитель получит {executor_gets:.2f} ₽ (комиссия {commission:.2f} ₽)')
    return redirect(url_for('task_order_detail', task_id=task.id))

@app.route('/cancel-task/<int:task_id>', methods=['POST'])
@login_required
def cancel_task(task_id):
    user = User.query.get(session['user_id'])
    task = Task.query.get_or_404(task_id)
    
    if task.client_id != user.id:
        flash('❌ Только заказчик может отменить задание')
        return redirect(url_for('index'))
    
    task.status = 'cancelled'
    db.session.commit()
    flash('❌ Задание отменено')
    return redirect(url_for('index'))

@app.route('/cancel-task-executor/<int:task_id>', methods=['POST'])
@login_required
def cancel_task_executor(task_id):
    user = User.query.get(session['user_id'])
    task = Task.query.get_or_404(task_id)
    
    if task.executor_id != user.id:
        flash('❌ Только исполнитель может отказаться')
        return redirect(url_for('index'))
    
    task.executor_id = None
    task.status = 'open'
    db.session.commit()
    flash('✅ Вы отказались от задания')
    return redirect(url_for('index'))

# ==================== ОБЩИЙ ЧАТ ====================
@app.route('/send-message', methods=['POST'])
@login_required
def send_message():
    user = User.query.get(session['user_id'])
    
    order_id = int(request.form.get('order_id'))
    order_type = request.form.get('order_type', 'service')
    text = request.form.get('text', '').strip()
    
    if not text:
        return jsonify({'error': 'Сообщение не может быть пустым'}), 400
    
    if order_type == 'service':
        order = ServiceOrder.query.get_or_404(order_id)
        if order.buyer_id != user.id and order.seller_id != user.id:
            return jsonify({'error': 'Доступ запрещён'}), 403
    else:
        task = Task.query.get_or_404(order_id)
        if task.client_id != user.id and (task.executor_id != user.id and task.executor_id is not None):
            return jsonify({'error': 'Доступ запрещён'}), 403
    
    message = Message(
        order_id=order_id,
        order_type=order_type,
        sender_id=user.id,
        text=text
    )
    db.session.add(message)
    db.session.commit()
    
    return jsonify({
        'id': message.id,
        'text': message.text,
        'sender': user.username,
        'created_at': message.created_at.strftime('%Y-%m-%d %H:%M')
    })

@app.route('/api/messages/<order_type>/<int:order_id>')
@login_required
def get_messages(order_type, order_id):
    user = User.query.get(session['user_id'])
    
    if order_type == 'service':
        order = ServiceOrder.query.get_or_404(order_id)
        if order.buyer_id != user.id and order.seller_id != user.id:
            return jsonify({'error': 'Доступ запрещён'}), 403
    else:
        task = Task.query.get_or_404(order_id)
        if task.client_id != user.id and (task.executor_id != user.id and task.executor_id is not None):
            return jsonify({'error': 'Доступ запрещён'}), 403
    
    messages = Message.query.filter_by(order_id=order_id, order_type=order_type).order_by(Message.created_at).all()
    return jsonify([{
        'id': m.id,
        'text': m.text,
        'sender': m.sender.username,
        'created_at': m.created_at.strftime('%Y-%m-%d %H:%M')
    } for m in messages])

# ==================== ПРОФИЛЬ ====================
@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    user = User.query.get(session['user_id'])
    
    if request.method == 'POST':
        user.full_name = request.form['full_name']
        user.phone = request.form['phone']
        user.card_number = request.form['card_number']
        user.bank_name = request.form['bank_name']
        db.session.commit()
        flash('✅ Профиль обновлён!')
    
    service_orders_buyer = ServiceOrder.query.filter_by(buyer_id=user.id).all()
    service_orders_seller = ServiceOrder.query.filter_by(seller_id=user.id).all()
    
    task_orders_client = Task.query.filter_by(client_id=user.id).all()
    task_orders_executor = Task.query.filter_by(executor_id=user.id).all()
    
    total_bought = len(service_orders_buyer)
    total_spent = sum(o.amount for o in service_orders_buyer)
    total_sold = len(service_orders_seller)
    total_earned = sum(o.seller_gets for o in service_orders_seller)
    
    total_tasks_client = len(task_orders_client)
    total_tasks_executor = len(task_orders_executor)
    
    active_services = Service.query.filter_by(seller_id=user.id, is_active=True).count()
    
    all_users = User.query.all() if user.is_developer else []
    admin_balance = AdminBalance.query.first()
    
    return render_template('profile.html', 
                          user=user,
                          service_orders_buyer=service_orders_buyer,
                          service_orders_seller=service_orders_seller,
                          task_orders_client=task_orders_client,
                          task_orders_executor=task_orders_executor,
                          total_bought=total_bought,
                          total_spent=total_spent,
                          total_sold=total_sold,
                          total_earned=total_earned,
                          total_tasks_client=total_tasks_client,
                          total_tasks_executor=total_tasks_executor,
                          active_services=active_services,
                          all_users=all_users,
                          admin_balance=admin_balance)

# ==================== РАЗРАБОТЧИК ====================
@app.route('/developer/add', methods=['POST'])
@developer_required
def add_developer():
    username = request.form['username']
    user = User.query.filter_by(username=username).first()
    if not user:
        flash('❌ Пользователь не найден')
        return redirect(url_for('profile'))
    if user.is_developer:
        flash('⚠️ Пользователь уже разработчик')
        return redirect(url_for('profile'))
    user.is_developer = True
    db.session.commit()
    flash(f'✅ Пользователь {username} назначен разработчиком!')
    return redirect(url_for('profile'))

@app.route('/developer/remove', methods=['POST'])
@developer_required
def remove_developer():
    username = request.form['username']
    user = User.query.filter_by(username=username).first()
    if not user:
        flash('❌ Пользователь не найден')
        return redirect(url_for('profile'))
    if user.username == MAIN_DEVELOPER:
        flash('❌ Нельзя удалить главного разработчика')
        return redirect(url_for('profile'))
    if not user.is_developer:
        flash('⚠️ Пользователь не разработчик')
        return redirect(url_for('profile'))
    user.is_developer = False
    db.session.commit()
    flash(f'✅ Пользователь {username} лишён прав разработчика')
    return redirect(url_for('profile'))

@app.route('/developer/block', methods=['POST'])
@developer_required
def block_user():
    username = request.form['username']
    user = User.query.filter_by(username=username).first()
    if not user:
        flash('❌ Пользователь не найден')
        return redirect(url_for('profile'))
    if user.username == MAIN_DEVELOPER:
        flash('❌ Нельзя заблокировать главного разработчика')
        return redirect(url_for('profile'))
    if user.is_blocked:
        flash('⚠️ Пользователь уже заблокирован')
        return redirect(url_for('profile'))
    user.is_blocked = True
    db.session.commit()
    flash(f'✅ Пользователь {username} заблокирован!')
    return redirect(url_for('profile'))

@app.route('/developer/unblock', methods=['POST'])
@developer_required
def unblock_user():
    username = request.form['username']
    user = User.query.filter_by(username=username).first()
    if not user:
        flash('❌ Пользователь не найден')
        return redirect(url_for('profile'))
    if not user.is_blocked:
        flash('⚠️ Пользователь не заблокирован')
        return redirect(url_for('profile'))
    user.is_blocked = False
    db.session.commit()
    flash(f'✅ Пользователь {username} разблокирован!')
    return redirect(url_for('profile'))

@app.route('/developer/delete-service/<int:service_id>', methods=['POST'])
@developer_required
def delete_service_admin(service_id):
    service = Service.query.get_or_404(service_id)
    db.session.delete(service)
    db.session.commit()
    flash('✅ Услуга удалена администратором!')
    return redirect(url_for('index'))

@app.route('/developer/delete-task/<int:task_id>', methods=['POST'])
@developer_required
def delete_task_admin(task_id):
    task = Task.query.get_or_404(task_id)
    db.session.delete(task)
    db.session.commit()
    flash('✅ Задание удалено администратором!')
    return redirect(url_for('index'))

# ==================== АВТОРИЗАЦИЯ ====================
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = generate_password_hash(request.form['password'])
        email = request.form['email']
        full_name = request.form.get('full_name', '')
        phone = request.form.get('phone', '')
        
        if User.query.filter_by(username=username).first():
            flash('❌ Логин уже занят')
            return redirect(url_for('register'))
        if User.query.filter_by(email=email).first():
            flash('❌ Email уже используется')
            return redirect(url_for('register'))
        
        user = User(username=username, password=password, email=email, 
                    full_name=full_name, phone=phone, balance=0.0)
        db.session.add(user)
        db.session.commit()
        flash('✅ Регистрация успешна! Войдите в аккаунт.')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            if user.is_blocked:
                flash('❌ Ваш аккаунт заблокирован')
                return redirect(url_for('login'))
            session['user_id'] = user.id
            session['username'] = user.username
            flash('👋 Добро пожаловать в LightFree!')
            return redirect(url_for('index'))
        flash('❌ Неверный логин или пароль')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('Вы вышли из аккаунта')
    return redirect(url_for('index'))

# ==================== СОЗДАНИЕ HTML-ФАЙЛОВ ====================
if not os.path.exists('templates'):
    os.makedirs('templates')

# БАЗОВЫЙ ШАБЛОН
HTML_BASE = '''<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>LightFree - биржа услуг</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; font-family: 'Segoe UI', system-ui, sans-serif; }
        body { background: #0b0e14; color: #e4e6eb; min-height: 100vh; }
        .header { background: #14181f; padding: 16px 40px; display: flex; align-items: center; justify-content: space-between; border-bottom: 1px solid #2a313c; flex-wrap: wrap; gap: 10px; }
        .logo { font-size: 28px; font-weight: 800; background: linear-gradient(135deg, #22c55e, #16a34a); -webkit-background-clip: text; -webkit-text-fill-color: transparent; cursor: pointer; }
        nav { display: flex; flex-wrap: wrap; gap: 10px; align-items: center; }
        nav a { color: #a0aec0; text-decoration: none; font-weight: 500; transition: 0.3s; padding: 8px 12px; border-radius: 8px; }
        nav a:hover { color: #22c55e; background: #1a1f2a; }
        .search-form { display: flex; gap: 5px; }
        .search-form input { padding: 8px 12px; background: #0b0e14; border: 1px solid #2a313c; border-radius: 8px; color: #e4e6eb; width: 150px; }
        .search-form button { padding: 8px 16px; background: linear-gradient(135deg, #22c55e, #16a34a); border: none; border-radius: 8px; color: #0b0e14; cursor: pointer; font-weight: 600; }
        main { max-width: 1200px; margin: 0 auto; padding: 30px 20px; min-height: 70vh; }
        .flash { margin-bottom: 20px; }
        .flash-message { background: #1a1f2a; border-left: 4px solid #22c55e; padding: 12px 20px; margin-bottom: 10px; border-radius: 8px; }
        .btn { display: inline-block; padding: 10px 24px; background: linear-gradient(135deg, #22c55e, #16a34a); color: #0b0e14; text-decoration: none; border-radius: 8px; font-weight: 600; transition: 0.3s; border: none; cursor: pointer; font-size: 14px; }
        .btn:hover { transform: translateY(-2px); box-shadow: 0 4px 20px rgba(34, 197, 94, 0.3); }
        .btn-green { background: linear-gradient(135deg, #22c55e, #16a34a); }
        .btn-red { background: linear-gradient(135deg, #ef4444, #dc2626); }
        .btn-blue { background: linear-gradient(135deg, #3b82f6, #2563eb); }
        .btn-purple { background: linear-gradient(135deg, #8b5cf6, #7c3aed); }
        .form-container { max-width: 500px; margin: 40px auto; background: #14181f; padding: 40px; border-radius: 16px; border: 1px solid #2a313c; }
        .form-container h2 { text-align: center; margin-bottom: 30px; color: #22c55e; }
        .form-container input, .form-container textarea { width: 100%; padding: 12px 16px; margin-bottom: 15px; background: #0b0e14; border: 1px solid #2a313c; border-radius: 8px; color: #e4e6eb; font-size: 16px; }
        .form-container textarea { min-height: 100px; resize: vertical; }
        .form-container button { width: 100%; padding: 14px; background: linear-gradient(135deg, #22c55e, #16a34a); border: none; border-radius: 8px; font-size: 18px; font-weight: 600; color: #0b0e14; cursor: pointer; transition: 0.3s; }
        .form-container button:hover { transform: translateY(-2px); box-shadow: 0 4px 20px rgba(34, 197, 94, 0.3); }
        .form-row { display: flex; gap: 10px; margin-bottom: 15px; }
        .form-row .form-group { flex: 1; }
        .form-row .form-group label { display: block; color: #a0aec0; font-size: 14px; margin-bottom: 5px; }
        .form-row .form-group input { width: 100%; padding: 10px; background: #0b0e14; border: 1px solid #2a313c; border-radius: 8px; color: #e4e6eb; }
        .grid-2col { display: grid; grid-template-columns: 1fr 1fr; gap: 30px; margin-top: 20px; }
        @media (max-width: 768px) { .grid-2col { grid-template-columns: 1fr; } }
        .service-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 20px; margin-top: 20px; }
        .service-card { background: #14181f; border: 1px solid #2a313c; border-radius: 12px; padding: 20px; transition: 0.3s; cursor: pointer; }
        .service-card:hover { transform: translateY(-4px); border-color: #22c55e; box-shadow: 0 8px 30px rgba(0,0,0,0.3); }
        .service-card h3 { color: #22c55e; margin-bottom: 10px; }
        .service-card .price { font-size: 22px; font-weight: 700; color: #22c55e; margin: 10px 0; }
        .service-card .seller { color: #a0aec0; font-size: 14px; margin-bottom: 12px; }
        .service-card .expires { color: #a0aec0; font-size: 12px; margin-top: 5px; }
        .task-card { background: #14181f; border: 1px solid #2a313c; border-radius: 12px; padding: 20px; transition: 0.3s; cursor: pointer; border-left: 3px solid #f59e0b; }
        .task-card:hover { transform: translateY(-4px); border-color: #f59e0b; box-shadow: 0 8px 30px rgba(0,0,0,0.3); }
        .task-card h3 { color: #f59e0b; margin-bottom: 10px; }
        .task-card .price { font-size: 22px; font-weight: 700; color: #f59e0b; margin: 10px 0; }
        .task-card .client { color: #a0aec0; font-size: 14px; margin-bottom: 12px; }
        .category-list { display: flex; flex-wrap: wrap; gap: 10px; margin: 20px 0; }
        .category-item { padding: 10px 20px; background: #14181f; border: 1px solid #2a313c; border-radius: 20px; color: #a0aec0; text-decoration: none; transition: 0.3s; }
        .category-item:hover { background: #1a1f2a; color: #22c55e; border-color: #22c55e; }
        .chat-box { background: #0b0e14; border: 1px solid #2a313c; border-radius: 12px; padding: 20px; height: 400px; overflow-y: auto; margin-bottom: 15px; }
        .message { margin-bottom: 10px; padding: 10px; border-radius: 8px; background: #14181f; }
        .message .sender { color: #22c55e; font-weight: 600; }
        .message .time { color: #a0aec0; font-size: 12px; margin-left: 10px; }
        .message .text { margin-top: 5px; }
        .hero { background: linear-gradient(135deg, #14181f, #1a1f2a); padding: 60px 40px; border-radius: 16px; text-align: center; margin-bottom: 40px; border: 1px solid #2a313c; }
        .hero h1 { font-size: 42px; margin-bottom: 15px; background: linear-gradient(135deg, #22c55e, #16a34a); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
        .status-pending { color: #f59e0b; }
        .status-paid { color: #22c55e; }
        .status-completed { color: #3b82f6; }
        .status-open { color: #22c55e; }
        .status-in_progress { color: #f59e0b; }
        .status-cancelled { color: #ef4444; }
        .profile-section { background: #14181f; border: 1px solid #2a313c; border-radius: 12px; padding: 24px; margin-bottom: 20px; }
        .stat-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 15px; margin-top: 15px; }
        .stat-item { background: #0b0e14; padding: 15px; border-radius: 8px; border-left: 3px solid #22c55e; }
        .stat-item .stat-value { font-size: 24px; font-weight: 700; color: #22c55e; }
        .stat-item .stat-label { color: #a0aec0; font-size: 14px; margin-top: 5px; }
        .developer-badge { background: #8b5cf6; color: white; padding: 2px 10px; border-radius: 12px; font-size: 12px; }
        .blocked-badge { background: #ef4444; color: white; padding: 2px 10px; border-radius: 12px; font-size: 12px; }
        .service-detail-card { background: #14181f; border: 1px solid #2a313c; border-radius: 16px; padding: 40px; max-width: 800px; margin: 0 auto; }
        .service-detail-card h1 { color: #22c55e; font-size: 32px; margin-bottom: 15px; }
        .service-detail-card .price { font-size: 36px; font-weight: 700; color: #22c55e; margin: 20px 0; }
        .service-detail-card .description { font-size: 16px; line-height: 1.8; color: #e4e6eb; margin: 20px 0; }
        .task-detail-card { background: #14181f; border: 1px solid #2a313c; border-radius: 16px; padding: 40px; max-width: 800px; margin: 0 auto; border-left: 4px solid #f59e0b; }
        .task-detail-card h1 { color: #f59e0b; font-size: 32px; margin-bottom: 15px; }
        .task-detail-card .price { font-size: 36px; font-weight: 700; color: #f59e0b; margin: 20px 0; }
        .payment-info { background: #0b0e14; padding: 20px; border-radius: 12px; margin: 15px 0; border: 1px solid #2a313c; }
        .payment-info .label { color: #a0aec0; font-size: 14px; }
        .payment-info .value { font-size: 18px; font-weight: 600; margin: 5px 0; }
        .section-title { color: #22c55e; margin: 30px 0 15px; border-bottom: 1px solid #2a313c; padding-bottom: 10px; }
        .section-title-green { color: #f59e0b; margin: 30px 0 15px; border-bottom: 1px solid #2a313c; padding-bottom: 10px; }
        footer { text-align: center; padding: 30px; color: #a0aec0; border-top: 1px solid #2a313c; margin-top: 40px; }
        @media (max-width: 768px) { .header { padding: 12px 20px; } .hero h1 { font-size: 28px; } .service-grid { grid-template-columns: 1fr; } .search-form input { width: 100px; } .form-row { flex-direction: column; } }
    </style>
</head>
<body>
    <header class="header">
        <div class="logo">🌱 LightFree</div>
        <nav>
            <a href="/">Главная</a>
            <a href="/services">Услуги</a>
            <a href="/tasks">Задания</a>
            <form class="search-form" action="/search" method="get">
                <input type="text" name="q" placeholder="Поиск...">
                <button type="submit">🔍</button>
            </form>
            {% if session.user_id %}
                <a href="/create-service">+ Услуга</a>
                <a href="/create-task">+ Задание</a>
                <a href="/profile">👤 {{ session.username }}</a>
                <a href="/logout">Выйти</a>
            {% else %}
                <a href="/login">Вход</a>
                <a href="/register">Регистрация</a>
            {% endif %}
        </nav>
    </header>
    <main>
        {% with messages = get_flashed_messages() %}
            {% if messages %}
                <div class="flash">
                    {% for message in messages %}
                        <div class="flash-message">{{ message }}</div>
                    {% endfor %}
                </div>
            {% endif %}
        {% endwith %}
        {% block content %}{% endblock %}
    </main>
    <footer>LightFree © 2026 — безопасная биржа услуг и заданий</footer>
</body>
</html>'''

# ВСЕ ШАБЛОНЫ
templates  = {
    'base.html': HTML_BASE,
    'index.html': '''
{% extends "base.html" %}
{% block content %}
<div class="hero">
    <h1>Покупайте услуги и находите исполнителей</h1>
    <p style="color:#a0aec0;font-size:18px;">🔒 Безопасные сделки с защитой покупателя и продавца</p>
    <span style="display:inline-block;background:#22c55e;color:#0b0e14;padding:6px 16px;border-radius:20px;font-weight:600;font-size:14px;margin-top:15px;">🛡️ Защита сделки</span>
    {% if not session.user_id %}<br><br><a href="/register" class="btn">Начать зарабатывать</a>{% endif %}
</div>
<div class="categories">
    <h2 style="color:#22c55e;">📂 Категории</h2>
    <div class="category-list">
        {% for cat in categories %}<a href="/services/category/{{ cat }}" class="category-item">{{ cat }}</a>{% endfor %}
        {% if not categories %}<span style="color:#a0aec0;">Пока нет категорий</span>{% endif %}
    </div>
</div>
<div class="grid-2col">
    <div>
        <h2 class="section-title">🛒 Услуги</h2>
        <div class="service-grid">
            {% for service in services %}
                <div class="service-card" onclick="window.location='/service/{{ service.id }}'">
                    <h3>{{ service.title }}</h3>
                    <p style="color:#a0aec0;font-size:14px;">{{ service.category }}</p>
                    <p class="price">{{ service.price }} ₽</p>
                    <p class="seller">👤 {{ service.seller.username }}</p>
                    <p class="expires">⏳ {{ service.expires_at.strftime('%d.%m.%Y') }}</p>
                    <a href="/buy-service/{{ service.id }}" class="btn">Купить</a>
                    <a href="/service/{{ service.id }}" class="btn btn-blue" style="margin-left:10px;">Подробнее</a>
                </div>
            {% else %}<p style="color:#a0aec0;">Услуг пока нет.</p>{% endfor %}
        </div>
        <br><a href="/services" class="btn btn-blue">Все услуги →</a>
    </div>
    <div>
        <h2 class="section-title-green">📋 Задания</h2>
        <div class="service-grid">
            {% for task in tasks %}
                <div class="task-card" onclick="window.location='/task/{{ task.id }}'">
                    <h3>{{ task.title }}</h3>
                    <p style="color:#a0aec0;font-size:14px;">{{ task.category }}</p>
                    <p class="price">{{ task.price }} ₽</p>
                    <p class="client">👤 Заказчик: {{ task.client.username }}</p>
                    <p class="expires">⏳ До: {{ task.expires_at.strftime('%d.%m.%Y') }}</p>
                    <a href="/take-task/{{ task.id }}" class="btn">Взять задание</a>
                    <a href="/task/{{ task.id }}" class="btn btn-blue" style="margin-left:10px;">Подробнее</a>
                </div>
            {% else %}<p style="color:#a0aec0;">Заданий пока нет.</p>{% endfor %}
        </div>
        <br><a href="/tasks" class="btn">Все задания →</a>
    </div>
</div>
{% endblock %}
''',
    'services.html': '''
{% extends "base.html" %}
{% block content %}
<h2 style="color:#22c55e;">🛒 {{ title }}</h2>
<div class="service-grid">
    {% for service in services %}
        <div class="service-card" onclick="window.location='/service/{{ service.id }}'">
            <h3>{{ service.title }}</h3>
            <p>{{ service.description[:100] }}{% if service.description|length > 100 %}...{% endif %}</p>
            <p style="color:#a0aec0;font-size:14px;">{{ service.category }}</p>
            <p class="price">{{ service.price }} ₽</p>
            <p class="seller">👤 {{ service.seller.username }}</p>
            <p class="expires">⏳ До: {{ service.expires_at.strftime('%d.%m.%Y %H:%M') }}</p>
            <a href="/buy-service/{{ service.id }}" class="btn">Купить</a>
            <a href="/service/{{ service.id }}" class="btn btn-blue" style="margin-left:10px;">Подробнее</a>
        </div>
    {% else %}<p style="color:#a0aec0;">Услуг не найдено</p>{% endfor %}
</div>
{% endblock %}
''',
    'tasks.html': '''
{% extends "base.html" %}
{% block content %}
<h2 style="color:#f59e0b;">📋 {{ title }}</h2>
<div class="service-grid">
    {% for task in tasks %}
        <div class="task-card" onclick="window.location='/task/{{ task.id }}'">
            <h3>{{ task.title }}</h3>
            <p>{{ task.description[:100] }}{% if task.description|length > 100 %}...{% endif %}</p>
            <p style="color:#a0aec0;font-size:14px;">{{ task.category }}</p>
            <p class="price">{{ task.price }} ₽</p>
            <p class="client">👤 Заказчик: {{ task.client.username }}</p>
            <p class="expires">⏳ До: {{ task.expires_at.strftime('%d.%m.%Y %H:%M') }}</p>
            <a href="/take-task/{{ task.id }}" class="btn">Взять задание</a>
            <a href="/task/{{ task.id }}" class="btn btn-blue" style="margin-left:10px;">Подробнее</a>
        </div>
    {% else %}<p style="color:#a0aec0;">Заданий не найдено</p>{% endfor %}
</div>
{% endblock %}
''',
    'service_detail.html': '''
{% extends "base.html" %}
{% block content %}
<div class="service-detail-card">
    <h1>{{ service.title }}</h1>
    <p style="color:#a0aec0;font-size:16px;">📌 {{ service.category }}</p>
    <p class="price">{{ service.price }} ₽</p>
    <div class="description">{{ service.description }}</div>
    <div>
        <p>👤 Продавец: <a href="/profile" style="color:#22c55e;">{{ service.seller.username }}</a></p>
        <p>📅 Создано: {{ service.created_at.strftime('%d.%m.%Y %H:%M') }}</p>
        <p>⏳ Истекает: {{ service.expires_at.strftime('%d.%m.%Y %H:%M') }}</p>
    </div>
    <br>
    <a href="/buy-service/{{ service.id }}" class="btn">💳 Купить</a>
    {% if user and user.is_developer %}
        <form method="post" action="/developer/delete-service/{{ service.id }}" style="display:inline;margin-left:10px;">
            <button type="submit" class="btn btn-red" onclick="return confirm('Удалить услугу?')">🗑️ Удалить (админ)</button>
        </form>
    {% endif %}
</div>
{% endblock %}
''',
    'task_detail.html': '''
{% extends "base.html" %}
{% block content %}
<div class="task-detail-card">
    <h1>{{ task.title }}</h1>
    <p style="color:#a0aec0;font-size:16px;">📌 {{ task.category }}</p>
    <p class="price">{{ task.price }} ₽</p>
    <div class="description">{{ task.description }}</div>
    <div>
        <p>👤 Заказчик: <a href="/profile" style="color:#f59e0b;">{{ task.client.username }}</a></p>
        <p>📅 Создано: {{ task.created_at.strftime('%d.%m.%Y %H:%M') }}</p>
        <p>⏳ До: {{ task.expires_at.strftime('%d.%m.%Y %H:%M') }}</p>
        <p>📊 Статус: <span class="status-{{ task.status }}">{{ task.status }}</span></p>
        {% if task.executor %}
            <p>👤 Исполнитель: {{ task.executor.username }}</p>
        {% endif %}
    </div>
    <br>
    {% if task.status == 'open' %}
        <a href="/take-task/{{ task.id }}" class="btn">✅ Взять задание</a>
    {% elif task.status == 'in_progress' and session.user_id == task.executor_id %}
        <a href="/task-order/{{ task.id }}" class="btn btn-blue">📦 Перейти к заданию</a>
    {% elif task.status == 'in_progress' and session.user_id == task.client_id %}
        <a href="/task-order/{{ task.id }}" class="btn btn-blue">📦 Перейти к заданию</a>
    {% elif task.status == 'completed' %}
        <span class="btn" style="cursor:default;">✅ Задание выполнено</span>
    {% endif %}
    {% if user and user.is_developer %}
        <form method="post" action="/developer/delete-task/{{ task.id }}" style="display:inline;margin-left:10px;">
            <button type="submit" class="btn btn-red" onclick="return confirm('Удалить задание?')">🗑️ Удалить (админ)</button>
        </form>
    {% endif %}
</div>
{% endblock %}
''',
    'create_service.html': '''
{% extends "base.html" %}
{% block content %}
<div class="form-container">
    <h2>🚀 Создать услугу</h2>
    <form method="post">
        <input type="text" name="title" placeholder="Название услуги" required>
        <textarea name="description" placeholder="Подробное описание" required></textarea>
        <input type="number" name="price" step="0.01" placeholder="Цена в ₽" required>
        <input type="text" name="category" placeholder="Категория" required>
        <h4 style="color:#22c55e;margin:20px 0 10px;">⏳ Срок действия</h4>
        <div class="form-row">
            <div class="form-group"><label>Дни</label><input type="number" name="days" value="7" min="0"></div>
            <div class="form-group"><label>Часы</label><input type="number" name="hours" value="0" min="0" max="23"></div>
            <div class="form-group"><label>Минуты</label><input type="number" name="minutes" value="0" min="0" max="59"></div>
        </div>
        <button type="submit">📢 Опубликовать</button>
    </form>
</div>
{% endblock %}
''',
    'create_task.html': '''
{% extends "base.html" %}
{% block content %}
<div class="form-container">
    <h2>📋 Создать задание</h2>
    <form method="post">
        <input type="text" name="title" placeholder="Название задания" required>
        <textarea name="description" placeholder="Что нужно сделать? Подробное описание" required></textarea>
        <input type="number" name="price" step="0.01" placeholder="Бюджет в ₽" required>
        <input type="text" name="category" placeholder="Категория" required>
        <h4 style="color:#f59e0b;margin:20px 0 10px;">⏳ Срок выполнения</h4>
        <div class="form-row">
            <div class="form-group"><label>Дни</label><input type="number" name="days" value="3" min="0"></div>
            <div class="form-group"><label>Часы</label><input type="number" name="hours" value="0" min="0" max="23"></div>
            <div class="form-group"><label>Минуты</label><input type="number" name="minutes" value="0" min="0" max="59"></div>
        </div>
        <button type="submit">📢 Опубликовать задание</button>
    </form>
</div>
{% endblock %}
''',
    'service_payment.html': '''
{% extends "base.html" %}
{% block content %}
<div style="max-width:600px;margin:0 auto;background:#14181f;border:1px solid #2a313c;border-radius:16px;padding:40px;">
    <h2 style="color:#22c55e;">💳 Оплата услуги</h2>
    <div class="payment-info">
        <p class="label">📌 Услуга</p>
        <p class="value">{{ order.service.title }}</p>
        <p class="label">💰 Сумма</p>
        <p class="value" style="color:#22c55e;font-size:24px;">{{ "%.2f"|format(order.amount) }} ₽</p>
        <p class="label">📊 Комиссия (10%)</p>
        <p class="value">{{ "%.2f"|format(order.commission) }} ₽</p>
        <p class="label">👤 Продавец</p>
        <p class="value">{{ seller.full_name or seller.username }}</p>
    </div>
    <div style="background:#1a1f2a;padding:20px;border-radius:12px;margin:20px 0;border:1px solid #22c55e;">
        <h3 style="color:#22c55e;text-align:center;">💳 Реквизиты продавца</h3>
        <p style="text-align:center;font-size:20px;font-weight:700;margin:15px 0;">{{ seller.card_number or 'Не указаны' }}</p>
        <p style="text-align:center;color:#a0aec0;">{{ seller.bank_name or 'Банк не указан' }}</p>
        <p style="text-align:center;color:#a0aec0;">👤 {{ seller.full_name or seller.username }}</p>
    </div>
    <form method="post" action="/confirm-service-payment/{{ order.id }}">
        <button type="submit" class="btn" style="width:100%;">✅ Я оплатил</button>
    </form>
</div>
{% endblock %}
''',
    'service_order_detail.html': '''
{% extends "base.html" %}
{% block content %}
<div style="max-width:800px;margin:0 auto;">
    <h2 style="color:#22c55e;">📦 Заказ #{{ order.id }}</h2>
    <div style="background:#14181f;border:1px solid #2a313c;border-radius:12px;padding:20px;margin-bottom:20px;">
        <p><strong>Услуга:</strong> {{ order.service.title }}</p>
        <p><strong>Сумма:</strong> {{ "%.2f"|format(order.amount) }} ₽</p>
        <p><strong>Статус:</strong> <span class="status-{{ order.status }}">{{ order.status }}</span></p>
        {% if order.buyer_id == session.user_id and order.status == 'pending' %}
            <a href="/service-payment/{{ order.id }}" class="btn">💳 Оплатить</a>
        {% endif %}
        {% if order.seller_id == session.user_id and order.status == 'paid' %}
            <form method="post" action="/complete-service-order/{{ order.id }}" style="margin-top:15px;">
                <button type="submit" class="btn">✅ Завершить заказ</button>
            </form>
        {% endif %}
    </div>
    <div style="background:#14181f;border:1px solid #2a313c;border-radius:12px;padding:20px;">
        <h3 style="color:#22c55e;">💬 Чат</h3>
        <div class="chat-box" id="chatBox">
            {% for msg in messages %}
                <div class="message">
                    <span class="sender">{{ msg.sender.username }}</span>
                    <span class="time">{{ msg.created_at.strftime('%Y-%m-%d %H:%M') }}</span>
                    <div class="text">{{ msg.text }}</div>
                </div>
            {% endfor %}
        </div>
        <form id="messageForm" style="display:flex;gap:10px;">
            <input type="text" id="messageInput" placeholder="Сообщение..." style="flex:1;padding:12px;background:#0b0e14;border:1px solid #2a313c;border-radius:8px;color:#e4e6eb;">
            <button type="submit" class="btn">Отправить</button>
        </form>
    </div>
</div>
<script>
const orderId = {{ order.id }};
const orderType = 'service';
const chatBox = document.getElementById('chatBox');

document.getElementById('messageForm').addEventListener('submit', function(e) {
    e.preventDefault();
    const input = document.getElementById('messageInput');
    const text = input.value.trim();
    if (!text) return;
    
    fetch('/send-message', {
        method: 'POST',
        headers: {'Content-Type': 'application/x-www-form-urlencoded'},
        body: `order_id=${orderId}&order_type=${orderType}&text=${encodeURIComponent(text)}`
    })
    .then(r => r.json())
    .then(data => {
        if (data.error) { alert(data.error); return; }
        input.value = '';
        const msg = document.createElement('div');
        msg.className = 'message';
        msg.innerHTML = `<span class="sender">{{ session.username }}</span><span class="time">${data.created_at}</span><div class="text">${data.text}</div>`;
        chatBox.appendChild(msg);
        chatBox.scrollTop = chatBox.scrollHeight;
    });
});

setInterval(() => {
    fetch(`/api/messages/${orderType}/${orderId}`)
        .then(r => r.json())
        .then(messages => {
            const currentCount = chatBox.children.length;
            if (messages.length > currentCount) {
                chatBox.innerHTML = messages.map(m => 
                    `<div class="message"><span class="sender">${m.sender}</span><span class="time">${m.created_at}</span><div class="text">${m.text}</div></div>`
                ).join('');
                chatBox.scrollTop = chatBox.scrollHeight;
            }
        });
}, 3000);
</script>
{% endblock %}
''',
    'task_order_detail.html': '''
{% extends "base.html" %}
{% block content %}
<div style="max-width:800px;margin:0 auto;">
    <h2 style="color:#f59e0b;">📋 Задание #{{ task.id }}</h2>
    <div style="background:#14181f;border:1px solid #2a313c;border-radius:12px;padding:20px;margin-bottom:20px;">
        <p><strong>Название:</strong> {{ task.title }}</p>
        <p><strong>Бюджет:</strong> {{ "%.2f"|format(task.price) }} ₽</p>
        <p><strong>Статус:</strong> <span class="status-{{ task.status }}">{{ task.status }}</span></p>
        <p><strong>Заказчик:</strong> {{ task.client.username }}</p>
        {% if task.executor %}
            <p><strong>Исполнитель:</strong> {{ task.executor.username }}</p>
        {% endif %}
        {% if task.client_id == session.user_id and task.status == 'in_progress' %}
            <form method="post" action="/complete-task/{{ task.id }}" style="margin-top:15px;">
                <button type="submit" class="btn">✅ Завершить задание</button>
            </form>
            <form method="post" action="/cancel-task/{{ task.id }}" style="margin-top:10px;">
                <button type="submit" class="btn btn-red">❌ Отменить задание</button>
            </form>
        {% endif %}
        {% if task.executor_id == session.user_id and task.status == 'in_progress' %}
            <form method="post" action="/cancel-task-executor/{{ task.id }}" style="margin-top:15px;">
                <button type="submit" class="btn btn-red">❌ Отказаться от задания</button>
            </form>
        {% endif %}
    </div>
    <div style="background:#14181f;border:1px solid #2a313c;border-radius:12px;padding:20px;">
        <h3 style="color:#f59e0b;">💬 Чат</h3>
        <div class="chat-box" id="chatBox">
            {% for msg in messages %}
                <div class="message">
                    <span class="sender">{{ msg.sender.username }}</span>
                    <span class="time">{{ msg.created_at.strftime('%Y-%m-%d %H:%M') }}</span>
                    <div class="text">{{ msg.text }}</div>
                </div>
            {% endfor %}
        </div>
        <form id="messageForm" style="display:flex;gap:10px;">
            <input type="text" id="messageInput" placeholder="Сообщение..." style="flex:1;padding:12px;background:#0b0e14;border:1px solid #2a313c;border-radius:8px;color:#e4e6eb;">
            <button type="submit" class="btn">Отправить</button>
        </form>
    </div>
</div>
<script>
const orderId = {{ task.id }};
const orderType = 'task';
const chatBox = document.getElementById('chatBox');

document.getElementById('messageForm').addEventListener('submit', function(e) {
    e.preventDefault();
    const input = document.getElementById('messageInput');
    const text = input.value.trim();
    if (!text) return;
    
    fetch('/send-message', {
        method: 'POST',
        headers: {'Content-Type': 'application/x-www-form-urlencoded'},
        body: `order_id=${orderId}&order_type=${orderType}&text=${encodeURIComponent(text)}`
    })
    .then(r => r.json())
    .then(data => {
        if (data.error) { alert(data.error); return; }
        input.value = '';
        const msg = document.createElement('div');
        msg.className = 'message';
        msg.innerHTML = `<span class="sender">{{ session.username }}</span><span class="time">${data.created_at}</span><div class="text">${data.text}</div>`;
        chatBox.appendChild(msg);
        chatBox.scrollTop = chatBox.scrollHeight;
    });
});

setInterval(() => {
    fetch(`/api/messages/${orderType}/${orderId}`)
        .then(r => r.json())
        .then(messages => {
            const currentCount = chatBox.children.length;
            if (messages.length > currentCount) {
                chatBox.innerHTML = messages.map(m => 
                    `<div class="message"><span class="sender">${m.sender}</span><span class="time">${m.created_at}</span><div class="text">${m.text}</div></div>`
                ).join('');
                chatBox.scrollTop = chatBox.scrollHeight;
            }
        });
}, 3000);
</script>
{% endblock %}
''',
    'register.html': '''
{% extends "base.html" %}
{% block content %}
<div class="form-container">
    <h2>📝 Регистрация</h2>
    <form method="post">
        <input type="text" name="username" placeholder="Логин" required>
        <input type="email" name="email" placeholder="Email" required>
        <input type="password" name="password" placeholder="Пароль" required>
        <input type="text" name="full_name" placeholder="Полное имя">
        <input type="text" name="phone" placeholder="Телефон">
        <button type="submit">Зарегистрироваться</button>
    </form>
    <p style="text-align:center;margin-top:20px;color:#a0aec0;">Уже есть аккаунт? <a href="/login" style="color:#22c55e;">Войти</a></p>
</div>
{% endblock %}
''',
    'login.html': '''
{% extends "base.html" %}
{% block content %}
<div class="form-container">
    <h2>🔐 Вход</h2>
    <form method="post">
        <input type="text" name="username" placeholder="Логин" required>
        <input type="password" name="password" placeholder="Пароль" required>
        <button type="submit">Войти</button>
    </form>
    <p style="text-align:center;margin-top:20px;color:#a0aec0;">Нет аккаунта? <a href="/register" style="color:#22c55e;">Зарегистрироваться</a></p>
</div>
{% endblock %}
''',
    'profile.html': '''
{% extends "base.html" %}
{% block content %}
<div style="max-width:900px;margin:0 auto;">
    <h2 style="color:#22c55e;">👤 Профиль {{ user.username }}
        {% if user.is_developer %}<span class="developer-badge">🔧 Разработчик</span>{% endif %}
        {% if user.is_blocked %}<span class="blocked-badge">🚫 Заблокирован</span>{% endif %}
    </h2>
    
    <div class="profile-section">
        <h3 style="color:#22c55e;">📋 Личные данные</h3>
        <form method="post">
            <input type="text" name="full_name" value="{{ user.full_name or '' }}" placeholder="Полное имя" style="width:100%;padding:10px;margin-bottom:10px;background:#0b0e14;border:1px solid #2a313c;border-radius:8px;color:#e4e6eb;">
            <input type="text" name="phone" value="{{ user.phone or '' }}" placeholder="Телефон" style="width:100%;padding:10px;margin-bottom:10px;background:#0b0e14;border:1px solid #2a313c;border-radius:8px;color:#e4e6eb;">
            <h4 style="color:#22c55e;margin:15px 0 10px;">💳 Реквизиты</h4>
            <input type="text" name="card_number" value="{{ user.card_number or '' }}" placeholder="Номер карты" style="width:100%;padding:10px;margin-bottom:10px;background:#0b0e14;border:1px solid #2a313c;border-radius:8px;color:#e4e6eb;">
            <input type="text" name="bank_name" value="{{ user.bank_name or '' }}" placeholder="Название банка" style="width:100%;padding:10px;margin-bottom:10px;background:#0b0e14;border:1px solid #2a313c;border-radius:8px;color:#e4e6eb;">
            <button type="submit" class="btn">💾 Сохранить</button>
        </form>
    </div>
    
    <div class="profile-section">
        <h3 style="color:#22c55e;">📊 Статистика</h3>
        <div class="stat-grid">
            <div class="stat-item"><div class="stat-value">{{ total_bought }}</div><div class="stat-label">🛒 Куплено услуг</div></div>
            <div class="stat-item"><div class="stat-value">{{ "%.2f"|format(total_spent) }} ₽</div><div class="stat-label">💰 Потрачено</div></div>
            <div class="stat-item"><div class="stat-value">{{ total_sold }}</div><div class="stat-label">📦 Продано услуг</div></div>
            <div class="stat-item"><div class="stat-value">{{ "%.2f"|format(total_earned) }} ₽</div><div class="stat-label">💵 Заработано</div></div>
            <div class="stat-item"><div class="stat-value">{{ total_tasks_client }}</div><div class="stat-label">📋 Создано заданий</div></div>
            <div class="stat-item"><div class="stat-value">{{ total_tasks_executor }}</div><div class="stat-label">✅ Взято заданий</div></div>
            <div class="stat-item"><div class="stat-value">{{ active_services }}</div><div class="stat-label">📌 Активных услуг</div></div>
        </div>
    </div>
    
    {% if user.is_developer %}
    <div class="profile-section" style="border:2px solid #8b5cf6;">
        <h3 style="color:#8b5cf6;">🔧 Панель разработчика</h3>
        <h4 style="color:#22c55e;margin-top:15px;">➕ Добавить разработчика</h4>
        <form method="post" action="/developer/add" style="display:flex;gap:10px;">
            <input type="text" name="username" placeholder="Логин" style="flex:1;padding:10px;background:#0b0e14;border:1px solid #2a313c;border-radius:8px;color:#e4e6eb;">
            <button type="submit" class="btn btn-purple">Назначить</button>
        </form>
        <h4 style="color:#22c55e;margin-top:15px;">❌ Лишить прав</h4>
        <form method="post" action="/developer/remove" style="display:flex;gap:10px;">
            <input type="text" name="username" placeholder="Логин" style="flex:1;padding:10px;background:#0b0e14;border:1px solid #2a313c;border-radius:8px;color:#e4e6eb;">
            <button type="submit" class="btn btn-red">Лишить прав</button>
        </form>
        <h4 style="color:#22c55e;margin-top:15px;">🚫 Блокировка</h4>
        <form method="post" action="/developer/block" style="display:flex;gap:10px;">
            <input type="text" name="username" placeholder="Логин" style="flex:1;padding:10px;background:#0b0e14;border:1px solid #2a313c;border-radius:8px;color:#e4e6eb;">
            <button type="submit" class="btn btn-red">Заблокировать</button>
        </form>
        <h4 style="color:#22c55e;margin-top:15px;">🔓 Разблокировка</h4>
        <form method="post" action="/developer/unblock" style="display:flex;gap:10px;">
            <input type="text" name="username" placeholder="Логин" style="flex:1;padding:10px;background:#0b0e14;border:1px solid #2a313c;border-radius:8px;color:#e4e6eb;">
            <button type="submit" class="btn">Разблокировать</button>
        </form>
        <h4 style="color:#22c55e;margin-top:15px;">👥 Пользователи</h4>
        <div style="max-height:300px;overflow-y:auto;">
            {% for u in all_users %}
                <div style="display:flex;justify-content:space-between;padding:8px;background:#0b0e14;border-radius:8px;margin-bottom:5px;align-items:center;">
                    <span>{{ u.username }}{% if u.is_developer %} 🔧{% endif %}{% if u.is_blocked %} 🚫{% endif %}</span>
                    <span style="color:#a0aec0;font-size:12px;">{{ u.full_name or '' }}</span>
                </div>
            {% endfor %}
        </div>
        <h4 style="color:#22c55e;margin-top:15px;">💰 Баланс платформы</h4>
        <p style="font-size:24px;font-weight:700;color:#22c55e;">{{ "%.2f"|format(admin_balance.total_commission) }} ₽</p>
        <p style="color:#a0aec0;">💳 Карта: 5536092301335542</p>
    </div>
    {% endif %}
    
    <div class="profile-section">
        <h3 style="color:#22c55e;">🛒 Покупки услуг</h3>
        {% for order in service_orders_buyer %}
            <div style="padding:10px;background:#0b0e14;border-radius:8px;margin-bottom:8px;border-left:3px solid #22c55e;">
                {{ order.service.title }} — {{ "%.2f"|format(order.amount) }} ₽ <span class="status-{{ order.status }}">({{ order.status }})</span>
                <a href="/service-order/{{ order.id }}" class="btn" style="padding:4px 12px;font-size:12px;float:right;">Подробнее</a>
            </div>
        {% else %}<p style="color:#a0aec0;">Нет покупок</p>{% endfor %}
    </div>
    
    <div class="profile-section">
        <h3 style="color:#22c55e;">📦 Продажи услуг</h3>
        {% for order in service_orders_seller %}
            <div style="padding:10px;background:#0b0e14;border-radius:8px;margin-bottom:8px;border-left:3px solid #22c55e;">
                {{ order.service.title }} — {{ "%.2f"|format(order.amount) }} ₽ <span class="status-{{ order.status }}">({{ order.status }})</span>
                <a href="/service-order/{{ order.id }}" class="btn" style="padding:4px 12px;font-size:12px;float:right;">Подробнее</a>
            </div>
        {% else %}<p style="color:#a0aec0;">Нет продаж</p>{% endfor %}
    </div>
    
    <div class="profile-section">
        <h3 style="color:#f59e0b;">📋 Мои задания (как заказчик)</h3>
        {% for task in task_orders_client %}
            <div style="padding:10px;background:#0b0e14;border-radius:8px;margin-bottom:8px;border-left:3px solid #f59e0b;">
                {{ task.title }} — {{ "%.2f"|format(task.price) }} ₽ <span class="status-{{ task.status }}">({{ task.status }})</span>
                <a href="/task-order/{{ task.id }}" class="btn" style="padding:4px 12px;font-size:12px;float:right;">Подробнее</a>
            </div>
        {% else %}<p style="color:#a0aec0;">Нет заданий</p>{% endfor %}
    </div>
    
    <div class="profile-section">
        <h3 style="color:#f59e0b;">✅ Задания в работе (как исполнитель)</h3>
        {% for task in task_orders_executor %}
            <div style="padding:10px;background:#0b0e14;border-radius:8px;margin-bottom:8px;border-left:3px solid #f59e0b;">
                {{ task.title }} — {{ "%.2f"|format(task.price) }} ₽ <span class="status-{{ task.status }}">({{ task.status }})</span>
                <a href="/task-order/{{ task.id }}" class="btn" style="padding:4px 12px;font-size:12px;float:right;">Подробнее</a>
            </div>
        {% else %}<p style="color:#a0aec0;">Нет заданий в работе</p>{% endfor %}
    </div>
</div>
{% endblock %}
'''
}

for filename, content in templates.items():
    with open(f'templates/{filename}', 'w', encoding='utf-8') as f:
        f.write(content)

if __name__ == '__main__':
    print("=" * 60)
    print("🌱 LightFree запущен!")
    print("👤 Логин разработчика: razrab")
    print("🔑 Пароль: Vadim06.04.2012")
    print("🔒 Безопасные сделки | Чат | Комиссия 10%")
    print("🛒 Раздел 'Услуги' - продажа готовых услуг")
    print("📋 Раздел 'Задания' - биржа фриланса")
    print("💾 Данные сохраняются при перезапуске")
    print("🌐 http://127.0.0.1:5000")
    print("=" * 60)
    app.run(debug=True, host='0.0.0.0', port=5000)
