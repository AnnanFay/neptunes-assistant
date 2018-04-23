import requests
import os
import bmemcached    
import praw
import html
from pprint import pprint

BASE_DOMAIN = 'https://np.ironhelmet.com'
url = BASE_DOMAIN + '/mrequest/open_games'
data = {'type': 'open_games'}
already_posted_key = 'POSTED'

# flair IDs

open_id = '40ac6e5e-4701-11e8-bd80-0e491115009a'
closed_id = '109d87bc-4674-11e8-a30b-0eed8597e7ae'

def get_npsub():
    username = os.environ['REDDIT_USERNAME']
    password = os.environ['REDDIT_PASSWORD']

    reddit = praw.Reddit(client_id='**************',
                         client_secret='***************************',
                         password=password,
                         username=username,
                         user_agent='neptunes-assistant bot by /u/AnnanFay')

    print('Me:', reddit.user.me())

    npsub = reddit.subreddit('neptunespride')
    return npsub

def get_mc():
    mc = bmemcached.Client(
        os.environ.get('MEMCACHEDCLOUD_SERVERS').split(','),
        os.environ.get('MEMCACHEDCLOUD_USERNAME'),
        os.environ.get('MEMCACHEDCLOUD_PASSWORD'))
    return mc

mc = get_mc()
mc.add(already_posted_key, ())

# mc.set(already_posted_key, ())

npsub = get_npsub()

# for f in npsub.flair.link_templates:
#     print(f)
# exit(1)

def run_bot():
    post_user_games()

def get_open_games():
    req = requests.post(url, data)
    rdata = req.json()
    print('rdata.len', len(rdata))
    games = rdata[1]
    return games

get_number = lambda g: int(g['number'])
def post_user_games():
    games = get_open_games()
    ugames = games['user_created_games']
    numbers = map(get_number, ugames)

    # already_posted = mc.get(already_posted_key)
    # REMOVE THIS
    already_posted = tuple(mc.get(already_posted_key))
    print('already_posted', already_posted)

    for game in ugames:
        number = int(game['number'])
        if number in already_posted:
            print('Skipping', number, game['name'])
            continue
        try: 
            post_open_game_thread(game)
        except praw.exceptions.APIException as e:
            if not 'ALREADY_SUB' in str(e):
                print('APIException', str(e))
                break

        already_posted = already_posted + (number,)
        mc.set(already_posted_key, already_posted)

        # only one per run for testing
        # avoids rate limit also....
        # break

    # we want to remove the games which are unlisted
    already_posted = tuple(set(already_posted) & set(numbers))
    mc.set(already_posted_key, already_posted)

    print('Done')

tick_descs = {
    15: 'Quad',
    30: 'Double',
    60: 'Normal',
    120: 'Slow'
}
def post_open_game_thread(game):

    name = html.unescape(game['name'])
    number = game['number']
    version = game['version'] # triton/proteus
    max_players = game['maxPlayers']
    # disabled, enabled, dark start
    dark = game['config']['darkGalaxy']
    
    turn_based = game['turn_based'] # 0 or 1

    # minutes per tick
    tick_rate = game['config']['tickRate']
    tick_desc = tick_descs[tick_rate]


    # ticks per production
    # production_ticks = game['config']['productionTicks']

    turn_jump_ticks = game['config']['turnJumpTicks']
    turn_time = game['config']['turnTime']

    # pprint(game)
    # exit(1)

    tags = []

    if dark == 1:
        tags.append('Dark')

    if turn_based == 1:
        tags.append('Turn Based')
    elif tick_desc is not 'Normal':
        tags.append(tick_desc)

    # flair
    status = game['status'] # 'open'
    players = game['players'] # current players

    if status != 'open':
        raise Exception('Recieved a closed game!')


    if tags:
        tag_part = ' [{}]'.format(','.join(sorted(tags)))
    else:
        tag_part = ''

    title = '{} {{{}}}{} ({})'.format(
        name,
        max_players, 
        tag_part, 
        version.title())

    link = '{}/{}/{}'.format(
        BASE_DOMAIN,
        'game' if version == 'triton' else version,
        number)

    print('Posting:', game['config']['password'], title, link)

    submission = npsub.submit(
        title,
        url=link,
        resubmit=False,
        flair_id=open_id
        )

    # submission = npsub.submit('Some title', selftext='Some text')
    # submission = npsub.submit(title, url=link, resubmit=False)
    # submission.mod.flair(text='Open', css_class='open-game')

    # thread.mod.distinguish(sticky=True)

# def main():
    
#     input_key = 'TEST_KEY'

#     obj = mc.get(input_key)
#     mc.set(input_key, "True")
#     mc.delete(key)