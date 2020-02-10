import os, datetime, string 
from flask import Flask, render_template, request, redirect, flash, session
from flask_sqlalchemy import SQLAlchemy
from flask_heroku import Heroku
import csv

app = Flask(__name__)
app.secret_key = 'thishasbeenanafternoonofdoddingnothing'
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://localhost/local_copy'
app.config['SQLALCHEMY_ECHO'] = True
app.permanent_session_lifetime = datetime.timedelta(days=365)
#heroku = Heroku(app)
db = SQLAlchemy(app)


START_HOUR = 10
END_HOUR = 17
SLOT_DURATION_HOURS = .5
DAYS_OPEN = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
HEADER_OH_SLOTS = []
def time_to_readable(time):
    hour = str(int(time)%12 if int(time) !=12 else 12)
    min = str(int(60*(time-int(time)))).zfill(2)
    return hour+":"+min

cur_time = START_HOUR
while (cur_time < END_HOUR):
    HEADER_OH_SLOTS.append(time_to_readable(cur_time) +"-" +time_to_readable(cur_time+SLOT_DURATION_HOURS))
    cur_time+=SLOT_DURATION_HOURS
            
USER_LIST_TABLE_HEADINGS = ['Username', 'Password', 'Division', 'Standing', '# Unavail. Hours', '# Required Hours', 'Assigned Hours', 'Magic Key?']

ADMIN_USERNAME = 'admin'
ADMIN_PASSWORD = 'rosaparks1955'

OFFICE_USERNAME = 'office'
OFFICE_PASSWORD = 'sp1ndoctor'

OFFICE_SIGNIN_LOCK = False

class StatsCollection(db.Model):
    __tablename__ = "stats_collection"
    signout_time = db.Column(db.String(120), primary_key = True)
    username = db.Column(db.String(120))
    logged_time = db.Column(db.String(120))
    def __init__(self, username, signout_time, logged_time):
        self.username=username
        self.signout_time = signout_time
        self.logged_time=logged_time

class SignedInDb(db.Model):
    __tablename__ = "signed_in_db"
    username = db.Column(db.String(120), primary_key=True)
    sign_in_time = db.Column(db.Integer)

    def __init__(self, username):
        self.username=username
        cur_time = datetime.datetime.now()
        database_time = cur_time.hour + cur_time.minute/60
        self.sign_in_time = int(100*database_time)

class User(db.Model):
    __tablename__ = "users"
    
    username = db.Column(db.String(120), primary_key=True)
    password = db.Column(db.String(120))
    DEFAULT_PASSWORD = "advocate"
    name = db.Column(db.String(120))

    #see below for possible divisions
    division = db.Column(db.String(120))
    CONDUCT = "Conduct"
    ACADEMIC = "Academic"
    FIN_AID = "Financial Aid"
    GRIEVANCE = "Grievance"
    NOT_APPLICABLE = "N/A"    
    #see below for the possible types
    standing = db.Column(db.String(120))
    INACTIVE = '4. Inactive'
    NEW_HIRE = '1. New Hire'
    CASEWORKER = '2. Caseworker'
    VETERAN = '3. Veteran'

    #There are 70 office hour slots, so we have an array with 70 entries. See below for possible value of each entry
    office_hour_input = db.Column(db.ARRAY(db.String(120), dimensions = 2))
    AVAILABLE = 'available'
    PREFERRED = 'preferred'
    UNAVAILABLE = 'unavailable'

    DEFAULT_ASSIGNED_SLOTS = 7
    required_slots = db.Column(db.Integer)

    #There are 70 office hour slots, this will have the 6 assigned slots
    assigned_office_hours = db.Column(db.ARRAY(db.Integer))
    UNASSIGNED = -1

    magic_key = db.Column(db.String(120))
    DEFAULT_MAGIC_KEY = 'not set'

    def __init__(self, username, name="name"):
        self.username = username
        self.password = User.DEFAULT_PASSWORD
        self.standing = User.INACTIVE
        self.office_hour_input = [[User.AVAILABLE for _ in range(int((END_HOUR-START_HOUR)/SLOT_DURATION_HOURS))] for _ in range(len(DAYS_OPEN))]
        self.required_slots = User.DEFAULT_ASSIGNED_SLOTS
        self.assigned_office_hours = [User.UNASSIGNED for _ in range(self.required_slots)]
        self.name = name
        self.division = User.NOT_APPLICABLE
        self.magic_key = User.DEFAULT_MAGIC_KEY

#db.drop_all()
db.create_all()

def clear_user_session():
    logged_out_user = session.pop('user', None)
    if logged_out_user == OFFICE_USERNAME:
        global OFFICE_SIGNIN_LOCK
        OFFICE_SIGNIN_LOCK = False
       


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
        signed_in_list_classform = db.session.query(SignedInDb).all()
        return render_template('office.html', signed_in_users = [signed_in.username for signed_in in signed_in_list_classform])
    else:
        return automatic_logout()

@app.route('/handle_signins', methods = ['POST'])
def handle_signins():
    if session.get('user') == OFFICE_USERNAME:

        input_from_signin = request.form['username']
        input_user = None
        if db.session.query(User).filter(User.username == input_from_signin).count():
            input_user = db.session.query(User).filter(User.username == input_from_signin).one().username
        elif input_from_signin != User.DEFAULT_MAGIC_KEY and db.session.query(User).filter(User.magic_key == input_from_signin).count():
            input_user = db.session.query(User).filter(User.magic_key == input_from_signin).one().username
        
        if input_user:
            if db.session.query(SignedInDb).filter(SignedInDb.username == input_user).count():
                return redirect('/signout&=' + input_user)
            else:
                db.session.rollback()
                db.session.add(SignedInDb(input_user))
                db.session.commit()
                flash("Signed in: " + input_user)
                return redirect('/office')
        else :
            flash('Invalid Sign-In')
            return redirect('/office')
    return automatic_logout()

@app.route('/signout_all')
def signout_all():
    if session.get('user') == OFFICE_USERNAME:
        signed_in_list_classform = db.session.query(SignedInDb).all()
        for signed_in in signed_in_list_classform:
            signout(signed_in.username)
        return redirect('/office')
    return automatic_logout()


@app.route('/signout&=<username>')
def signout(username):
    if session.get('user') == OFFICE_USERNAME:

        db.session.rollback()
        signed_out = db.session.query(SignedInDb).filter(SignedInDb.username == username).one()
        db.session.query(SignedInDb).filter(SignedInDb.username == username).delete()
        cur_time = datetime.datetime.now()
        current_hour = cur_time.hour + cur_time.minute/60
        completed_hours = current_hour - signed_out.sign_in_time/100
        completed_hours_text = int(completed_hours)
        completed_minutes_text = int(60*(completed_hours - completed_hours_text))
        db.session().add(StatsCollection(username, str(cur_time), int(100*completed_hours)))
        db.session.commit()
        flash("Signed out: " + username + ", for " + str(completed_hours_text) + " hours and " + str(completed_minutes_text) + " minutes. ")
        return redirect('/office')
    return automatic_logout()

def kick_stragglers():
    db.session.query(SignedInDb).delete()
    db.session.commit()
    return redirect('/office')


@app.route('/assign_hours')
def assign_hours():
    if session.get('user') == ADMIN_USERNAME:
        db.session.rollback()
        user_list_for_html = []
        user_list_classform = db.session.query(User).all()
        slot_availibility = [[ [[],[]] for _ in HEADER_OH_SLOTS] for _ in DAYS_OPEN]
        for user in user_list_classform:
            if user.standing != User.INACTIVE:
                for i in range (len(DAYS_OPEN)):
                    for j in range (len(HEADER_OH_SLOTS)):
                        if user.office_hour_input[i][j] == User.PREFERRED:
                            slot_availibility[i][j][0].append(user.username)
                        elif user.office_hour_input[i][j] == User.AVAILABLE:
                            slot_availibility[i][j][1].append(user.username)

        return render_template('assign_hours.html', header_oh_slots = HEADER_OH_SLOTS,
                                                    days_open = DAYS_OPEN,
                                                    slot_availibility=slot_availibility)
    else:
        return automatic_logout()
    
@app.route('/add_users')
def add_users():
    if session.get('user') == ADMIN_USERNAME:
        return render_template('add_users.html')
    else:
        return automatic_logout()

@app.route('/try_adding_users', methods = ['POST'])
def try_adding_users():
    if session.get('user') == ADMIN_USERNAME:
        new_users_text = request.form['new_users_text'].strip()
        if new_users_text:
            new_users_lines = new_users_text.splitlines()
            something_to_write = False
            for username_unstripped in new_users_lines:
                username=username_unstripped.translate({ord(c): None for c in string.whitespace})
                if db.session.query(User).filter(User.username == username).count():
                    flash("<"+username_unstripped + "> already exists in the database. Nothing was written for this line.")
                elif ',' in username:
                    flash("<"+username_unstripped + "> had a comma in it - illegal formatting!")
                else:
                    user = User(username)
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
    if session.get('user') == ADMIN_USERNAME:
        db.session.rollback()
        user_list_for_html = []
        user_list_classform = db.session.query(User).all()
        for user in user_list_classform:
            num_unavailable_hours = 0
            for i in range (len (user.office_hour_input)):
                for j in range (len (user.office_hour_input[i])):
                    if user.office_hour_input[i][j] == User.UNAVAILABLE:
                        num_unavailable_hours+=1
            office_hour_assignments = 'not yet assigned' if -1 in user.assigned_office_hours else 'coming soon'
            user_list_for_html.append([user.username, user.password, user.division, user.standing, num_unavailable_hours, user.required_slots*SLOT_DURATION_HOURS, office_hour_assignments, user.magic_key])
        print(user_list_for_html)
        return render_template('user_list.html', table_headings = USER_LIST_TABLE_HEADINGS, user_list = user_list_for_html, default_password = User.DEFAULT_PASSWORD)
    else:
        return automatic_logout()

@app.route('/try_deleting_users', methods = ['POST'])
def try_deleting_users():
    if session.get('user') == ADMIN_USERNAME:
        selected = request.form.getlist('users_to_delete')
        deleted_string = ''
        db.session.rollback()
        for username in selected :
            deleted_string += username + ", "
            db.session.query(User).filter(User.username == username).delete()
            db.session.commit()
        if selected:
            flash("Successfully deleted: " + deleted_string[:-2])
        return redirect('/user_list')
    return automatic_logout()

@app.route('/reset_system')
def reset_system():
    if session.get('user') == ADMIN_USERNAME:
        return render_template('reset_system.html')
    return automatic_logout()

@app.route('/try_reset', methods = ['POST'])
def try_reset():
    if session.get('user') == ADMIN_USERNAME:
        username = request.form['username']
        password = request.form['password']
        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            StatsCollection.__table__.drop(db.engine)
            StatsCollection.__table__.create(db.engine)
            flash("System has been reset!")
        else:
            flash ("Invalid Credentials! Also think again.")
        return redirect('/reset_system')
    return automatic_logout()

@app.route('/user&=<username>')
def user_page(username):
    if (session.get('user') == username or session.get('user') == ADMIN_USERNAME) and db.session.query(User).filter(User.username == username).count():
        return render_template('user_page.html', username=username, num_required_hours=db.session.query(User).filter(User.username == username).one().required_slots*SLOT_DURATION_HOURS, admin = session.get('user') == ADMIN_USERNAME)
    return automatic_logout()

@app.route('/change_password&=<username>')
def change_password(username):
    if session.get('user') == username or session.get('user') == ADMIN_USERNAME:
        return render_template('change_password.html', username=username, admin = session.get('user') == ADMIN_USERNAME)
    return automatic_logout()

@app.route('/try_resetting_password&=<username>')
def try_resetting_password(username):
    if (session.get('user') == username or session.get('user') == ADMIN_USERNAME) and db.session.query(User).filter(User.username == username).count():
        db.session.rollback()
        db.session.query(User).filter(User.username == username).one().password = User.DEFAULT_PASSWORD
        db.session.commit()
        flash ("Successfuly reset <" + username + "> password")
    return redirect('/user_list')


@app.route('/try_changing_password&=<username>', methods = ['POST'])
def try_changing_password(username):
    if session.get('user') == username or session.get('user') == ADMIN_USERNAME:
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

@app.route('/set_magic_key&=<username>')
def set_magic_key(username):
    if session.get('user') == username or session.get('user') == ADMIN_USERNAME:
        return render_template('set_magic_key.html', username=username, admin = session.get('user') == ADMIN_USERNAME)
    return automatic_logout()

@app.route('/try_setting_magic_key&=<username>', methods = ['POST'])
def try_setting_magic_key(username):
    if (session.get('user') == username or session.get('user') == ADMIN_USERNAME) and db.session.query(User).filter(User.username == username).count():
        db.session.query(User).filter(User.username == username).one().magic_key = request.form['magic_key']
        db.session.commit()
        flash ("Successfully set Magic Key!")
        return redirect("/set_magic_key&=" + username)
    return automatic_logout()

@app.route('/edit_required_hours&=<username>')
def edit_required_hours(username):
    if (session.get('user') == ADMIN_USERNAME) and db.session.query(User).filter(User.username == username).count():
        return render_template('edit_required_hours.html', username = username, 
                                                            current_slot_duration = SLOT_DURATION_HOURS,
                                                            current_required_hours = db.session.query(User).filter(User.username == username).one().required_slots*SLOT_DURATION_HOURS)
    return automatic_logout()

@app.route('/try_editing_required_hours&=<username>', methods = ['POST'])
def try_editing_required_hours(username):
    if (session.get('user') == ADMIN_USERNAME) and db.session.query(User).filter(User.username == username).count():
        new_slots = float(request.form['required_hours'])/SLOT_DURATION_HOURS
        if int (new_slots) == new_slots:
            db.session.query(User).filter(User.username == username).one().required_slots = new_slots 
            db.session.commit()
            flash ("Successfully edited required hours!")
        else :
            flash ("Required hour must be an integer multiple of slot duration!")
        return redirect("/edit_required_hours&=" + username)
    return automatic_logout()

@app.route('/edit_profile&=<username>')
def edit_profile(username):
    if (session.get('user') == username or session.get('user') == ADMIN_USERNAME) and db.session.query(User).filter(User.username == username).count():
        cur_user = db.session.query(User).filter(User.username == username).one()
        radio_preferencebox_order = [User.UNAVAILABLE, User.AVAILABLE, User.PREFERRED]
        radio_preferencebox_settings = [[['checked' if user_selection == selection  else '' for selection in radio_preferencebox_order] for user_selection in row_input] for row_input in cur_user.office_hour_input]
        radio_standing_order = [User.NEW_HIRE, User.CASEWORKER, User.VETERAN, User.INACTIVE]
        radio_standing = ['checked' if cur_user.standing == standing else '' for standing in radio_standing_order]
        radio_division_order = [User.CONDUCT, User.GRIEVANCE, User.ACADEMIC, User.FIN_AID, User.NOT_APPLICABLE]
        radio_division = ['checked' if cur_user.division == division else '' for division in radio_division_order]
    
        return render_template('edit_profile.html', username=username, 
                                                    num_slots_required = cur_user.required_slots,
                                                    header_oh_slots = HEADER_OH_SLOTS,
                                                    days_open = DAYS_OPEN,
                                                    radio_preferencebox_order=radio_preferencebox_order,
                                                    radio_preferencebox_settings=radio_preferencebox_settings,
                                                    radio_standing_order=radio_standing_order, 
                                                    radio_standing=radio_standing, 
                                                    radio_division_order=radio_division_order, 
                                                    radio_division=radio_division,
                                                    admin = session.get('user') == ADMIN_USERNAME)
    return automatic_logout()

@app.route('/try_editing_profile&=<username>', methods = ['POST'])
def try_editing_profile(username):
    if session.get('user') == username or session.get('user') == ADMIN_USERNAME:
        if db.session.query(User).filter(User.username == username).count():
            db.session.rollback()
            cur_user = db.session.query(User).filter(User.username == username).one()
            new_inputs = [['' for input in row_input] for row_input in cur_user.office_hour_input]
            for i in range (len(cur_user.office_hour_input)):
                for j in range (len(cur_user.office_hour_input[i])):
                    new_inputs[i][j] = request.form['preference'+ str(i) + '-' + str(j)]
            cur_user.office_hour_input = new_inputs
            cur_user.standing = request.form['standing']
            cur_user.division = request.form['division']
            db.session.commit()
            flash("Successfully Saved!")
        return redirect("/edit_profile&=" + username)
    return automatic_logout()

@app.route('/')
def home():
    if session.get('user') != OFFICE_USERNAME:
        return render_template('login_form.html')
    else:
        return render_template('office_logged_in.html')


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
        global OFFICE_SIGNIN_LOCK
        if OFFICE_SIGNIN_LOCK:
            redirect_url = '/'
        else :
            OFFICE_SIGNIN_LOCK = True
            redirect_url = '/office'
    elif db.session.query(User).filter(User.username == username).count() and db.session.query(User).filter(User.username == username).one().password == password:
        good_login = True
        redirect_url = '/user&='+username
    if good_login:
        session['user'] = username
    else:
        flash ("Invalid Credentials!")
    return redirect(redirect_url)

@app.route('/logout')
def logout():
    clear_user_session()
    return redirect('/')


if __name__ == '__main__':
    app.run()
