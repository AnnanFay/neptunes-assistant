from datetime import datetime

import requests
import os
import bmemcached
import praw
import html
from pprint import pprint

BASE_DOMAIN = "https://np.ironhelmet.com"
url = BASE_DOMAIN + "/mrequest/open_games"
data = {"type": "open_games"}

# cache names
ALREADY_POSTED = "POSTED"
OPEN_THREADS = "OPEN_THREADS"

# flair IDs
OPEN_ID = "40ac6e5e-4701-11e8-bd80-0e491115009a"
FULL_ID = "109d87bc-4674-11e8-a30b-0eed8597e7ae"


def get_npsub():
    username = os.environ["REDDIT_USERNAME"]
    password = os.environ["REDDIT_PASSWORD"]
    client_id = os.environ["NEPTUNES_ID"]
    client_secret = os.environ["NEPTUNES_SECRET"]

    reddit = praw.Reddit(
        client_id=client_id,
        client_secret=client_secret,
        password=password,
        username=username,
        user_agent="neptunes-assistant bot by /u/AnnanFay",
    )

    print("Me:", reddit.user.me())

    npsub = reddit.subreddit("neptunespride")
    return reddit, npsub


def get_mc():
    mc = bmemcached.Client(
        os.environ.get("MEMCACHEDCLOUD_SERVERS").split(","),
        os.environ.get("MEMCACHEDCLOUD_USERNAME"),
        os.environ.get("MEMCACHEDCLOUD_PASSWORD"),
    )

    # Adds empty values if cache doesn't exist
    mc.add(ALREADY_POSTED, ())
    mc.add(OPEN_THREADS, {})
    return mc


mc = get_mc()
reddit, npsub = get_npsub()


def dummy_test():
    # insert dummy test data
    # ensure thread exists

    test_game = 5326559473565696
    test_thread = "jg5ks6"

    ap = mc.get(ALREADY_POSTED)
    ap = ap + (test_game,)
    ap = mc.set(ALREADY_POSTED, ap)

    ot = mc.get(OPEN_THREADS)
    ot[test_game] = test_thread
    ot = mc.set(OPEN_THREADS, ot)


def run_bot():
    "main entry point of the bot"

    # for f in npsub.flair.link_templates:
    #     print(f)
    # exit(1)
    # dummy_test()

    post_user_games()

    # batch_archive_old_threads()


def batch_archive_old_threads():

    # user = reddit.redditor('neptunes-assistant')
    # submissions = tuple(user.submissions.new())

    submissions = tuple(
        npsub.search(
            query="author:neptunes-assistant flair:open", sort="new", limit=1000
        )
    )

    print("submissions", len(submissions))

    for sub in submissions:

        date_posted = datetime.utcfromtimestamp(sub.created_utc)
        post_age = datetime.now() - date_posted
        print(sub.title)
        print("    age     ", post_age.days, "days")
        print("    comments", sub.num_comments)
        print("    score   ", sub.score)

        if post_age.days < 14:
            continue
        else:
            sub.mod.flair(flair_template_id=FULL_ID)

            if sub.num_comments == 0 and sub.score <= 1:
                print("    REMOVING", sub)
                sub.mod.remove()


def get_open_games():
    req = requests.post(url, data)
    rdata = req.json()
    print("NP API | rdata len", len(rdata))
    games = rdata[1]
    return games


def get_number(g):
    return int(g["number"])


def post_user_games():
    games = get_open_games()
    open_user_games = games["user_created_games"]

    already_posted = tuple(mc.get(ALREADY_POSTED))
    print("already_posted", already_posted)

    for game in open_user_games:
        number = int(game["number"])
        if number in already_posted:
            print("Skipping", number, game["name"])
            continue
        try:
            post_open_game_thread(game)
        except praw.exceptions.APIException as e:
            print("APIException", str(e))
            if not "ALREADY_SUB" in str(e):
                break

        already_posted = already_posted + (number,)
        mc.set(ALREADY_POSTED, already_posted)

    user_game_numbers = tuple(map(get_number, open_user_games))
    print("user_game_numbers", user_game_numbers)

    # make newly closed games as CLOSED and delete if they have no comments
    newly_closed = tuple(set(already_posted) - set(user_game_numbers))
    print("newly_closed", len(newly_closed))

    for closed_game_number in newly_closed:
        close_topic_for(closed_game_number)

    # remove the games which are unlisted
    # from the cache to prevent it growing
    already_posted = tuple(set(already_posted) & set(user_game_numbers))
    mc.set(ALREADY_POSTED, already_posted)

    print(ALREADY_POSTED, "=", already_posted)
    print("Done")


def close_topic_for(game_number):
    print("closing ", game_number)

    sub_ids = mc.get(OPEN_THREADS)
    try:
        sub_id = sub_ids[game_number]
        print("...     ", sub_id)
    except KeyError:
        print("data missing for", game_number)
        print("ignoring.....!!!!!!!!!")
        # Topic is already closed, or data is missing
        return

    submission = praw.models.Submission(reddit, id=sub_id)
    submission.mod.flair(flair_template_id=FULL_ID)

    # delete the post if no one has replied to it or up voted it
    if submission.num_comments == 0 and submission.score <= 1:
        print("...      deleting")
        # alternatives: submission.delete()
        submission.mod.remove()

    mc.set(OPEN_THREADS, sub_ids)


tick_descs = {15: "Quad", 30: "Double", 60: "Normal", 120: "Slow"}


def post_open_game_thread(game):

    name = html.unescape(game["name"])
    number = game["number"]
    version = game["version"]  # triton/proteus
    max_players = game["maxPlayers"]
    # disabled, enabled, dark start
    is_dark = (game["config"]["darkGalaxy"] == 1)
    is_turn_based = (game["turn_based"] == 1)  # 0 or 1
    is_premium = (game["config"]["playertype"] == 1)

    # minutes per tick
    tick_rate = game["config"]["tickRate"]
    tick_desc = tick_descs[tick_rate]

    # ticks per production
    # production_ticks = game['config']['productionTicks']

    turn_jump_ticks = game["config"]["turnJumpTicks"]
    turn_time = game["config"]["turnTime"]

    tags = []

    if is_premium:
        tags.append("Premium")

    if is_dark:
        tags.append("Dark")

    if is_turn_based:
        tags.append("Turn Based")
    elif tick_desc is not "Normal":
        tags.append(tick_desc)

    # flair
    status = game["status"]  # 'open'
    players = game["players"]  # current players

    if status != "open":
        raise Exception("Recieved a closed game!")

    if tags:
        tag_part = " [{}]".format(",".join(sorted(tags)))
    else:
        tag_part = ""

    title = "{} {{{}}}{} ({})".format(name, max_players, tag_part, version.title())

    link = "{}/{}/{}".format(
        BASE_DOMAIN, "game" if version == "triton" else version, number
    )

    print("Posting:", game["config"]["password"], title, link)

    submission = npsub.submit(title, url=link, resubmit=False, flair_id=OPEN_ID)

    # cache submission so we can easily archive when game closes
    sub_ids = mc.get(OPEN_THREADS)
    sub_ids[number] = submission.id
    mc.set(OPEN_THREADS, sub_ids)

    # submission = npsub.submit('Some title', selftext='Some text')
    # submission = npsub.submit(title, url=link, resubmit=False)
    # submission.mod.flair(text='Open', css_class='open-game')

    # thread.mod.distinguish(sticky=True)


# def main():

#     input_key = 'TEST_KEY'

#     obj = mc.get(input_key)
#     mc.set(input_key, "True")
#     mc.delete(key)
