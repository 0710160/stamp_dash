# SCP Production Schedule

> Flask-powered site deployed on PythonAnywhere with SCP job information and production milestone tags.
<hr>

![](https://img.shields.io/badge/Code-Python-informational?style=flat&logo=python&logoColor=yellow&color=2bbc8a)
![](https://img.shields.io/badge/Tools-Flask-informational?style=flat&logo=flask&logoColor=black&color=2bbc8a)

## Contents
* index.html displays list of all jobs, allows authorized users to re-order and tag job milestones.
* new_user.html salts and hashes passwords, adding them to database. Sends a Telegram message to admin notifying them of a new user.
* login.html simple login page.
* add.html adds a job to the list displayed on index.html.
* edit.html edits the priority, due date or notes on a job.
* admin.html allows admin to assign an authorization level to new users and to view logs.
