from flask import Flask, render_template, request, redirect, url_for, flash
from flask_bootstrap import Bootstrap
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin, login_user, LoginManager, login_required, current_user, logout_user


app = Flask(__name__)
app.config['SECRET_KEY'] = "65K1Ax8pWqbNMkTkMJuY"
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///production_schedule.sqlite3'
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
    priority = db.Column(db.Float, default=4)
    plates_made = db.Column(db.Boolean, default=False)
    scheduled = db.Column(db.Boolean, default=False)
    approved = db.Column(db.Boolean, default=False)
    notes = db.Column(db.String)


class User(UserMixin, db.Model):
    ''' Creates a DB for the user information '''
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(250))
    password = db.Column(db.String(100))
    rights = db.Column(db.Integer, default=False)  #1 is admin, 2 can complete, 3 can plates, etc

db.create_all()


def refresh_priority():
    ''' Function to count all jobs in DB and re-arrange based on priority where 1 is highest '''
    all_jobs = Jobs.query.order_by(Jobs.priority).all()
    new_priority = 1
    for job in all_jobs:
        job.priority = new_priority
        new_priority += 1
    db.session.commit()


@app.route("/")
def home():
    # Displays all incomplete jobs and orders by priority
    all_jobs = Jobs.query.order_by(Jobs.priority).all()
    return render_template("index.html", all_jobs=all_jobs, logged_in=current_user.is_authenticated)


@app.route("/add", methods=["GET", "POST"])
@login_required
def add():
    # Currently manually adds jobs, later will import automatically from SQL
    if request.method == "POST":
        job_no = request.form["job_no"]
        job_name = request.form["job_name"]
        due_date = (request.form["due_date"])
        due_date = datetime.strptime(due_date, "%Y-%m-%d")
        add_job = Jobs(job_no=job_no, job_name=job_name, due_date=due_date)
        db.session.add(add_job)
        db.session.commit()
        all_jobs = Jobs.query.order_by(Jobs.priority).all()
        return redirect(url_for("home", all_jobs=all_jobs))
    else:
        return render_template("add.html")


@app.route("/edit/<job_id>", methods=["GET", "POST"])
@login_required
def edit(job_id):
    # Allows select users to edit the priority of jobs which influences sort order
    if request.method == "POST":
        edit_job = Jobs.query.get(job_id)
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
        db.session.commit()
        all_jobs = Jobs.query.order_by(Jobs.priority).all()
        return redirect(url_for("home", all_jobs=all_jobs, logged_in=current_user.is_authenticated))
    else:
        edit_job = Jobs.query.get(job_id)
        return render_template("edit.html", job=edit_job, logged_in=current_user.is_authenticated)


@app.route("/complete/<job_id>")
@login_required
def complete(job_id):
    # Removes a job from the database
    delete_job = Jobs.query.get(job_id)
    db.session.delete(delete_job)
    db.session.commit()
    all_jobs = Jobs.query.order_by(Jobs.priority).all()
    return redirect(url_for("home", all_jobs=all_jobs, logged_in=current_user.is_authenticated))


@app.route("/priority_up/<job_id>")
@login_required
def priority_up(job_id):
    ##TODO: need to restrict this to admins
    # Increases priority
    priority_edit = Jobs.query.get(job_id)
    priority_edit.priority -= 1.5
    db.session.commit()
    refresh_priority()
    all_jobs = Jobs.query.order_by(Jobs.priority).all()
    return redirect(url_for("home", all_jobs=all_jobs, logged_in=current_user.is_authenticated))


@app.route("/priority_down/<job_id>")
@login_required
def priority_down(job_id):
    # Decreases priority
    priority_edit = Jobs.query.get(job_id)
    priority_edit.priority += 1.5
    db.session.commit()
    refresh_priority()
    all_jobs = Jobs.query.order_by(Jobs.priority).all()
    return redirect(url_for("home", all_jobs=all_jobs, logged_in=current_user.is_authenticated))


@app.route("/plates/<job_id>")
@login_required
def plates(job_id):
    # Saves checkbox
    job = Jobs.query.get(job_id)
    if job.plates_made:
        job.plates_made = False
    else:
        job.plates_made = True
    db.session.commit()
    all_jobs = Jobs.query.order_by(Jobs.priority).all()
    return redirect(url_for("home", all_jobs=all_jobs, logged_in=current_user.is_authenticated))


@app.route("/approved/<job_id>")
@login_required
def approved(job_id):
    # Saves checkbox
    job = Jobs.query.get(job_id)
    if job.approved:
        job.approved = False
    else:
        job.approved = True
    db.session.commit()
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
            login_user(new_user, remember=True)
            all_jobs = Jobs.query.order_by(Jobs.priority).all()
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


@app.errorhandler(401)
def auth_401(error):
    flash("You need to be logged in to do that.")
    return render_template("login.html"), 401


if __name__ == "__main__":
    app.run(host="10.0.1.26", port="5959", debug=True)