from flask import Flask, render_template, request, redirect, url_for
from flask_bootstrap import Bootstrap
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///production_schedule.sqlite3'
Bootstrap(app)
db = SQLAlchemy(app)


class Jobs(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    job_no = db.Column(db.String, nullable=False)
    job_name = db.Column(db.String(250), nullable=False)
    due_date = db.Column(db.Date)
    priority = db.Column(db.Integer, default=4)
    plates_made = db.Column(db.Boolean, default=False)
    scheduled = db.Column(db.Boolean, default=False)


db.create_all()

@app.route("/")
def home():
    # Displays all incomplete jobs and orders by priority
    all_jobs = Jobs.query.order_by(Jobs.priority).all()
    return render_template("index.html", all_jobs=all_jobs)


@app.route("/add", methods=["GET", "POST"])
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
        db.session.commit()
        all_jobs = Jobs.query.order_by(Jobs.priority).all()
        return redirect(url_for("home", all_jobs=all_jobs))
    else:
        edit_job = Jobs.query.get(job_id)
        return render_template("edit.html", job=edit_job)


@app.route("/complete/<job_id>")
def complete(job_id):
    # Removes a job from the database
    delete_job = Jobs.query.get(job_id)
    db.session.delete(delete_job)
    db.session.commit()
    all_jobs = Jobs.query.order_by(Jobs.priority).all()
    return redirect(url_for("home", all_jobs=all_jobs))


@app.route("/priority_up/<job_id>")
def priority_up(job_id):
    # Increases priority
    priority_edit = Jobs.query.get(job_id)
    priority_edit.priority -= 1
    db.session.commit()
    all_jobs = Jobs.query.order_by(Jobs.priority).all()
    return redirect(url_for("home", all_jobs=all_jobs))


@app.route("/priority_down/<job_id>")
def priority_down(job_id):
    # Decreases priority
    priority_edit = Jobs.query.get(job_id)
    priority_edit.priority += 1
    db.session.commit()
    all_jobs = Jobs.query.order_by(Jobs.priority).all()
    return redirect(url_for("home", all_jobs=all_jobs))


@app.route("/plates/<job_id>")
def plates(job_id):
    # Saves checkbox
    job = Jobs.query.get(job_id)
    if job.plates_made:
        job.plates_made = False
    else:
        job.plates_made = True
    db.session.commit()
    all_jobs = Jobs.query.order_by(Jobs.priority).all()
    return redirect(url_for("home", all_jobs=all_jobs))


if __name__ == "__main__":
    app.run(debug=True)