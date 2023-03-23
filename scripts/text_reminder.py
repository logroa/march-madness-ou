import os
import sys
import psycopg2
from dotenv import load_dotenv

current = os.path.dirname(os.path.realpath(__file__))
parent = os.path.dirname(current)
sys.path.append(parent)

from messager import Texter

load_dotenv()

DB_USERNAME = os.getenv('DB_USERNAME')
DB_PASSWORD = os.getenv('DB_PASSWORD') 
DB_PORT = os.getenv('DB_PORT')
DB_NAME = os.getenv('DB_NAME')
DB_ENDPOINT = os.getenv('DB_ENDPOINT')
conn = psycopg2.connect(
    host=DB_ENDPOINT,
    database=DB_NAME,
    user=DB_USERNAME,
    password=DB_PASSWORD
)
API_URL = os.getenv('API_URL')

texter = Texter()

cur = conn.cursor()
cur.execute('''select handle, phone_number from players;''')
people = cur.fetchall()
for person in people:
    name, number = person
    better_number = number.replace('-', '')
    texter.send_text(f'''Yo {name}, don't forget to fill out your over under picks for today and tomorrow's Sweet 16 matchups.
                        \n\n
                        https://march-madness-overunders.herokuapp.com/''', better_number)