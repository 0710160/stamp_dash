import os
import pandas as pd
from datetime import datetime, timedelta
from sqlalchemy import create_engine
from flask import Flask
from flask_mail import Mail, Message
from dotenv import load_dotenv

load_dotenv()
APP_PASSWORD = os.getenv('APP_PASSWORD')
BRP_EMAIL = os.getenv('BRP_EMAIL')
MY_EMAIL = os.getenv('MY_EMAIL')

# Flask Mail manager
app = Flask(__name__)
app.app_context().push()
app.config['MAIL_SERVER']='smtp.fastmail.com'
app.config['MAIL_PORT'] = 465
app.config['MAIL_USERNAME'] = MY_EMAIL
app.config['MAIL_PASSWORD'] = APP_PASSWORD
app.config['MAIL_USE_SSL'] = True
app.config['MAIL_ASCII_ATTACHMENTS'] = False
mail = Mail(app)


db = create_engine("sqlite:////home/0710160/brpts/timesheet.sqlite3")


all_timesheets = pd.read_sql_table(
    "timesheet",
    con=db,
    columns=['user',
            'starttime',
            'stoptime',
            'job_no',
            'length',
            'operation',
            'note'],
)

df = all_timesheets[all_timesheets["starttime"] > datetime.now()]
df = df.sort_values(by=["user", "starttime"])
df = df[df["length"] > 0]

df["starttime"] = pd.to_datetime(df.starttime)
df["stoptime"] = pd.to_datetime(df.stoptime)
df["starttime"] = df["starttime"].dt.strftime("%H:%M:%S")
df["stoptime"] = df["stoptime"].dt.strftime("%H:%M:%S")

todays_date = str((datetime.now() + timedelta(hours=12)).strftime("%d/%m/%Y"))


# sends daily email
def email_group(staff, recipients):
    body = ""
    for user in staff:
        user_df = df[df["user"] == user]
        np = 0 #checks for non-productive work
        tp = 0 #total productive hours
        th = 0 #total hours
        body += (f'TIMESHEET FOR {user.upper()}\n')
        body += ("Start time\tEnd time\tJob no.\t\tLength\t\tOperation\tNote\n")
        for index, row in user_df.iterrows():
            if row['job_no'].startswith("np"):
                np += row['length']
                operation = "N/productive"
                job_no = "N/A\t"
            else:
                tp += row['length']
                job_no = row['job_no']
                if row['operation'] == 'None':
                    operation = ''
                else:
                    operation = row['operation']
            th += row['length']
            if row['length'] < 1:
                mins = int(row['length'] * 60)
                body += (f"{row['starttime']}\t{row['stoptime']}\t{job_no}\t{mins}mins\t\t{operation}\t{row['note']}\n")
            else:
                body += (f"{row['starttime']}\t{row['stoptime']}\t{job_no}\t{row['length']}hrs\t\t{operation}\t{row['note']}\n")
        body += (f"Total hours for {user}: {round(th, 1)} ({round((th/8)*100,0)}%)\n")
        body += (f"Total productive hours: {round(tp, 1)}\n")
        body += (f"Total non-productive hours: {round(np, 1)}\n\n")

    msg = Message(f'Timesheet spreadsheet for {staff} staff {todays_date}',
                sender=BRP_EMAIL,
                recipients=recipients,
                body=body)
    mail.send(msg)
    #print(body)
    return "Sent"


#define staff by department
prepress=["Des Sa'u", "Grant Shennan", "James Dale", "Richie McOnie", "Sara Bailey", "Erin Looyenga", "Tim Murphy"]
checking=["Kayla Oliver", "Clara Huynh", "Rowena Godfrey", "Pauline Niven", "Nimue Howes", "Casual"]

# run Mon-Fri (0-4)
today_nz = datetime.today() + timedelta(hours=10)
if today_nz.weekday() < 5:
    email_group(prepress, ["gregor.inger@brebnerprint.co.nz", "stacey.mccormack@brebnerprint.co.nz"])
    email_group(checking, ["matt.tobin@brebnerprint.co.nz"])
