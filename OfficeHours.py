import os, datetime
from flask import Flask, render_template, request, redirect, flash, session
from flask_sqlalchemy import SQLAlchemy
import csv
import re


app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://localhost/aninditgo'
app.config['SQLALCHEMY_ECHO'] = True
app.permanent_session_lifetime = datetime.timedelta(days=365)
db = SQLAlchemy(app)

TOTAL_OFFICE_HOUR_SLOTS = 7*2*5
ADMIN_USERNAME = 'admin'
ADMIN_PASSWORD = 'rosaparks1955'

OFFICE_USERNAME = 'office'
OFFICE_PASSWORD = 'sp1ndoctor'

class User(db.Model):
    __tablename__ = "users"
    
    username = db.Column(db.String(120), primary_key=True)
    password = db.Column(db.String(120))
    name = db.Column(db.String(120))

    #see below for possible divisions
    division = db.Column(db.String(120))
    CONDUCT = "conduct"
    ACADEMIC = "academic"
    FIN_AID = "fincial aid"
    GRIEVANCE = "grievance"
    NOT_APPLICABLE = "n/a"    
    #see below for the possible types
    standing = db.Column(db.String(120))
    INACTIVE = 'inactive'
    NEW_HIRE = 'new_hire'
    CASEWORKER = 'caseworker'
    VETERAN = 'veteran'

    #There are 70 office hour slots, so we have an array with 70 entries. See below for possible value of each entry
    office_hour_input = db.Column(db.ARRAY(db.Integer))
    NO_PREFERENCE = 0
    PREFERRED = 1
    UNAVAILABLE = 2

    #There are 70 office hour slots, this will have the 6 assigned slots
    NUM_ASSIGNED_SLOTS = 6
    assigned_office_hours = db.Column(db.ARRAY(db.Integer))
    UNASSIGNED = -1

    def __init__(self, username, password, name="name"):
        self.username = username
        self.password = password
        self.standing = User.INACTIVE
        self.office_hour_input = [User.NO_PREFERENCE for _ in range(TOTAL_OFFICE_HOUR_SLOTS)]
        self.assigned_office_hours = [User.UNASSIGNED for _ in range(User.NUM_ASSIGNED_SLOTS)]
        self.name = name
        self.division = User.NOT_APPLICABLE
#db.drop_all()
db.create_all()

def clear_user_session():
    session.pop('user', None)

def automatic_logout():
    flash("Sorry, you either logged out, logged into another account, or are trying to access something you shouldn't!")
    return redirect('/')

@app.route('/admin')
def admin():
    if session.get('user') == ADMIN_USERNAME: 
        return render_template('admin.html')
    else: 
        return automatic_logout()

@app.route('/office')
def office():
    if session.get('user') == OFFICE_USERNAME:
        return render_template('office.html')
    else:
        return automatic_logout()

@app.route('/add_users')
def add_users():
    if session.get('user') == ADMIN_USERNAME or True:
        return render_template('add_users.html')
    else:
        return automatic_logout()

@app.route('/try_adding_users', methods = ['POST'])
def try_adding_users():
    if session.get('user') == ADMIN_USERNAME or True:
        new_users_text = request.form['new_users_text'].strip()
        if new_users_text:
            new_users_lines = new_users_text.splitlines()
            user_list = []
            error = False
            for line in new_users_lines:
                user_pass = line.split(',')
                if len(user_pass) != 2:
                    flash("Formatting Error on this line: " + line)
                    error = True
                else:
                    user_list.append((user_pass[0].strip(), user_pass[1].strip()))
            if not error:
                something_to_write = False
                db.session.rollback()
                for username,pw in user_list:
                    if db.session.query(User).filter(User.username == username).count():
                        flash("<"+username + "> already exists in the database. Nothing was written for this line.")
                    else:
                        user = User(username,pw)
                        db.session.add(user)
                        something_to_write = True
                if something_to_write:
                    db.session.commit()
                    flash("Successfully wrote something to the database!!")
               
        else :
            flash("Please enter something!")

        return redirect('/add_users')
    else:
        return automatic_logout()

@app.route('/user_list')
def user_list():
    if session.get('user') == ADMIN_USERNAME or True:
        db.session.rollback()
        user_list_for_html = []
        user_list_classform = db.session.query(User).all()
        for user in user_list_classform:
            office_hour_preferences = 'no' if sum(user.office_hour_input) == 0 else 'yes'
            office_hour_assignments = 'not yet assigned' if -1 in user.assigned_office_hours else 'coming soon'
            user_list_for_html.append([user.username, user.password, user.division, user.standing, office_hour_preferences, office_hour_assignments])
        
        return render_template('user_list.html', user_list = user_list_for_html)
    else:
        return automatic_logout()

@app.route('/try_deleting_users', methods = ['POST'])
def try_deleting_users():
    selected = request.form.getlist('users_to_delete')
    deleted_string = ''
    db.session.rollback()
    for username in selected :
        deleted_string += username + ", "
        db.session.query(User).filter(User.username == username).delete()
        db.session.commit()
        flash("Successfully deleted: " + deleted_string[:-2])
    return redirect('/user_list')

@app.route('/reset_system')
def reset_system():
    if session.get('user') == ADMIN_USERNAME or True:
        return render_template('reset_system.html')
    return automatic_logout()

@app.route('/try_reset', methods = ['POST'])
def try_reset():
    if session.get('user') == ADMIN_USERNAME or True:
        username = request.form['username']
        password = request.form['password']
        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            db.drop_all()
            db.create_all()
            flash("System has been reset!")
        else:
            flash ("Invalid Credentials! Also think again.")
        return redirect('/reset_system')
    return automatic_logout()

@app.route('/user&=<username>')
def user_page(username):
    if session.get('user') == username or True:
        return render_template('user_page.html', username=username)
    return automatic_logout()

@app.route('/change_password&=<username>')
def change_password(username):
    if session.get('user') == username or True:
        return render_template('change_password.html', username=username)
    return automatic_logout()

@app.route('/try_changing_password&=<username>', methods = ['POST'])
def try_changing_password(username):
    if session.get('user') == username or True:
        if db.session.query(User).filter(User.username == username).count() and db.session.query(User).filter(User.username == username).one().password == request.form['old_pass']:
            if request.form['new_pass'] == request.form['new_pass_x2']:
                db.session.query(User).filter(User.username == username).one().password = request.form['new_pass']
                db.session.commit()
                flash ("Successfully changed password!")
            else:
                flash ("Your 2 new passwords don't match.")
        else: 
            flash ("Entered the wrong Old Password.")
        return redirect("/change_password&=" + username)
    return automatic_logout()

@app.route('/edit_profile&=<username>')
def edit_profile(username):
    if session.get('user') == username or True:
        if db.session.query(User).filter(User.username == username).count():
            cur_user = db.session.query(User).filter(User.username == username).one()
            radio_standing_order = [User.INACTIVE, User.NEW_HIRE, User.CASEWORKER, User.VETERAN]
            radio_standing = ['checked' if cur_user.standing == standing else '' for standing in radio_standing_order]
            radio_division_order = [User.NOT_APPLICABLE, User.CONDUCT, User.GRIEVANCE, User.ACADEMIC, User.FIN_AID]
            radio_division = ['checked' if cur_user.division == division else '' for division in radio_division_order]
        return render_template('edit_profile.html', username=username, radio_standing=radio_standing, radio_division=radio_division)
    return automatic_logout()

@app.route('/try_editing_profile&=<username>', methods = ['POST'])
def try_editing_profile(username):
    if session.get('user') == username or True:
        if db.session.query(User).filter(User.username == username).count():
            db.session.rollback()
            cur_user = db.session.query(User).filter(User.username == username).one()
            cur_user.standing = request.form['standing']
            cur_user.division = request.form['division']
            db.session.commit()
            flash("Successfully Saved!")
        return redirect("/edit_profile&=" + username)
    return automatic_logout()

@app.route('/')
def home():
    return render_template('login_form.html')

@app.route('/login', methods=['POST'])
def login():
    username = request.form['username']
    password = request.form['password']
    good_login = False
    redirect_url = '/'
    if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
        good_login = True
        redirect_url = '/admin'
    elif username == OFFICE_USERNAME and password == OFFICE_PASSWORD:
        good_login = True
        redirect_url = '/office'
    elif db.session.query(User).filter(User.username == username).count() and db.session.query(User).filter(User.username == username).one().password == password:
        good_login = True
        redirect_url = '/user&='+username
    if good_login:
        session.permanent = True
        session['user'] = username
    else:
        flash ("Invalid Credentials!")
    return redirect(redirect_url)

@app.route('/logout')
def logout():
    clear_user_session()
    return redirect('/')


if __name__ == '__main__':
    app.secret_key = os.urandom(12)
    app.run()
