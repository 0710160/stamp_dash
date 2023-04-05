import os
from datetime import datetime, timedelta
from pathlib import Path

from decimal import Decimal
from dotenv import load_dotenv
from flask import Flask, flash, redirect, render_template, request, url_for
from flask_login import (LoginManager, UserMixin, current_user, login_required,
                         login_user, logout_user)
from flask_mail import Mail, Message
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import ForeignKey, desc, func
from sqlalchemy.orm import relationship
from werkzeug.exceptions import HTTPException
from werkzeug.security import check_password_hash, generate_password_hash

from telegram_bot import TelegramBot

load_dotenv()
SECRET_KEY = os.getenv('SECRET_KEY')
APP_PASSWORD = os.getenv('APP_PASSWORD')
MY_EMAIL = os.getenv('MY_EMAIL')
STAMP_EMAIL = os.getenv('STAMP_EMAIL')

# UPLOAD_FOLDER = 'static/uploads/'
UPLOAD_FOLDER = '/home/0710160/mysite/static/uploads'
ALLOWED_EXTENSIONS = set(['webp', 'png', 'jpg', 'jpeg'])

app = Flask(__name__)
app.config['SECRET_KEY'] = SECRET_KEY
# app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv("DATABASE_URL2")
app.config['SQLALCHEMY_DATABASE_URI'] = ("sqlite:///production_schedule.sqlite3")
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Flask login manager
login_manager = LoginManager()
login_manager.init_app(app)

# Flask Mail manager
app.config['MAIL_SERVER']='smtp.fastmail.com'
app.config['MAIL_PORT'] = 465
app.config['MAIL_USERNAME'] = MY_EMAIL
app.config['MAIL_PASSWORD'] = APP_PASSWORD
app.config['MAIL_USE_SSL'] = True
mail = Mail(app)


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(user_id)


class Jobs(db.Model):
    ''' DB for the job information '''
    __tablename__= "jobs"
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    job_no = db.Column(db.String, nullable=False)
    job_name = db.Column(db.String(250), nullable=False)
    due_date = db.Column(db.Date)
    job_value = db.Column(db.Integer)
    plates_made = db.Column(db.Boolean, default=False) #unused
    scheduled = db.Column(db.Integer) #don't really know what this one does
    completed = db.Column(db.Boolean, default=False)
    status = db.Column(db.String)
    notes = db.Column(db.String)
    img_name = db.Column(db.String(250))
    quantity = db.Column(db.Integer)
    logs = relationship("Log", back_populates="jobs")
    materials = db.Column(db.String) # format 000; 0=cartons, 1=outwork, 2=unused


class User(UserMixin, db.Model):
    ''' DB for the user information '''
    __tablename__ = "user"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(250))
    password = db.Column(db.String(100))
    rights = db.Column(db.Integer, default=0)  # 0 is no access, 1 is read-only, 5 is admin
    active_job = db.Column(db.String(100))
    department = db.Column(db.String(100))
    #email_preferences = db.Column(db.String)


class Log(db.Model):
    ''' DB for user action logs '''
    __tablename__ = "log"
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime)
    action = db.Column(db.String(100))
    job_no = db.Column(db.String, ForeignKey("jobs.job_no"))
    jobs = relationship("Jobs", back_populates="logs")


class Timesheet(db.Model):
    ''' DB for user timesheets '''
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime)
    user = db.Column(db.String(100))
    job_no = db.Column(db.String)
    length = db.Column(db.Float, default=0)


#db.create_all()


def auth(user, action, job, name):
    '''
    Function to check if user is authorized to perform an action.
        5 = Admin (all rights)
        4 = Edit Quotes & Jobs
        3 = Add Quotes & Jobs
        2 = Unused
        1 = Read Only
        0 = No Access, Admin Confirmation Required
    Logs actions to log.db
    '''
    auth_user = User.query.get(user)
    if action.startswith("accessed") and auth_user.name == "mattt":
        pass
    else:
        accessed_time = datetime.now() + timedelta(hours=10)
        log_action = Log(timestamp=accessed_time, job_no=job, action=f"User {auth_user.name} {action} {job} {name}")
        check_log = Log.query.order_by(Log.id.desc()).first()
        if check_log.action == log_action.action:
            pass
        else:
            db.session.add(log_action)
            db.session.commit()
    return auth_user.rights


def mail_manager(recipients, body):
    msg = Message('Notification from Stamp Production Viewer', sender=STAMP_EMAIL, recipients=recipients)
    for recipient in recipients:
        full_body = body + f'\n\nThis message was sent automatically from https://www.jobslist.scolour.co.nz/ To opt out of future emails, reply to this email with UNSUBSCRIBE as the subject.'
        msg.body=full_body
        mail.send(msg)
    return "Sent"


def auth_user_min(user):
    auth_user = User.query.get(user)
    return auth_user.rights


def time_adjusted():
    # Adds 10 hours to PythonAnywhere system time to adjust for timezone
    nz_time = datetime.now() + timedelta(hours=10)
    return nz_time.strftime('%d/%m/%Y')


def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


# Changes date display with Jinja templating
@app.template_filter()
def datefilter(value, format='%d/%m/%y'):
    return value.strftime(format)


app.jinja_env.filters['datefilter'] = datefilter


@app.route("/")
@login_required
def home():
    if auth(user=current_user.id, action="accessed dashboard", job='', name='') >= 1:
        stamp_jobs = Jobs.query.order_by(Jobs.due_date, Jobs.job_name).filter(Jobs.scheduled == 1, Jobs.completed == False)
        outstanding_quotes = Jobs.query.order_by(Jobs.due_date).filter(Jobs.status == "submitted")
        to_do_quotes = Jobs.query.order_by(Jobs.due_date).filter(Jobs.status == "todo")
        due_late_jobs = stamp_jobs.filter(Jobs.due_date < (datetime.now() + timedelta(hours=10)))
        return render_template("dashboard.html",
                               all_jobs=stamp_jobs,
                               outstanding_quotes=outstanding_quotes,
                               to_do_quotes=to_do_quotes,
                               due_late_jobs=due_late_jobs,
                               all=False,
                               logged_in=current_user.is_authenticated)
    else:
        flash(f"Please register a user to view this content.\nIf you've already signed up, please wait for the administrator to approve your user.")
        return redirect(url_for('new_user'))


@app.route("/all")
@login_required
def all():
    if auth(user=current_user.id, action="accessed dashboard", job='', name='') >= 1:
        stamp_jobs = Jobs.query.order_by(Jobs.job_no.desc()).filter(Jobs.scheduled == 1)
        return render_template("all.html",
                               all_jobs=stamp_jobs,
                               logged_in=current_user.is_authenticated)
    else:
        flash(f"Please register a user to view this content.\nIf you've already signed up, please wait for the administrator to approve your user.")
        return redirect(url_for('new_user'))


@app.route("/add_quote", methods=["GET", "POST"])
@login_required
def add_quote():
    last_job = Jobs.query.order_by(Jobs.id.desc()).first()
    last_id_plus_one = last_job.id + 1
    if auth(user=current_user.id, action="added quote", job=last_id_plus_one, name='') >= 3:
        if request.method == "GET":
            return render_template("add_quote.html", logged_in=current_user.is_authenticated)
        if request.method == "POST":
            job_name = request.form["job_name"]
            due_date = request.form["due_date"]
            due_date = datetime.strptime(due_date, "%Y-%m-%d")
            notes = request.form["notes"]
            add_quote = Jobs(job_no=last_id_plus_one,
                           job_name=job_name,
                           due_date=due_date,
                           status="todo",
                           notes=notes,
                           img_name="NULL")
            db.session.add(add_quote)
            db.session.commit()
            return redirect(url_for('home', logged_in=current_user.is_authenticated))
    else:
        flash("You are not authorized to perform this action.")
        return redirect(url_for('home', logged_in=current_user.is_authenticated))


@app.route("/complete_quote/<job_id>")
@login_required
def complete_quote(job_id):
    edit_job = Jobs.query.get(job_id)
    if auth(user=current_user.id, action="confirmed quote", job=edit_job.job_no, name=edit_job.job_name) >= 3:
            edit_job.status = "submitted"
            edit_job.due_date = datetime.now() + timedelta(hours=10)
            db.session.commit()

    else:
        flash("You are not authorized to perform this action.")
    return redirect(request.referrer)


@app.route("/add_job/<job_id>", methods=["GET", "POST"])
@login_required
def add_job(job_id):
    new_job = Jobs.query.get(job_id)
    if auth(user=current_user.id, action="added job", job=new_job.job_no, name=new_job.job_name) >= 3:
        if request.method == "GET":
            return render_template("add_job.html",
                job_name=new_job.job_name,
                materials=new_job.materials,
                notes=new_job.notes,
                logged_in=current_user.is_authenticated)
        if request.method == "POST":
            job_no = request.form["job_no"]
            job_value = request.form["job_value"]
            job_qty = request.form["job_qty"]
            due_date = (request.form["due_date"])
            due_date = datetime.strptime(due_date, "%Y-%m-%d")
            notes = request.form["notes"]
            materials = list("000")
            try:
                if request.form.getlist("cartons")[0]:
                    materials[0] = '1'
                if request.form.getlist("outwork")[0]:
                    materials[1] = '1'
                if request.form.getlist("other")[0]:
                    materials[2] = '1'
            except IndexError:
                pass
            new_job.materials = "".join(materials)
            filename = f'job{job_no}'
            blank_img = open(os.path.join(app.config['UPLOAD_FOLDER'], filename), "w")
            blank_img.close()
            current_date = time_adjusted()
            status = f'Entered {current_date}'
            new_job.job_no=job_no
            new_job.job_value=job_value
            new_job.quantity=job_qty
            new_job.due_date=due_date
            new_job.notes=notes
            new_job.scheduled=1
            new_job.status=status
            new_job.img_name=f'job{job_no}'
            mail_manager(recipients=['Ricky.Howes@brebnerprint.co.nz'], body=f'Stamp quote \'{new_job.job_name}\' has been accepted by the client, with a value of ${new_job.job_value}, and a target dispatch date of {new_job.due_date.strftime("%d/%m/%Y")}.')
            db.session.commit()
            return redirect(url_for('image_handler',
            job_id=job_id,
            logged_in=current_user.is_authenticated))
    else:
        flash("You are not authorized to perform this action.")
        return redirect(url_for('home', logged_in=current_user.is_authenticated))


@app.route("/edit/<job_id>", methods=["GET", "POST"])
@login_required
def edit(job_id):
    edit_job = Jobs.query.get(job_id)
    logs = Log.query.filter_by(job_no=edit_job.job_no).all()
    timesheet = Timesheet.query.filter_by(job_no=edit_job.job_no).all()
    hours = Timesheet.query.with_entities(func.sum(Timesheet.length)).filter_by(job_no=edit_job.job_no).first()
    if auth_user_min(user=current_user.id) >= 4:
        if request.method == "GET":
            filename = Path(os.path.join(app.config['UPLOAD_FOLDER'], edit_job.img_name))
            if filename.is_file():
                file_exists = True
            else:
                file_exists = False
            return render_template("edit.html",
                                   file_exists=file_exists,
                                   job=edit_job,
                                   log=logs,
                                   hours=hours,
                                   timesheet=timesheet,
                                   logged_in=current_user.is_authenticated)
        if request.method == "POST":
            current_date = time_adjusted()
            if request.form["new_due_date"] == "":
                pass
            else:
                auth(user=current_user.id, action="edited due date on job", job=edit_job.job_no, name=edit_job.job_name)
                new_due_date = request.form["new_due_date"]
                new_due_date = datetime.strptime(new_due_date, "%Y-%m-%d")
                edit_job.due_date = new_due_date
            if request.form["notes"] == "":
                pass
            elif request.form["notes"] == " ":
                edit_job.notes = None
            else:
                notes = request.form["notes"]
                auth(user=current_user.id, action=f"edited note: {notes} on job", job=edit_job.job_no, name=edit_job.job_name)
                edit_job.notes = notes
            if request.form["new_name"] == "":
                pass
            else:
                job_name = request.form["new_name"]
                auth(user=current_user.id, action="edited job name on job", job=edit_job.job_no, name=edit_job.job_name)
                edit_job.job_name = job_name
            if request.form["new_value"] == "":
                pass
            else:
                job_value = request.form["new_value"]
                auth(user=current_user.id, action="edited value on job", job=edit_job.job_no, name=edit_job.job_name)
                edit_job.job_value = job_value
            materials = list("000")
            try:
                if request.form.getlist("cartons")[0]:
                    materials[0] = '1'
                if request.form.getlist("outwork")[0]:
                    materials[1] = '1'
                if request.form.getlist("other")[0]:
                    materials[2] = '1'
            except IndexError:
                pass
            edit_job.materials = "".join(materials)
            if request.form["new_qty"] == "":
                pass
            else:
                job_qty = request.form["new_qty"]
                auth(user=current_user.id, action="edited quantity on job", job=edit_job.job_no, name=edit_job.job_name)
                edit_job.job_qty = job_qty
            if request.form['status'] == "curr":
                pass
            elif request.form['status'] == "proof":
                auth(user=current_user.id, action="marked on proof job", job=edit_job.job_no, name=edit_job.job_name)
                edit_job.status = f'On proof {current_date}'
            elif request.form['status'] == "approved":
                auth(user=current_user.id, action="marked proof approved on job", job=edit_job.job_no, name=edit_job.job_name)
                edit_job.status = f'Proof approved {current_date}'
                mail_manager(recipients=['Stacey.McCormack@brebnerprint.co.nz', 'tim.murphy@scolour.co.nz', 'matt.tobin@brebnerprint.co.nz'], body=f'Stamp job {edit_job.job_no} \'{edit_job.job_name}\' is approved to print, and has a target dispatch date of {edit_job.due_date.strftime("%d/%m/%Y")}.')
            elif request.form['status'] == "printed":
                auth(user=current_user.id, action="marked printed job", job=edit_job.job_no, name=edit_job.job_name)
                edit_job.status = f'Printed {current_date}'
            elif request.form['status'] == "finishing":
                auth(user=current_user.id, action="marked finishing job", job=edit_job.job_no, name=edit_job.job_name)
                edit_job.status = f'Finishing {current_date}'
            elif request.form['status'] == "check_pack":
                auth(user=current_user.id, action="marked check & pack job", job=edit_job.job_no, name=edit_job.job_name)
                edit_job.status = f'Checking & packing {current_date}'
            elif request.form['status'] == "dispatched":
                auth(user=current_user.id, action="marked dispatched job", job=edit_job.job_no, name=edit_job.job_name)
                edit_job.status = f'Dispatched {current_date}'
                mail_manager(recipients=['Stacey.McCormack@brebnerprint.co.nz'], body=f'Stamp job {edit_job.job_no} \'{edit_job.job_name}\' has been dispatched.')
            db.session.commit()
            return redirect(url_for('home', logged_in=current_user.is_authenticated))
    else:
        flash("You are not authorized to perform this action.")
        return redirect(url_for('home', logged_in=current_user.is_authenticated))


@app.route("/status/<job_id>")
@login_required
def status(job_id):
    edit_job = Jobs.query.get(job_id)
    # Cycles through job status
    if auth_user_min(user=current_user.id) >= 4:
        current_date = time_adjusted()
        if edit_job.status.startswith("Entered"):
            edit_job.status = f"On proof {current_date}"
            auth(user=current_user.id, action="marked on proof job", job=edit_job.job_no, name=edit_job.job_name)
        elif edit_job.status.startswith("On proof"):
            edit_job.status = f"Proof approved {current_date}"
            auth(user=current_user.id, action="marked proof approved on job", job=edit_job.job_no, name=edit_job.job_name)
            mail_manager(recipients=['Stacey.McCormack@brebnerprint.co.nz', 'tim.murphy@scolour.co.nz', 'matt.tobin@brebnerprint.co.nz'], body=f'Stamp job {edit_job.job_no} \'{edit_job.job_name}\' is approved to print, and has a target dispatch date of {edit_job.due_date.strftime("%d/%m/%Y")}.')
        elif edit_job.status.startswith("Proof approved"):
            auth(user=current_user.id, action="marked printed job", job=edit_job.job_no, name=edit_job.job_name)
            edit_job.status = f"Printed {current_date}"
        elif edit_job.status.startswith("Printed"):
            auth(user=current_user.id, action="marked finishing job", job=edit_job.job_no, name=edit_job.job_name)
            edit_job.status = f"Finishing {current_date}"
        elif edit_job.status.startswith("Finishing"):
            auth(user=current_user.id, action="marked check & pack job", job=edit_job.job_no, name=edit_job.job_name)
            edit_job.status = f"Check & pack {current_date}"
        elif edit_job.status.startswith("Check"):
            auth(user=current_user.id, action="marked dispatched job", job=edit_job.job_no, name=edit_job.job_name)
            edit_job.status = f"Dispatched {current_date}"
            mail_manager(recipients=['Stacey.McCormack@brebnerprint.co.nz'], body=f'Stamp job {edit_job.job_no} \'{edit_job.job_name}\' has been dispatched.')
        elif edit_job.status.startswith("Dispatched "):
            auth(user=current_user.id, action="marked delivered job", job=edit_job.job_no, name=edit_job.job_name)
            edit_job.status = f"Delivered {current_date}"
            edit_job.completed = True
            try:
                os.remove(os.path.join(app.config['UPLOAD_FOLDER'], edit_job.img_name))
            except(FileNotFoundError):
                pass
        else:
            edit_job.status = edit_job.status
        db.session.commit()
        return redirect(request.referrer)
    else:
        flash("You are not authorized to perform this action.")
        return redirect(url_for('home', logged_in=current_user.is_authenticated))


@app.route("/status_update")
@login_required
def status_update():
    if auth(user=current_user.id, action="accessed status update", job='', name='') >= 4:
        stamp_jobs = Jobs.query.order_by(Jobs.due_date).filter(Jobs.scheduled == 1, Jobs.completed == False)
        return render_template("status_update.html",
                               all_jobs=stamp_jobs,
                               logged_in=current_user.is_authenticated)
    else:
        flash("You are not authorized to perform this action.")
        return redirect(url_for('home'))


@app.route("/timesheet-clock", methods=["GET", "POST"])
@login_required
def timesheetclock():
    timesheet_users = User.query.filter(User.department == 'stamp')
    if request.method == "GET":
        return render_template('timesheet-clock.html',
                                users=timesheet_users,
                                logged_in=current_user.is_authenticated)
    if request.method == "POST":
        selected_users = request.form.getlist('select-users')
        for u in selected_users:
            uq = User.query.get(u)
            try:
                if uq.active_job: #closes off active timesheet entry per user
                    timesheet_entry = Timesheet.query.filter_by(user=uq.id).order_by(Timesheet.id.desc()).first()
                    hours_spent = datetime.now() - timesheet_entry.timestamp
                    timesheet_entry.length = round(Decimal(timesheet_entry.length + (hours_spent.total_seconds() / 3600)),2)
                    #TelegramBot.send_text(f'{uq.name} clocked off job {uq.active_job} at {datetime.now()} for a total of {hours_spent} hours.')
                    uq.active_job = ""
                    db.session.commit()
            except:
                pass
        return redirect(url_for('home', logged_in=current_user.is_authenticated))


@app.route("/timesheet-job/<job_id>", methods=["GET", "POST"])
@login_required
def timesheetjob(job_id):
    job = Jobs.query.get(job_id)
    timesheet_users = User.query.filter(User.department == 'stamp')
    if request.method == "GET":
        return render_template('timesheet-job.html',
                                job=job,
                                users=timesheet_users,
                                logged_in=current_user.is_authenticated)
    if request.method == "POST":
        selected_users = request.form.getlist('select-users')
        for u in selected_users:
            uq = User.query.get(u)
            if uq.active_job: #closes off active timesheet entry per user
                timesheet_entry = Timesheet.query.filter_by(user=uq.id).order_by(Timesheet.id.desc()).first()
                hours_spent = datetime.now() - timesheet_entry.timestamp
                timesheet_entry.length = round(Decimal(timesheet_entry.length + (hours_spent.total_seconds() / 3600)),2)
                db.session.commit()
                #TelegramBot.send_text(f'{uq.name} clocked off job {job.job_no} at {datetime.now()} for a total of {hours_spent} hours.')
            timesheet_entry = Timesheet(user=uq.id,
                                        timestamp=datetime.now(),
                                        job_no=job.job_no)
            #TelegramBot.send_text(f'{uq.name} started job {job.job_no} at {datetime.now()}')
            #TelegramBot.send_text(f'{datetime.now()} {timesheet_entry.timestamp}')
            db.session.add(timesheet_entry)
            uq.active_job = job.job_no
            db.session.commit()
        return redirect(url_for('home', logged_in=current_user.is_authenticated))


@app.route("/image_handler/<job_id>")
@login_required
def image_handler(job_id):
    job = Jobs.query.get(job_id)
    filename = os.path.join(app.config['UPLOAD_FOLDER'], job.img_name)
    filesize = os.path.getsize(filename)
    if filesize < 100:
        return redirect(url_for('upload_img',
                                job_id=job_id,
                                logged_in=current_user.is_authenticated))
    else:
        return redirect(url_for('image',
                                job_id=job.id,
                                logged_in=current_user.is_authenticated))


@app.route("/upload_img/<job_id>", methods=["GET", "POST"])
@login_required
def upload_img(job_id):
    job = Jobs.query.get(job_id)
    if auth(user=current_user.id, action="added image to job", job=job.job_no, name=job.job_name) >= 3:
        if request.method == 'GET':
            return render_template('upload_img.html',
                                   job=job,
                                   logged_in=current_user.is_authenticated)
        if request.method == 'POST':
            # check if the post request has the file part
            if 'file' not in request.files:
                flash('No file part')
                return redirect(request.url)
            file = request.files['file']
            # if user does not select a file, browser submits empty part without filename
            if file.filename == '':
                flash('No file selected for uploading')
                return redirect(request.url)
            if file and allowed_file(file.filename):
                filename = f'job{job.job_no}'
                job.img_name = filename
                db.session.commit()
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                # print('upload_image filename: ' + new_filename)
                return redirect(url_for('home',
                                        job_id=job_id,
                                        logged_in=current_user.is_authenticated))
    else:
        flash("You are not authorized to perform this action.")
        return redirect(url_for('home', logged_in=current_user.is_authenticated))


@app.route("/image/<job_id>")
@login_required
def image(job_id):
    job = Jobs.query.get(job_id)
    return render_template('image.html',
                            job=job,
                            logged_in=current_user.is_authenticated)


@app.route("/delete/<job_id>")
@login_required
def delete(job_id):
    # Removes a job from the database
    delete_job = Jobs.query.get(job_id)
    if auth(user=current_user.id, action="deleted quote/job", job=delete_job.job_no, name=delete_job.job_name) >= 4:
        try:
            os.remove(os.path.join(app.config['UPLOAD_FOLDER'], delete_job.img_name))
        except(FileNotFoundError):
            pass
        db.session.delete(delete_job)
        db.session.commit()
        return redirect(url_for('home'))
    else:
        flash("You are not authorized to perform this action.")
        return redirect(url_for('home', logged_in=current_user.is_authenticated))


@app.route('/Llj882hefgoo49wguih24ht438udgriu', methods=["GET", "POST"])
def new_user():
    if request.method == "GET":
        return render_template("new_user.html")
    if request.method == "POST":
        password = generate_password_hash(
            request.form["password"],
            method='pbkdf2:sha256',
            salt_length=8
        )
        name = request.form["name"]
        new_db_entry = User(password=password, name=name)
        if User.query.filter_by(name=name).first():
            flash("This username is already in use.")
            return redirect(url_for('login'))
        else:
            db.session.add(new_db_entry)
            db.session.commit()
            login_user(new_db_entry, remember=True)
            TelegramBot.send_text(
                f"New user {name} created.\nGo to https://www.jobslist.scolour.co.nz/admin to approve.")
            flash("Request sent to administrator for approval.")
            return redirect(url_for('login'))


@app.route('/login', methods=["GET", "POST"])
def login():
    if request.method == "GET":
        return render_template("login.html")
    if request.method == "POST":
        name = request.form["name"]
        user = db.session.query(User).filter_by(name=name).first()
        if not user:
            flash("User does not exist in database. Please try again.")
            return redirect(url_for('login'))
        elif not check_password_hash(user.password, request.form["password"]):
            flash("Incorrect password. Please try again.")
            return redirect(url_for('login'))
        else:
            login_user(user, remember=True)
            return redirect(url_for('home', logged_in=current_user.is_authenticated))


@app.route("/pager", methods=["GET", "POST"])
@login_required
def pager():
    if auth(user=current_user.id, action="accessed page", job='', name='') >= 2:
        '''
        #this can load a template for a custom message rather than just sending a page
        if request.method == "GET":
            return render_template("pager.html")
        if request.method == "POST":
            message = request.form["message"]
            TelegramBot.send_text(f'New message from {current_user.name}: {message}')
            return redirect(url_for('home', logged_in=current_user.is_authenticated))
        '''
        TelegramBot.send_text(f'Page from {current_user.name}')
        return redirect(url_for('home', logged_in=current_user.is_authenticated))
    else:
        flash("You are not authorized to perform this action.")
        return redirect(url_for('home', logged_in=current_user.is_authenticated))


@app.route("/logout")
def logout():
    return redirect(url_for("home"))


@app.route("/admin", methods=["GET", "POST"])
@login_required
def admin():
    if auth(user=current_user.id, action="accessed admin page", job='', name='') >= 5:
        if request.method == "GET":
            all_logs = Log.query.order_by(desc(Log.timestamp)).all()
            all_users = User.query.all()
            all_timesheets = Timesheet.query.order_by(Timesheet.id.desc()).all()
            return render_template("admin.html",
                                   all_logs=all_logs,
                                   users=all_users,
                                   timesheets=all_timesheets,
                                   logged_in=current_user.is_authenticated)
        if request.method == "POST":
            name = request.form["name"]
            user = db.session.query(User).filter_by(name=name).first()
            try:
                rights = int(request.form["rights"])
                user.rights = rights
            except ValueError:
                pass
            if request.form["department"] == "":
                pass
            else:
                department = request.form["department"]
                user.department = department
            if request.form["password"] == "":
                pass
            else:
                password = generate_password_hash(
                    request.form["password"],
                    method='pbkdf2:sha256',
                    salt_length=8
                )
                user.password = password
            db.session.commit()
            return redirect(url_for('home', logged_in=current_user.is_authenticated))
    else:
        flash("You are not authorized to perform this action.")
        return redirect(url_for('home', logged_in=current_user.is_authenticated))


# This part is not in use yet
'''
@app.route("/user/<name>", methods=["GET", "POST"])
@login_required
def user(name):
    edit_user = User.query.filter(User.name == name)
    if request.method == "GET":
        return render_template("user.html",
                                user=edit_user,
                                logged_in=current_user.is_authenticated)
    else:
        if request.form["email"] == "":
            pass
        else:
            user.name = request.form["email"]
        if request.form["password"] == "":
            pass
        else:
            user.password = generate_password_hash(
                request.form["password"],
                method='pbkdf2:sha256',
                salt_length=8
                )
        entered = '0'
        approved = '0'
        dispatched = '0'
        delivered = '0'
        if request.form.getlist('entered')[0]:
            entered = '1'
        if request.form.getlist('approved')[0]:
            approved = '1'
        if request.form.getlist('dispatched')[0]:
            dispatched = '1'
        if request.form.getlist('delivered')[0]:
            delivered = '1'
        #user.email_preferences = entered+approved+dispatched+delivered
        db.session.commit()
        return redirect(url_for('home', logged_in=current_user.is_authenticated))
'''


@app.errorhandler(401)
def auth_401(error):
    flash("You need to be logged in to do that.")
    return render_template("login.html"), 401


@app.errorhandler(500)
def special_exception_handler(error):
    if isinstance(error, HTTPException):
        TelegramBot.send_text(f'User {current_user.name} broke something.')
        return render_template("crash.html"), 500


if __name__ == "__main__":
    app.run()
