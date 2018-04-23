import requests
from pprint import pprint

url = 'https://np.ironhelmet.com/mrequest/open_games'
data = {'type': 'open_games'}

req = requests.post(url, data)

pprint(req.json())


