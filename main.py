from flask import Flask, render_template, request
from flask_bootstrap import Bootstrap
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///production_schedule.sqlite3'
Bootstrap(app)
db = SQLAlchemy(app)


class Jobs(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    job_no = db.Column(db.String, nullable=False)
    job_name = db.Column(db.String(250), nullable=False)
    due_date = db.Column(db.Date)
    #priority = db.Column(db.Integer)


db.create_all()


@app.route("/")
def home():
    # Displays all incomplete jobs and orders by priority
    all_jobs = [job for job in db.session.query(Jobs).all()]
    return render_template("index.html", all_jobs=all_jobs)


@app.route("/add", methods=["GET", "POST"])
def add():
    # Currently manually adds jobs
    if request.method == "POST":
        job_no = request.form["job_no"]
        job_name = request.form["job_name"]
        due_date = (request.form["due_date"])
        due_date = datetime.strptime(due_date, "%Y-%m-%d")
        add_job = Jobs(job_no=job_no, job_name=job_name, due_date=due_date)
        db.session.add(add_job)
        db.session.commit()
        all_jobs = [job for job in db.session.query(Jobs).all()]
        return render_template("index.html", all_jobs=all_jobs)
    else:
        return render_template("add.html")


@app.route("/edit/<jobno>", methods=["GET", "POST"])
def edit(jobno):
    # Allows select users to edit the priority of jobs which influences sort order
    if request.method == "POST":
        return render_template("index.html")
    else:
        return render_template("edit.html")


@app.route("/complete/<jobno>")
def complete(jobno):
    # Removes a job from the database
    return render_template("index.html")


if __name__ == "__main__":
    app.run(debug=True)