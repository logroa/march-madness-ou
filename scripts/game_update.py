import os
import requests
from bs4 import BeautifulSoup
import re
import psycopg2
from dotenv import load_dotenv

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

DAYS_2_ROUND = {
    '20230316': 'Round of 64',
    '20230317': 'Round of 64',
    '20230318': 'Round of 32',
    '20230319': 'Round of 32'
}

# edge cases for not started games, games in progress, and finished games
# get o/u from here too
def request_page(date):
    base_url = f"https://www.espn.com/mens-college-basketball/scoreboard/_/date/{date}"
    page_raw = requests.get(base_url)
    page = BeautifulSoup(page_raw.content, 'html.parser')
    scoreboards = page.find_all('section', class_='Scoreboard')
    results = []
    for sb in scoreboards:
        game = {}
        count = 1
        lis = sb.find_all('li')
        game['id'] = sb.attrs['id']
        game['done'] = False
        for team in lis:
            pic = team.find('img')
            # print(pic)
            # print(pic.attrs['src'])
            seed = team.find('div', class_='ScoreCell__Rank').text
            team_name = team.find('div', class_='ScoreCell__TeamName').text
            # games that have yet to start
            try:
                score = team.find('div', class_='ScoreCell__Score').text
            except:
                score = "0"

            game[f'team{count}'] = team_name
            game[f'team{count}score'] = score
            game[f'team{count}seed'] = seed
            count += 1

        game_info = sb.find_all('div', class_='ScoreCell__Time') + sb.find_all('div', class_='ScoreCell__Network')

        try:
            ou = sb.find('div', class_='Odds__Message').text.split()[-1]
        except:
            ou = "0"
        game['overunder'] = ou

        if len(game_info) == 1:
            game['done'] = True
        results.append(game)

    return results


def check_exists(table, column, value):
    query = f'''SELECT COUNT(1) FROM {table} WHERE {column}='''
    if type(value) == str:
        query += f"'{value}';"
    else:
        query += f"{value};"

    cur = conn.cursor()
    cur.execute(query)
    res = cur.fetchone()
    return True if res[0] else False


def get_prim_key(prim_key_column, table, column, value):
    query = f'''SELECT {prim_key_column} FROM {table} WHERE {column} = '''
    if type(value) == str:
        query += f"'{value}';"
    else:
        query += f"{value};"
    cur = conn.cursor()
    cur.execute(query)
    res = cur.fetchone()
    return res[0] if res[0] else None


def insert_into(table, data):
    query = f"INSERT INTO {table} "
    cols = ""
    vals = ""
    for k in data.keys():
        cols += f'{k}, '
        if type(data[k]) == str:
            vals += f"'{data[k]}', "
        else:
            vals += f"{data[k]}, "
    cols = cols[:-2]
    vals = vals[:-2]
    query += f"({cols}) VALUES ({vals});"
    cur = conn.cursor()
    cur.execute(query)
    conn.commit()


def update_please(table, data, column, value):
    query = f"UPDATE {table} SET "
    for k in data.keys():
        query += f"{k} = "
        if type(data[k]) == str:
            query += f"'{data[k]}', "
        else:
            query += f"{data[k]}, "
    query = query[:-2] + " "
    query += f"WHERE {column} = "
    if type(value) == str:
        query += f"'{value}';"
    else:
        query += f"{value};"
    cur = conn.cursor()
    cur.execute(query)
    conn.commit()


# don't change o/u if game is alredy in DB
def db_cron(date):
    games = request_page(date)
    for game in games:
        id = int(game['id'])
        if not check_exists('games', 'id', id):
            if not check_exists('teams', 'team_name', game['team1']):
                insert_into(
                    'teams',
                    {
                        'team_name': game['team1'],
                        'seed': game['team1seed'],
                        'team_pic': ''
                    }
                )
            if not check_exists('teams', 'team_name', game['team2']):
                insert_into(
                    'teams',
                    {
                        'team_name': game['team2'],
                        'seed': game['team2seed'],
                        'team_pic': ''
                    }
                )
            team1id = get_prim_key('id', 'teams', 'team_name', game['team1'])
            team2id = get_prim_key('id', 'teams', 'team_name', game['team2'])
            insert_into(
                'games',
                {
                    'id': id,
                    'round': DAYS_2_ROUND[date],
                    'date_played': date,
                    'team1': team1id,
                    'team2': team2id,
                    'team1score': int(game['team1score']),
                    'team2score': int(game['team2score']),
                    'overunder': float(game['overunder']),
                    'started': False,
                    'finished': False
                }
            )
        else:
            started = False
            if int(game['team1score']) > 0 or int(game['team2score']) > 0:
                started = True
            update_please(
                'games',
                {
                    'team1score': int(game['team1score']),
                    'team2score': int(game['team2score']),
                    'started': started,
                    'finished': game['done']
                },
                'id',
                id
            )


db_cron("20230316")