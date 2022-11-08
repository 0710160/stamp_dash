from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import desc, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.exceptions import HTTPException
from flask_login import UserMixin, login_user, LoginManager, login_required, current_user, logout_user
from telegram_bot import TelegramBot
from dotenv import load_dotenv
from pathlib import Path
from flask_mail import Mail, Message
import os

load_dotenv()
SECRET_KEY = os.getenv('SECRET_KEY')
APP_PASSWORD = os.getenv('APP_PASSWORD')

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
app.config['MAIL_USERNAME'] = 'mtobin@fastmail.fm'
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
    plates_made = db.Column(db.Boolean, default=False)
    scheduled = db.Column(db.Integer, default=False)
    completed = db.Column(db.Boolean, default=False)
    status = db.Column(db.String)
    notes = db.Column(db.String)
    img_name = db.Column(db.String(250))
    is_stamp = db.Column(db.Boolean, default=False)  #unused
    logs = relationship("Log", back_populates="jobs")


class User(UserMixin, db.Model):
    ''' DB for the user information '''
    __tablename__ = "user"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(250))
    password = db.Column(db.String(100))
    rights = db.Column(db.Integer, default=0)  # 0 is no access, 1 is read-only, 5 is admin
    #email_preferences = db.Column(db.String)


class Log(db.Model):
    ''' DB for user action logs '''
    __tablename__ = "log"
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime)
    action = db.Column(db.String(100))
    job_no = db.Column(db.String, ForeignKey("jobs.job_no"))
    jobs = relationship("Jobs", back_populates="logs")


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
    msg = Message('Notification from Stamp Production Viewer', sender='stamps@sent.com', recipients=recipients)
    for recipient in recipients:
        full_body = body + f'\n\nThis message was sent automatically from http://www.jobslist.scolour.co.nz/ To opt out of future emails, reply to this email with UNSUBSCRIBE as the subject.'
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
        stamp_jobs = Jobs.query.order_by(Jobs.due_date).filter(Jobs.scheduled == 1, Jobs.completed == False)
        outstanding_quotes = Jobs.query.order_by(Jobs.due_date).filter(Jobs.status == "submitted")
        to_do_quotes = Jobs.query.order_by(Jobs.due_date).filter(Jobs.status == "todo")
        return render_template("dashboard.html",
                               all_jobs=stamp_jobs,
                               outstanding_quotes=outstanding_quotes,
                               to_do_quotes=to_do_quotes,
                               all=False,
                               logged_in=current_user.is_authenticated)
    else:
        flash(f"Please register a user to view this content.\nIf you've already signed up, please wait for the administrator to approve your user.")
        return redirect(url_for('new_user'))


@app.route("/all")
@login_required
def all():
    if auth(user=current_user.id, action="accessed dashboard", job='', name='') >= 1:
        stamp_jobs = Jobs.query.order_by(Jobs.due_date).filter(Jobs.scheduled == 1)
        outstanding_quotes = Jobs.query.order_by(Jobs.due_date).filter(Jobs.status == "submitted")
        to_do_quotes = Jobs.query.order_by(Jobs.due_date).filter(Jobs.status == "todo")
        return render_template("dashboard.html",
                               all_jobs=stamp_jobs,
                               outstanding_quotes=outstanding_quotes,
                               to_do_quotes=to_do_quotes,
                               all=True,
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
        else:
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


@app.route("/complete_quote/<job_id>", methods=["GET", "POST"])
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
                logged_in=current_user.is_authenticated)
        else:
            job_no = request.form["job_no"]
            job_value = request.form["job_value"]
            due_date = (request.form["due_date"])
            due_date = datetime.strptime(due_date, "%Y-%m-%d")
            notes = request.form["notes"]
            filename = f'job{job_no}'
            blank_img = open(os.path.join(app.config['UPLOAD_FOLDER'], filename), "w")
            blank_img.close()
            current_date = time_adjusted()
            status = f'Entered {current_date}'
            new_job.job_no=job_no
            new_job.job_value=job_value
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
                                   logged_in=current_user.is_authenticated)
        else:
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
                auth(user=current_user.id, action="edited notes on job", job=edit_job.job_no, name=edit_job.job_name)
                notes = request.form["notes"]
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
            if request.form['status'] == "curr":
                pass
            elif request.form['status'] == "proof":
                auth(user=current_user.id, action="marked on proof job", job=edit_job.job_no, name=edit_job.job_name)
                edit_job.status = f'On proof {current_date}'
            elif request.form['status'] == "approved":
                auth(user=current_user.id, action="marked proof approved on job", job=edit_job.job_no, name=edit_job.job_name)
                edit_job.status = f'Proof approved {current_date}'
                mail_manager(recipients=['Stacey.McCormack@brebnerprint.co.nz', 'tim.murphy@scolour.co.nz', 'matt.tobin@brebnerprint.co.nz'], body=f'Stamp job {edit_job.job_no} \'{edit_job.job_name}\' is approved to print, and has a target dispatch date of {edit_job.due_date.strftime("%d/%m/%Y")}.')
                edit_job.approved = True
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
            edit_job.approved = True
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
    if auth(user=current_user.id, action="created status update", job='', name='') >= 4:
        stamp_jobs = Jobs.query.order_by(Jobs.due_date).filter(Jobs.scheduled == 1, Jobs.completed == False)
        return render_template("status_update.html",
                               all_jobs=stamp_jobs,
                               logged_in=current_user.is_authenticated)
    else:
        flash(f"You are not authorized to perform this action.")
        return redirect(url_for('home'))


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
    else:
        flash("You are not authorized to perform this action.")
    return redirect(url_for('home', logged_in=current_user.is_authenticated))


@app.route('/new_user', methods=["GET", "POST"])
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
                f"New user {name} created.\nGo to http://www.jobslist.scolour.co.nz/admin to approve.")
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


@app.route("/logout")
def logout():
    logout_user()
    return redirect(url_for("login"))


@app.route("/admin", methods=["GET", "POST"])
@login_required
def admin():
    if auth(user=current_user.id, action="accessed admin page", job='N/A', name='') >= 5:
        if request.method == "GET":
            all_logs = Log.query.order_by(desc(Log.timestamp)).all()
            all_users = User.query.all()
            return render_template("admin.html",
                                   all_logs=all_logs,
                                   users=all_users,
                                   logged_in=current_user.is_authenticated)
        else:
            name = request.form["name"]
            user = db.session.query(User).filter_by(name=name).first()
            try:
                rights = int(request.form["rights"])
                user.rights = rights
            except ValueError:
                pass
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
        error_debug = f'User {current_user.name} broke something. {error.code}: {error.name}'
    TelegramBot.send_text(error_debug)
    return f"Database error. A notification has been sent to the administrator.", 500


if __name__ == "__main__":
    app.run()
