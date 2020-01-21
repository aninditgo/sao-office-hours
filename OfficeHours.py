import os, datetime
from flask import Flask, render_template, request, redirect, flash, session

app = Flask(__name__)
app.permanent_session_lifetime = datetime.timedelta(days=14)

ADMIN_USERNAME = 'admin'
ADMIN_PASSWORD = 'rosaparks1955'

OFFICE_USERNAME = 'office'
OFFICE_PASSWORD = 'sp1ndoctor'

def clear_user_session():
    session.pop('user')

def automatic_logout():
    flash("Sorry, you have either logged out or have logged into another account.")
    return redirect('/')

@app.route('/')
def home():
    return render_template('login_form.html')

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