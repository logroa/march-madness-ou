import os
import requests
import json
import urllib.parse
import flask
from flask import Flask, render_template, request, redirect, jsonify, flash, url_for, session
import psycopg2
from dotenv import load_dotenv
import hashlib
import uuid
from functools import wraps
from datetime import datetime
from difflib import SequenceMatcher
from messager import Texter

# jsut src for team pics prob
# still need to do that manually

# scoring - 1, 2, 4, ...
# but also streaks incur extra points
# 2 in a row -> + 1
# 3 in a row -> + 2
# ...

# put a bunch of weird photos on it, make the ux laughable

###############################################################
########################## SET UP #############################
###############################################################

app = Flask(__name__)
app.secret_key = 'logan'
load_dotenv()

DB_USERNAME = os.getenv('DB_USERNAME')
DB_PASSWORD = os.getenv('DB_PASSWORD') 
DB_PORT = os.getenv('DB_PORT')
DB_NAME = os.getenv('DB_NAME')
DB_ENDPOINT = os.getenv('DB_ENDPOINT')

API_URL = os.getenv('API_URL')

try:
    db_conn = psycopg2.connect(
        database=DB_NAME,
        user=DB_USERNAME,
        password=DB_PASSWORD,
        host=DB_ENDPOINT,
        port=DB_PORT
    )
    print("Successful DB connection.")
except:
    print("DB connection failed")
    exit(1)

texter = Texter()

###############################################################
########################## HELPERS ############################
###############################################################

def find_user(id, username=None):
    cur = db_conn.cursor()
    query = "SELECT * FROM players WHERE "

    if username:
        username = username.replace("'", "''")
        query += f"handle = '{username}';"
    else:
        query += f"id = {id};"

    cur.execute(query)
    return cur.fetchone()


def insert_user(og_handle, pw, number):
    cur = db_conn.cursor()
    handle = og_handle.replace("'", "''")
    pw = generate_password(pw)
    phone_number = number.replace("'", "")
    cur.execute(f'''
        INSERT INTO players (handle, pw, phone_number, confirmed, paid) VALUES ('{handle}', '{pw}', '{phone_number}', False, False);
    ''')
    db_conn.commit()
    print(f'{og_handle} registered.')

    user_id = find_user(0, handle)[0]
    texter.send_text(f'''Click the link below to verify this phone number for {handle} 
                      for March Madness OverUnders. \n\n
                      {API_URL}/confirm/{user_id}''', phone_number)

    return user_id


def confirm_user(user_id):
    query = f'''UPDATE players SET confirmed = True WHERE id = {user_id}'''
    cur = db_conn.cursor()
    cur.execute(query)
    db_conn.commit()
    cur.execute(f'''SELECT * FROM players WHERE id = {user_id}''')
    return cur.fetchone()


def generate_password(password):
    algorithm = 'sha512'
    salt = uuid.uuid4().hex
    hash_obj = hashlib.new(algorithm)
    password_salted = salt + password
    hash_obj.update(password_salted.encode('utf-8'))
    password_hash = hash_obj.hexdigest()
    password_db_string = "$".join([algorithm, salt, password_hash])
    print("A", algorithm)
    print("B", salt)
    print("C", password_salted)
    print("D", password_hash)
    return password_db_string


def check_password(password, password_db_string):
    [algorithm, salt, password_hash] = password_db_string.split("$")
    hash_obj = hashlib.new(algorithm)
    password_salted = salt + password
    hash_obj.update(password_salted.encode('utf-8'))
    print("E", algorithm)
    print("F", salt)
    print("G", password_salted)
    print("H", hash_obj.hexdigest())
    return hash_obj.hexdigest() == password_hash


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        print("Checking user...")
        if 'user' not in session:
            return redirect(url_for('validate'))

        return f(*args, **kwargs)
    return decorated_function


def admin_login_required(f):
    @wraps(f)
    def admin_decorated_function(*args, **kwargs):
        print("Checking admin user...")
        if 'user' not in session:
            return redirect(url_for('validate'))

        id = find_user(0, session['user'])[0]
        if id != 1:
            return redirect(url_for('validate'))
        
        return f(*args, **kwargs)
    return admin_decorated_function


###############################################################
############################ API ##############################
###############################################################

@app.route('/', methods=['GET'])
@login_required
def index():
    return render_template('play.html', username=session['user'])


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        handle = request.form['handle']
        user = find_user(0, handle)
        if not user:   
            code = request.form['pw']
            number = request.form['number']
            id = insert_user(handle, code, number)
            session['user'] = handle
            print(f"Registration for '{handle}' complete.")

            return redirect(url_for('index'))

        return render_template('register.html', message="Username already taken.")
    
    return render_template('register.html')


@app.route('/validate', methods=['GET', 'POST'])
def validate():
    if request.method == 'POST':
        handle = request.form['handle']
        code = request.form['pw']
        me = find_user(0, handle)

        if not me or me[0] == None or not check_password(code, me[2]):
            return render_template('validate.html', message='Incorrect login.')

        session['user'] = me[1]

        return redirect(url_for('index'))

    return render_template('validate.html')


@app.route('/logout', methods=['POST'])
@login_required
def logout():
    print(f"Logging {session['user']} out.")
    session.clear()
    return redirect(url_for('validate'))

@app.route('/confirm/<id>', methods=['GET'])
def confirm(id):
    user = confirm_user(id)
    return render_template('confirmation.html', username=user[1])


if __name__ == '__main__':
    app.run()