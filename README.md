# SCP Production Schedule

> Flask-powered site with sqlite3 database deployed on PythonAnywhere.
<hr>

![](https://img.shields.io/badge/Code-Python-informational?style=flat&logo=python&logoColor=yellow&color=2bbc8a)
![](https://img.shields.io/badge/Tools-Flask-informational?style=flat&logo=flask&logoColor=black&color=2bbc8a)

## Contents
* new_user.html salts and hashes passwords, adding them to database. Sends a Telegram message to admin notifying them of a new user and links to Admin page to approve.
* login.html simple login page.
* index.html displays list of all jobs, allows authorized users to re-order, edit due date and notes, and tag job milestones.
* add.html adds a job to the list displayed on index.html with ability to add due date and job notes.
* edit.html edits the priority, due date or notes on a job, or deletes a job from the database.
* admin.html allows admin to assign an authorization level to new users and to view logs of add activity on the site.

## Feature Wishlist
* Self-hosted site linking to Tharstern SQL.
