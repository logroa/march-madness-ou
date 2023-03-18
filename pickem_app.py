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

DEBUG = os.getenv('DEBUG')

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

num_2_round = {
    1: "Round of 64",
    2: "Round of 32",
    3: "Sweet 16",
    4: "Elite 8",
    5: "Final 4",
    6: "Championship"
}

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


def get_games():
    query = f'''SELECT g.id, g.day_order, g.round, g.date_played, g.team1, t1.team_name as t1name, t1.seed as t1seed, g.team1score,
                t2.team_name as t2name, t2.seed as t2seed, g.team2score, g.overunder, g.started, g.finished, g.overhit
                FROM games g 
                INNER JOIN teams t1 ON g.team1 = t1.id 
                INNER JOIN teams t2 ON g.team2 = t2.id 
                ORDER BY g.round DESC, g.date_played, g.day_order;'''
    cur = db_conn.cursor()
    cur.execute(query)
    rows = cur.fetchall()
    games = [
        {
            "id": dr[0],
            "day_order": dr[1],
            "round": dr[2],
            "date_played": f"{dr[3][:4]}-{dr[3][4:6]}-{dr[3][6:]}",
            "team1": dr[4],
            "t1name": dr[5],
            "t1seed": dr[6],
            "team1score": dr[7],
            "t2name": dr[8],
            "t2seed": dr[9],
            "team2score": dr[10],
            "overunder": dr[11],
            "started": dr[12],
            "finished": dr[13],
            "overhit": dr[14]
        } for dr in rows
    ]
    return games


def get_user_picks(games, user_id):
    cur = db_conn.cursor()
    cur.execute(f'''SELECT game_id, over_picked FROM picks WHERE player_id = {user_id};''')
    picks = cur.fetchall()
    for pick in picks:
        for i in range(len(games)):
            if games[i]['id'] == pick[0]:
                games[i]['over_picked'] = pick[1]
    return games


def get_orged(games):
    orged = []
    layer = {
        "round_name": num_2_round[games[0]["round"]],
        "dates": [
            {
                "date": games[0]["date_played"],
                "games": [games[0]]
            }
        ]
    }
    for g in games[1:]:
        if layer["round_name"] == num_2_round[g["round"]]:
            if layer["dates"][-1]["date"] == g["date_played"]:
                layer["dates"][-1]["games"].append(g)
            else:
                layer["dates"].append(
                    {
                        "date": g["date_played"],
                        "games": [g]
                    }
                )
        else:
            orged.append(layer)
            layer = {
                "round_name": num_2_round[g["round"]],
                "dates": [
                    {
                        "date": g["date_played"],
                        "games": [g]
                    }
                ]
            }
    orged.append(layer)
    return orged


def insert_picks(picks, user_id):
    cur = db_conn.cursor()
    for pick in picks:
        if pick[1]:
            cur.execute(f'''SELECT COUNT(1) FROM picks WHERE player_id = {user_id} AND game_id = {pick[0]};''')
            res = cur.fetchone()
            over = True
            if pick[1] == 'U':
                over = False
            if res[0]:
                # update
                cur.execute(f'''UPDATE picks SET over_picked = {over} WHERE player_id = {user_id} AND game_id = {pick[0]};''')
            else:
                # insert
                cur.execute(f'''INSERT INTO picks (player_id, game_id, over_picked) VALUES ({user_id}, {pick[0]}, {over});''')
            db_conn.commit()


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

    games = get_games()
    user_games = get_user_picks(games, find_user(0, session['user'])[0])
    orged = get_orged(user_games)    
    return render_template('play.html', username=session['user'], orged = orged)


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


@app.route('/makepicks', methods=['POST'])
@login_required
def make_picks():
    game_ids = [g['id'] for g in get_games()]
    picks = []
    for id in game_ids:
        try:
            pick = request.form[str(id)]
        except:
            pick = None
        picks.append((id, pick))

    user_id = find_user(0, session['user'])[0]
    insert_picks(picks, user_id)
    
    return redirect(url_for('index'))


@app.route('/leaderboard', methods=['GET'])
@login_required
def leaderbaord():
    pass


if __name__ == '__main__':
    app.run(
        debug=DEBUG
    )