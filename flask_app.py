from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import desc
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.exceptions import HTTPException
from flask_login import UserMixin, login_user, LoginManager, login_required, current_user, logout_user
from telegram_bot import TelegramBot
from dotenv import load_dotenv
from pathlib import Path
import os

load_dotenv()
SECRET_KEY = os.getenv('SECRET_KEY')

UPLOAD_FOLDER = 'static/uploads/'
# UPLOAD_FOLDER = '/home/0710160/mysite/static/uploads'
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


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(user_id)


class Jobs(db.Model):
    ''' Creates a DB for the job information '''
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    job_no = db.Column(db.String, nullable=False)
    job_name = db.Column(db.String(250), nullable=False)
    due_date = db.Column(db.Date)
    priority = db.Column(db.Float, default=9)
    plates_made = db.Column(db.Boolean, default=False)
    scheduled = db.Column(db.Integer, default=False)
    approved = db.Column(db.Boolean, default=False)
    completed = db.Column(db.Boolean, default=False)
    status = db.Column(db.String)
    notes = db.Column(db.String)
    img_name = db.Column(db.String(250))
    is_stamp = db.Column(db.Boolean, default=False)


class User(UserMixin, db.Model):
    ''' Creates a DB for the user information '''
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(250))
    password = db.Column(db.String(100))
    rights = db.Column(db.Integer, default=0)  # 0 is read-only, 5 is admin


class Log(db.Model):
    ''' Creates a DB for user action logs '''
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime)
    action = db.Column(db.String(100))


db.create_all()


def refresh_priority():
    ''' Function to count all jobs in DB and re-arrange based on priority where 1 is highest '''
    all_jobs = Jobs.query.order_by(Jobs.priority).filter(Jobs.completed == False)
    new_priority = 1
    all_jobs = Jobs.query.order_by(Jobs.priority).all()
    new_priority = 0
    for job in all_jobs:
        job.priority = new_priority
        new_priority += 1
    db.session.commit()


def auth(user, action, job):
    '''
    Function to check if user is authorized to perform an action.
        5 = Admin (all rights)
        4 = Add, Edit
        3 = Unused
        2 = Unused
        1 = Read Only
        0 = Account Only
    Logs actions to log.db
    '''
    auth_user = User.query.get(user)
    if action.startswith("accessed"):
        pass
    else:
        log_action = Log(timestamp=datetime.now(), action=f"User {auth_user.name} {action} job {job}")
        db.session.add(log_action)
        db.session.commit()
    return auth_user.rights


def plates_resort(job):
    '''Re-sorts job order based on new confirmed+plated job'''
    all_jobs = Jobs.query.order_by(Jobs.priority).filter(Jobs.completed == False)
    mark = 0
    for i in all_jobs:
        if i.approved and i.plates_made and not i.job_no == job.job_no:
            mark += 1
            print(i.job_no, mark)
    job.priority = mark + 0.5
    refresh_priority()


def date_resort(job):
    '''Re-sorts job order based on new job's due date'''
    all_jobs = Jobs.query.order_by(Jobs.priority).filter(Jobs.completed == False)
    mark = 0
    for i in all_jobs:
        added_job_date = i.due_date.strftime("%d%m%y")
        try:
            if i.approved or added_job_date < job.due_date.strftime("%d%m%y"):
                mark += 1
        except(AttributeError):
            pass
    job.priority = mark + 0.5
    refresh_priority()


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
    # Displays all jobs and orders by priority
    if auth(user=current_user.id, action="accessed dashboard", job='N/A') >= 1:
        stamp_jobs = Jobs.query.order_by(Jobs.due_date).filter(Jobs.is_stamp == True,
                                                                Jobs.scheduled == 1)
        outstanding_quotes = Jobs.query.order_by(Jobs.due_date).filter(Jobs.is_stamp == True,
                                                                Jobs.status == "submitted")
        to_do_quotes = Jobs.query.order_by(Jobs.due_date).filter(Jobs.is_stamp == True,
                                                                Jobs.status == "todo")
        return render_template("dashboard.html",
                               all_jobs=stamp_jobs,
                               outstanding_quotes=outstanding_quotes,
                               to_do_quotes=to_do_quotes,
                               logged_in=current_user.is_authenticated)
    else:
        flash(f"Please register a user to view this content.\nIf you've already signed up, please wait for the administrator to approve your user.")
        return redirect(url_for('new_user'))


@app.route("/add_quote", methods=["GET", "POST"])
@login_required
def add_quote():
    if auth(user=current_user.id, action="added", job="{new}") >= 4:
        if request.method == "GET":
            return render_template("add_quote.html", logged_in=current_user.is_authenticated)
        else:
            job_name = request.form["job_name"]
            due_date = request.form["due_date"]
            due_date = datetime.strptime(due_date, "%Y-%m-%d")
            notes = request.form["notes"]
            add_quote = Jobs(job_no="NULL",
                           job_name=job_name,
                           due_date=due_date,
                           status="todo",
                           notes=notes,
                           img_name="NULL",
                           is_stamp=True)
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
    if auth(user=current_user.id, action="confirmed", job=edit_job.job_no) >= 4:
            edit_job.status = "submitted"
            edit_job.due_date = datetime.now().strftime('%d/%m/%Y')
            refresh_priority()
    else:
        flash("You are not authorized to perform this action.")
    return redirect(request.referrer)


@app.route("/add_job/<job_id>", methods=["GET", "POST"])
@login_required
def add_job(job_id):
    new_job = Jobs.query.get(job_id)
    if auth(user=current_user.id, action="added", job=job_id) >= 4:
        if request.method == "GET":
            return render_template("add_job.html",
                job_name=new_job.job_name,
                logged_in=current_user.is_authenticated)
        else:
            job_no = request.form["job_no"]
            job_name = new_job.job_name
            due_date = (request.form["due_date"])
            due_date = datetime.strptime(due_date, "%Y-%m-%d")
            notes = request.form["notes"]
            filename = f'job{job_no}'
            blank_img = open(os.path.join(app.config['UPLOAD_FOLDER'], filename), "w")
            blank_img.close()
            current_date = datetime.now().strftime('%d/%m/%Y')
            is_stamp = False
            try:
                if request.form.getlist('is_stamp')[0]:
                    is_stamp = True
            except IndexError:
                is_stamp = False
            status = f'Entered {current_date}'
            new_job.job_no=job_no
            new_job.due_date=due_date
            new_job.notes=notes
            new_job.scheduled=1
            new_job.status=status
            new_job.img_name=f'job{job_no}'
            new_job.is_stamp=is_stamp
            db.session.commit()
            date_resort(new_job)
            return redirect(url_for('home', logged_in=current_user.is_authenticated))
    else:
        flash("You are not authorized to perform this action.")
        return redirect(url_for('home', logged_in=current_user.is_authenticated))


@app.route("/edit/<job_id>", methods=["GET", "POST"])
@login_required
def edit(job_id):
    edit_job = Jobs.query.get(job_id)
    if auth(user=current_user.id, action="edited", job=edit_job.job_no) >= 4:
        if request.method == "GET":
            filename = Path(os.path.join(app.config['UPLOAD_FOLDER'], edit_job.img_name))
            if filename.is_file():
                file_exists = True
            else:
                file_exists = False
            return render_template("edit.html",
                                   file_exists=file_exists,
                                   job=edit_job,
                                   logged_in=current_user.is_authenticated)
        else:
            current_date = datetime.now().strftime('%d/%m/%Y')
            if request.form["new_due_date"] == "":
                pass
            else:
                new_due_date = request.form["new_due_date"]
                new_due_date = datetime.strptime(new_due_date, "%Y-%m-%d")
                edit_job.due_date = new_due_date
            try:
                if request.form.getlist('is_stamp')[0]:
                    edit_job.is_stamp = True
            except IndexError:
                edit_job.is_stamp = False
            if request.form["new_priority"] == "":
                pass
            else:
                new_priority = request.form["new_priority"]
                edit_job.priority = new_priority
            if request.form["notes"] == "":
                pass
            elif request.form["notes"] == " ":
                edit_job.notes = None
            else:
                notes = request.form["notes"]
                edit_job.notes = notes
            if request.form["new_name"] == "":
                pass
            else:
                job_name = request.form["new_name"]
                edit_job.job_name = job_name
            if request.form['status'] == "curr":
                pass
            elif request.form['status'] == "proof":
                edit_job.status = f'On proof {current_date}'
            elif request.form['status'] == "approved":
                edit_job.status = f'Proof approved {current_date}'
                edit_job.approved = True
            elif request.form['status'] == "plates":
                edit_job.status = f'Plates made {current_date}'
                edit_job.plates_made = True
            elif request.form['status'] == "printed":
                edit_job.status = f'Printed {current_date}'
                edit_job.completed = True
            elif request.form['status'] == "finishing":
                edit_job.status = f'Finishing {current_date}'
            elif request.form['status'] == "check_pack":
                edit_job.status = f'Checking & packing {current_date}'
            elif request.form['status'] == "dispatched":
                edit_job.status = f'Dispatched {current_date}'
            refresh_priority()
            return redirect(url_for('home', logged_in=current_user.is_authenticated))
    else:
        flash("You are not authorized to perform this action.")
        return redirect(url_for('home', logged_in=current_user.is_authenticated))


@app.route("/upload_img/<job_id>", methods=["GET", "POST"])
@login_required
def upload_img(job_id):
    job = Jobs.query.get(job_id)
    if auth(user=current_user.id, action="completed", job=job.job_no) >= 4:
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
                return redirect(url_for('dashboard',
                                        job_id=job_id,
                                        logged_in=current_user.is_authenticated))
    else:
        flash("You are not authorized to perform this action.")
        return redirect(url_for('home', logged_in=current_user.is_authenticated))


@app.route("/complete/<job_id>")
@login_required
def complete(job_id):
    # Removes a job from the list
    complete_job = Jobs.query.get(job_id)
    job_name = complete_job.job_name
    if auth(user=current_user.id, action="completed", job=complete_job.job_no) >= 4:
        if complete_job.is_stamp:
            complete_job.completed = True
            current_date = datetime.now().strftime('%d/%m/%Y')
            complete_job.status = f'Printed {current_date}'
        else:
            os.remove(os.path.join(app.config['UPLOAD_FOLDER'], complete_job.img_name))
            db.session.delete(complete_job)
        db.session.commit()
        TelegramBot.send_text(f"Job {job_name} completed.")
    else:
        flash("You are not authorized to perform this action.")
    return redirect(request.referrer)


@app.route("/delete/<job_id>")
@login_required
def delete(job_id):
    # Removes a job from the database
    delete_job = Jobs.query.get(job_id)
    if auth(user=current_user.id, action="deleted", job=delete_job.job_no) >= 3:
        os.remove(os.path.join(app.config['UPLOAD_FOLDER'], delete_job.img_name))
        db.session.delete(delete_job)
        db.session.commit()
    else:
        flash("You are not authorized to perform this action.")
    return redirect(url_for('home', logged_in=current_user.is_authenticated))


@app.route("/priority_up/<job_id>")
@login_required
def priority_up(job_id):
    # Increases priority
    priority_edit = Jobs.query.get(job_id)
    if auth(user=current_user.id, action="increased priority on", job=priority_edit.job_no) >= 4:
        priority_edit.priority -= 1.5
        refresh_priority()
    else:
        flash("You are not authorized to perform this action.")
    return redirect(request.referrer)


@app.route("/priority_down/<job_id>")
@login_required
def priority_down(job_id):
    # Decreases priority
    priority_edit = Jobs.query.get(job_id)
    if auth(user=current_user.id, action="decreased priority on", job=priority_edit.job_no) >= 4:
        priority_edit.priority += 1.5
        refresh_priority()
    else:
        flash("You are not authorized to perform this action.")
    return redirect(request.referrer)


@app.route("/plates/<job_id>")
@login_required
def plates(job_id):
    # Toggles True/False
    job = Jobs.query.get(job_id)
    if auth(user=current_user.id, action="plates made for", job=job.job_no) >= 2:
        if job.plates_made:
            job.plates_made = False
            db.session.commit()
        else:
            job.plates_made = True
            current_date = datetime.now().strftime('%d/%m/%Y')
            job.status = f'Plates made {current_date}'
            # Runs through list to re-prioritise below other confirmed/plated jobs
            plates_resort(job)
    else:
        flash("You are not authorized to perform this action.")
    return redirect(request.referrer)


@app.route("/approved/<job_id>")
@login_required
def approved(job_id):
    # Toggles True/False
    job = Jobs.query.get(job_id)
    if auth(user=current_user.id, action="approved", job=job.job_no) >= 3:
        if job.approved:
            job.approved = False
            db.session.commit()
        else:
            job.approved = True
            current_date = datetime.now().strftime('%d/%m/%Y')
            job.status = f'Proof approved {current_date}'
            # Runs through list to re-prioritise below other confirmed/plated jobs
            plates_resort(job)
    else:
        flash("You are not authorized to perform this action.")
    return redirect(request.referrer)


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
    if auth(user=current_user.id, action="accessed admin page", job='N/A') >= 5:
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


@app.route("/status/<job_id>")
@login_required
def status(job_id):
    # Cycles through job status
    job_edit = Jobs.query.get(job_id)
    current_date = datetime.now().strftime('%d/%m/%Y')
    if job_edit.status.startswith("Entered"):
        job_edit.status = f"On proof {current_date}"
    elif job_edit.status.startswith("On proof"):
        job_edit.status = f"Proof approved {current_date}"
        job_edit.approved = True
        plates_resort(job_edit)
    elif job_edit.status.startswith("Proof approved"):
        job_edit.status = f"Plates made {current_date}"
        job_edit.plates_made = True
        plates_resort(job_edit)
    elif job_edit.status.startswith("Plates made"):
        job_edit.status = f"Printed {current_date}"
        job_edit.completed = True
    elif job_edit.status.startswith("Printed"):
        job_edit.status = f"Check & pack {current_date}"
    elif job_edit.status.startswith("Check"):
        job_edit.status = f"Dispatched {current_date}"
    elif job_edit.status.startswith("Dispatched "):
        db.session.delete(job_edit)
        os.remove(os.path.join(app.config['UPLOAD_FOLDER'], job_edit.img_name))
    else:
        job_edit.status = job_edit.status
    db.session.commit()
    return redirect(request.referrer)


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
