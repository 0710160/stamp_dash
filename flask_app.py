from flask import Flask, render_template, request, redirect, url_for, flash
from flask_bootstrap import Bootstrap
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import desc
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.exceptions import HTTPException
from flask_login import UserMixin, login_user, LoginManager, login_required, current_user, logout_user
from telegram_bot import TelegramBot
from dotenv import load_dotenv
import os

load_dotenv()
SECRET_KEY = os.getenv('SECRET_KEY')

app = Flask(__name__)
app.config['SECRET_KEY'] = SECRET_KEY
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv("DATABASE_URL2")
#app.config['SQLALCHEMY_DATABASE_URI'] = ("sqlite:///production_schedule.sqlite3")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
Bootstrap(app)
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
    scheduled = db.Column(db.Boolean, default=False)
    approved = db.Column(db.Boolean, default=False)
    notes = db.Column(db.String)


class User(UserMixin, db.Model):
    ''' Creates a DB for the user information '''
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(250))
    password = db.Column(db.String(100))
    rights = db.Column(db.Integer, default=0)  #0 is read-only, 5 is admin


class Log(db.Model):
    ''' Creates a DB for user action logs '''
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime)
    action = db.Column(db.String(100))


db.create_all()


def refresh_priority():
    ''' Function to count all jobs in DB and re-arrange based on priority where 1 is highest '''
    all_jobs = Jobs.query.order_by(Jobs.priority).all()
    new_priority = 1
    for job in all_jobs:
        job.priority = new_priority
        new_priority += 1
    db.session.commit()


def auth(user, action, job):
    '''
    Function to check if user is authorized to perform an action.
        5 = Admin (all rights)
        4 = Sort, Edit
        3 = Approve, Add New Job
        2 = Plates
        1 = Complete
        0 = Read only
    Logs actions to log.db
    '''
    auth_user = User.query.get(user)
    log_action = Log(timestamp=datetime.now(), action=f"User {auth_user.name} {action} job {job}")
    db.session.add(log_action)
    db.session.commit()
    return auth_user.rights


def plates_resort(job):
    '''Re-sorts job order based on new confirmed+plated job'''
    all_jobs = Jobs.query.order_by(Jobs.priority).all()
    mark = 0
    for i in all_jobs:
        if i.approved and i.plates_made:
            mark += 1
    job.priority = mark
    refresh_priority()


def date_resort(job):
    '''Re-sorts job order based on new job's due date'''
    all_jobs = Jobs.query.order_by(Jobs.priority).all()
    mark = 0
    for i in all_jobs:
        added_job_date = i.due_date.strftime("%d%m%y")
        if i.approved or added_job_date < job.due_date.strftime("%d%m%y"):
            mark += 1
    job.priority = mark
    refresh_priority()


# Changes date display with Jinja templating
@app.template_filter()
def datefilter(value, format='%d/%m/%y'):
    return value.strftime(format)


app.jinja_env.filters['datefilter'] = datefilter


@app.route("/")
def home():
    # Displays all incomplete jobs and orders by priority
    all_jobs = Jobs.query.order_by(Jobs.priority).all()
    return render_template("index.html", all_jobs=all_jobs, logged_in=current_user.is_authenticated)


@app.route("/add", methods=["GET", "POST"])
@login_required
def add():
    # Currently manually adds jobs, later will import automatically from SQL
    if auth(user=current_user.id, action="added", job="{new}") >= 3:
        if request.method == "GET":
            return render_template("add.html", logged_in=current_user.is_authenticated)
        else:
            job_no = request.form["job_no"]
            job_name = request.form["job_name"]
            due_date = (request.form["due_date"])
            due_date = datetime.strptime(due_date, "%Y-%m-%d")
            add_job = Jobs(job_no=job_no, job_name=job_name, due_date=due_date)
            db.session.add(add_job)
            date_resort(add_job)
            all_jobs = Jobs.query.order_by(Jobs.priority).all()
            return redirect(url_for("home", all_jobs=all_jobs))
    else:
        flash("You are not authorized to perform this action.")
        all_jobs = Jobs.query.order_by(Jobs.priority).all()
        return redirect(url_for("home", all_jobs=all_jobs))


@app.route("/edit/<job_id>", methods=["GET", "POST"])
@login_required
def edit(job_id):
    # Allows select users to edit the priority of jobs which influences sort order
    edit_job = Jobs.query.get(job_id)
    if auth(user=current_user.id, action="edited", job=edit_job.job_no) >= 4:
        if request.method == "GET":
            return render_template("edit.html", job=edit_job, logged_in=current_user.is_authenticated)
        else:
            if request.form["new_due_date"] == "":
                pass
            else:
                new_due_date = request.form["new_due_date"]
                new_due_date = datetime.strptime(new_due_date, "%Y-%m-%d")
                edit_job.due_date = new_due_date
            if request.form["new_priority"] == "":
                pass
            else:
                new_priority = request.form["new_priority"]
                edit_job.priority = new_priority
            if request.form["notes"] == "":
                pass
            else:
                notes = request.form["notes"]
                edit_job.notes = notes
            refresh_priority()
            all_jobs = Jobs.query.order_by(Jobs.priority).all()
            return redirect(url_for("home", all_jobs=all_jobs, logged_in=current_user.is_authenticated))
    else:
        flash("You are not authorized to perform this action.")
        all_jobs = Jobs.query.order_by(Jobs.priority).all()
        return redirect(url_for("home", all_jobs=all_jobs, logged_in=current_user.is_authenticated))


@app.route("/complete/<job_id>")
@login_required
def complete(job_id):
    # Removes a job from the database
    delete_job = Jobs.query.get(job_id)
    if auth(user=current_user.id, action="completed", job=delete_job.job_no) >= 1:
        db.session.delete(delete_job)
        db.session.commit()
    else:
        flash("You are not authorized to perform this action.")
    all_jobs = Jobs.query.order_by(Jobs.priority).all()
    return redirect(url_for("home", all_jobs=all_jobs, logged_in=current_user.is_authenticated))


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
    all_jobs = Jobs.query.order_by(Jobs.priority).all()
    return redirect(url_for("home", all_jobs=all_jobs, logged_in=current_user.is_authenticated))


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
    all_jobs = Jobs.query.order_by(Jobs.priority).all()
    return redirect(url_for("home", all_jobs=all_jobs, logged_in=current_user.is_authenticated))


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
            # Runs through list to re-prioritise below other confirmed/plated jobs
            plates_resort(job)
    else:
        flash("You are not authorized to perform this action.")
    all_jobs = Jobs.query.order_by(Jobs.priority).all()
    return redirect(url_for("home", all_jobs=all_jobs, logged_in=current_user.is_authenticated))


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
            # Runs through list to re-prioritise below other confirmed/plated jobs
            plates_resort(job)
    else:
        flash("You are not authorized to perform this action.")
    all_jobs = Jobs.query.order_by(Jobs.priority).all()
    return redirect(url_for("home", all_jobs=all_jobs, logged_in=current_user.is_authenticated))


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
        new_db_entry = User(
            password=password,
            name=name
        )
        if User.query.filter_by(name=name).first():
            flash("This username is already in use.")
            return redirect(url_for('login'))
        else:
            db.session.add(new_db_entry)
            db.session.commit()
            login_user(new_db_entry, remember=True)
            all_jobs = Jobs.query.order_by(Jobs.priority).all()
            TelegramBot.send_text(f"New user {name} created.\nGo to http://0710160.pythonanywhere.com/admin to approve.")
            return redirect(url_for("home", all_jobs=all_jobs, logged_in=current_user.is_authenticated))


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
            all_jobs = Jobs.query.order_by(Jobs.priority).all()
            return redirect(url_for("home", all_jobs=all_jobs, logged_in=current_user.is_authenticated))


@app.route("/logout")
def logout():
    logout_user()
    all_jobs = Jobs.query.order_by(Jobs.priority).all()
    return redirect(url_for("home", all_jobs=all_jobs))


@app.route("/admin", methods=["GET", "POST"])
@login_required
def admin():
    if auth(user=current_user.id, action="accessed admin page;", job="N/A") >= 5:
        if request.method == "GET":
            all_logs = Log.query.order_by(desc(Log.timestamp)).all()
            return render_template("admin.html", all_logs=all_logs, logged_in=current_user.is_authenticated)
        else:
            name = request.form["name"]
            user = db.session.query(User).filter_by(name=name).first()
            rights = int(request.form["rights"])
            user.rights = rights
            db.session.commit()
            all_jobs = Jobs.query.order_by(Jobs.priority).all()
            return render_template("index.html", all_jobs=all_jobs, logged_in=current_user.is_authenticated)
    else:
        flash("You are not authorized to perform this action.")
        all_jobs = Jobs.query.order_by(Jobs.priority).all()
        return render_template("index.html", all_jobs=all_jobs, logged_in=current_user.is_authenticated)


@app.errorhandler(401)
def auth_401(error):
    flash("You need to be logged in to do that.")
    return render_template("login.html"), 401


@app.errorhandler(500)
def special_exception_handler(error):
    if isinstance(error, HTTPException):
        error_debug = {
            "code": error.code,
            "name": error.name,
            "description": error.description
        }
    TelegramBot.send_text(error_debug)
    return "Database error. A notification has been sent to the administrator.", 500


if __name__ == "__main__":
    app.run()
