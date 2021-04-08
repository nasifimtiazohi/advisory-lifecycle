import os
import requests
import json
token = os.environ['gh_token']

def rest_call(url):
    headers = {'Authorization': 'token {}'.format(token)}
    r = requests.get(url, headers=headers)
    print('fetched', r.url)
    return json.loads(r.content)