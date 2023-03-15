import os
import requests
import json
import urllib.parse
import pafy
import flask
from flask import Flask, render_template, request, redirect, jsonify, flash, url_for, session
import psycopg2
from dotenv import load_dotenv
import boto3
import hashlib
import uuid
from functools import wraps
from datetime import datetime
from difflib import SequenceMatcher

# jsut src for team pics prob
# still need to do that manually

# scoring - 1, 2, 4, ...
# but also streaks incur extra points
# 2 in a row -> + 1
# 3 in a row -> + 2
# ...

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


def insert_user(og_handle, pw):
    cur = db_conn.cursor()
    handle = og_handle.replace("'", "''")
    pw = generate_password(pw)
    cur.execute(f'''
        INSERT INTO players (handle, pw) VALUES ('{handle}', '{pw}');
    ''')
    db_conn.commit()
    print(f'{og_handle} registered.')
    return find_user(0, handle)[0]


def generate_password(password):
    algorithm = 'sha512'
    salt = uuid.uuid4().hex
    hash_obj = hashlib.new(algorithm)
    password_salted = salt + password
    hash_obj.update(password_salted.encode('utf-8'))
    password_hash = hash_obj.hexdigest()
    password_db_string = "$".join([algorithm, salt, password_hash])
    return password_db_string


def check_password(password, password_db_string):
    [algorithm, salt, password_hash] = password_db_string.split("$")
    hash_obj = hashlib.new(algorithm)
    password_salted = salt + password
    hash_obj.update(password_salted.encode('utf-8'))
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
    return render_template('play.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        handle = request.form['handle']
        user = find_user(0, handle)
        if not user:   
            ip = request.remote_addr
            code = request.form['code']
            generated_code = generate_password(code)
            id = insert_user(handle, generated_code)
            session['user'] = handle
            remove_machine_registration(ip)
            insert_machine_registration(ip, id)
            print(f"Registration for '{handle}' complete.")

            return redirect(url_for('index'))

        return render_template('register.html', message="Username already taken.")
    
    return render_template('register.html')


@app.route('/validate', methods=['GET', 'POST'])
def validate():
    if request.method == 'POST':
        handle = request.form['handle']
        code = request.form['code']
        ip = request.remote_addr
        me = find_user(0, handle)

        if me[0] == None or not check_password(code, me[2]):
            return render_template('validate.html', message='Incorrect login.')

        session['user'] = me[1]

        found_id = find_ip(ip)
        if not found_id:
            insert_machine_registration(ip, me[0])
        elif found_id != me[0]:
            remove_machine_registration(ip)
            insert_machine_registration(ip, me[0])

        return redirect(url_for('index'))

    return render_template('validate.html')


@app.route('/logout', methods=['POST'])
@login_required
def logout():
    session.clear()
    return redirect(url_for('validate'))