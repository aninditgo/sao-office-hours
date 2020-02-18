import os, datetime, string 
from flask import Flask, render_template, request, redirect, flash, session
from flask_sqlalchemy import SQLAlchemy
from flask_heroku import Heroku
from ortools.sat.python import cp_model
import csv

app = Flask(__name__)
app.secret_key = 'thishasbeenanafternoonofdoddingnothing'
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://localhost/local_copy'
#app.config['SQLALCHEMY_ECHO'] = True
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

TOTAL_SLOTS = len(HEADER_OH_SLOTS) * len(DAYS_OPEN)
MIN_PER_SLOT = 3
MAX_PER_SLOT = 6
MIN_EXPERIENCED_PER_SLOT = 2
WEIGHT_VETERAN = 6
WEIGHT_NORMAL = 7
TIMEOUT_SECONDS = 30
AVAILABLE_SLOTS_THRESHOLD = 50
            
USER_LIST_TABLE_HEADINGS = ['Username', 'Password', 'Division', 'Standing', '# Unavail. Hours', '# Required Hours', 'Assigned Hours', 'Magic Key?']

ADMIN_USERNAME = 'admin'
ADMIN_PASSWORD = 'rosaparks1955'

OFFICE_USERNAME = 'office'
OFFICE_PASSWORD = 'sp1ndoctor'

OFFICE_SIGNIN_LOCK = False
serverside_session = {}

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
        user_list_classform = db.session.query(User).all()
        slot_availibility = [[ [[],[]] for _ in HEADER_OH_SLOTS] for _ in DAYS_OPEN]
        currently_assigned_hours = [[[] for _ in range (len(HEADER_OH_SLOTS))] for _ in range (len(DAYS_OPEN))]
        for user in user_list_classform: 
            if user.standing != User.INACTIVE:
                if sum(user.assigned_office_hours) != -1 * len(user.assigned_office_hours):
                    for assigned_hour in user.assigned_office_hours:
                        currently_assigned_hours[assigned_hour//len(HEADER_OH_SLOTS)][assigned_hour%len(HEADER_OH_SLOTS)].append(user.username)
                for i in range (len(DAYS_OPEN)):
                    for j in range (len(HEADER_OH_SLOTS)):
                        if user.office_hour_input[i][j] == User.PREFERRED:
                            slot_availibility[i][j][0].append(user.username)
                        elif user.office_hour_input[i][j] == User.AVAILABLE:
                            slot_availibility[i][j][1].append(user.username)
        generated_solution = serverside_session.pop('generated_solution', None)
        
        if not generated_solution:
            generated_solution = currently_assigned_hours
            

        return render_template('assign_hours.html', header_oh_slots = HEADER_OH_SLOTS,
                                                    days_open = DAYS_OPEN,
                                                    slot_availibility=slot_availibility,
                                                    min_per_slot = MIN_PER_SLOT,
                                                    max_per_slot = MAX_PER_SLOT,
                                                    timeout_seconds = TIMEOUT_SECONDS,
                                                    weight_normal = WEIGHT_NORMAL,
                                                    weight_veteran = WEIGHT_VETERAN,
                                                    min_experienced_per_slot = MIN_EXPERIENCED_PER_SLOT,
                                                    available_slots_threshold = AVAILABLE_SLOTS_THRESHOLD,
                                                    generated_solution = generated_solution)
    else:
        return automatic_logout()

@app.route('/try_updating_constraints', methods = ['POST'])
def try_updating_constraints():
    if session.get('user') == ADMIN_USERNAME:
        global MIN_PER_SLOT
        MIN_PER_SLOT = int(request.form['min_per_slot'].strip())
        global MAX_PER_SLOT
        MAX_PER_SLOT = int(request.form['max_per_slot'].strip())
        global MIN_EXPERIENCED_PER_SLOT
        MIN_EXPERIENCED_PER_SLOT = int(request.form['min_experienced_per_slot'].strip())
        global WEIGHT_VETERAN
        WEIGHT_VETERAN = int(request.form['weight_veteran'].strip())
        global WEIGHT_NORMAL
        WEIGHT_NORMAL = int(request.form['weight_normal'].strip())
        global TIMEOUT_SECONDS
        TIMEOUT_SECONDS = int(request.form['timeout_seconds'].strip())
        flash("Successfully Updated Constraints")
        global AVAILABLE_SLOTS_THRESHOLD
        AVAILABLE_SLOTS_THRESHOLD = int(request.form['available_slots_threshold'].strip())
        return redirect('/assign_hours')
    return automatic_logout()

@app.route('/try_assigning_hours', methods = ['POST'])
def try_assigning_hours():
    if session.get('user') == ADMIN_USERNAME:
        db.session.rollback()
        user_list_classform = db.session.query(User).all()
        username_list = set({})
        for user in user_list_classform:
            username_list.add(user.username)
        print(username_list)

        generated_solution = [[[] for _ in range (len(HEADER_OH_SLOTS))] for _ in range (len(DAYS_OPEN))]
        for i in range (len(DAYS_OPEN)):
            for j in range (len (HEADER_OH_SLOTS)):
                prelim = request.form[str(i)+'-'+str(j)].strip().split(',')
                generated_solution[i][j] = [username.strip() for username in prelim if username]
        serverside_session['generated_solution'] = generated_solution     

        assigned_hours_dictionary = {}
        for i in range (len(DAYS_OPEN)):
            for j in range (len(HEADER_OH_SLOTS)):
                for username in generated_solution[i][j]:
                    if username in username_list:
                        if username not in assigned_hours_dictionary:
                            assigned_hours_dictionary[username] = []
                        assigned_hours_dictionary[username].append(i*len(HEADER_OH_SLOTS) + j)
                    else:
                        flash ("There was a formatting error in the " + str(i) + ", " + str(j) + " cell. " + username + " is not a valid username")
                        return redirect('/assign_hours')
        for user in user_list_classform:
            if user.username in assigned_hours_dictionary:
                user.assigned_office_hours = assigned_hours_dictionary[user.username]
        db.session.commit()
        flash ("Succesfully wrote assignments to the database")
        return redirect('/assign_hours')
    return automatic_logout()
    

@app.route('/try_finding_solution', methods = ['POST'])
def solve_hard_constraints():
    def helper_find_num_unavailibe_hours(office_hour_input):
        num_unavailable_hours = 0
        for i in range (len (office_hour_input)):
            for j in range (len (office_hour_input[i])):
                if office_hour_input[i][j] == User.UNAVAILABLE:
                    num_unavailable_hours+=1
        return num_unavailable_hours
    if session.get('user') == ADMIN_USERNAME:
        model = cp_model.CpModel()

        db.session.rollback()
        user_list_classform = db.session.query(User).all()          
        user_variable_lists = [[(model.NewBoolVar('%s-%d' % (user.username, i)), user.office_hour_input[i//len(HEADER_OH_SLOTS)][i%len(HEADER_OH_SLOTS)]) 
                                    for i in range (TOTAL_SLOTS)] + [helper_find_num_unavailibe_hours(user.office_hour_input), user.username, user.standing, user.required_slots]
                                    for user in user_list_classform 
                                    if user.standing != User.INACTIVE]
       
        for i in range (TOTAL_SLOTS):
            model.Add(sum([user_variable_list[i][0] for user_variable_list in user_variable_lists]) >= MIN_PER_SLOT)
            model.Add(sum([user_variable_list[i][0] for user_variable_list in user_variable_lists]) <= MAX_PER_SLOT)
            model.Add(sum([user_variable_list[i][0] for user_variable_list in user_variable_lists if user_variable_list[-2] != User.NEW_HIRE]) >= MIN_EXPERIENCED_PER_SLOT)
        
        for user_variable_list in user_variable_lists:
            if user_variable_list[-4] < AVAILABLE_SLOTS_THRESHOLD:
                for i in range (len(DAYS_OPEN)):
                    flattened_index_base = i*len(HEADER_OH_SLOTS)
                    print (user_variable_list[-3])
                    model.Add(user_variable_list[flattened_index_base][0] <= user_variable_list[flattened_index_base+1][0])
                    model.Add(user_variable_list[flattened_index_base+len(HEADER_OH_SLOTS)-1][0] <= user_variable_list[flattened_index_base+len(HEADER_OH_SLOTS)-2][0])
                    for j in range (1,len(HEADER_OH_SLOTS)-1):
                        cur_index = flattened_index_base + j
                        model.Add(user_variable_list[cur_index][0] <= user_variable_list[cur_index-1][0] + user_variable_list[cur_index+1][0])
                


        for user_variable_list in user_variable_lists:
            model.Add(sum([user_variable_list[i][0] for i in range(TOTAL_SLOTS)]) == user_variable_list[-1])
            for i in range(TOTAL_SLOTS):
                if user_variable_list[i][1] == User.UNAVAILABLE:
                    model.Add(user_variable_list[i][0] == 0)
        
        equation = 0
        for user_variable_list in user_variable_lists:
            weight = WEIGHT_VETERAN if user_variable_list[-2] == User.VETERAN else WEIGHT_NORMAL
            for i in range (TOTAL_SLOTS):
                if user_variable_list[i][1] == User.PREFERRED:
                    equation += weight*user_variable_list[i][0]
        model.Minimize(equation)
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = TIMEOUT_SECONDS
        status = solver.Solve(model)
        
        if status == cp_model.FEASIBLE or status == cp_model.OPTIMAL:
            generated_solution = [[[] for _ in range (len(HEADER_OH_SLOTS))] for _ in range (len(DAYS_OPEN))]

            for user_variable_list in user_variable_lists:
                for i in range (TOTAL_SLOTS):
                    if solver.Value(user_variable_list[i][0])==1:
                        generated_solution[i//len(HEADER_OH_SLOTS)][i%len(HEADER_OH_SLOTS)].append(user_variable_list[-3])
            serverside_session['generated_solution'] = generated_solution     

        else: 
            flash ("There was no valid solution - try relaxing the constraints!")
        return redirect('/assign_hours')
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
        cur_user = db.session.query(User).filter(User.username == username).one()
        assigned_shifts = []
        if sum(cur_user.assigned_office_hours) > 0:
            start, last = -1, -1
            for assigned_slot in cur_user.assigned_office_hours:
                assigned_shifts.append(DAYS_OPEN[assigned_slot//len(HEADER_OH_SLOTS)] + ": " + time_to_readable(START_HOUR + (assigned_slot%len(HEADER_OH_SLOTS)) * SLOT_DURATION_HOURS) + '-' + time_to_readable(START_HOUR + (assigned_slot%len(HEADER_OH_SLOTS)+1) * SLOT_DURATION_HOURS))

        return render_template('user_page.html', username=username, num_required_hours=cur_user.required_slots*SLOT_DURATION_HOURS, admin = session.get('user') == ADMIN_USERNAME, assigned_shifts=assigned_shifts)
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
