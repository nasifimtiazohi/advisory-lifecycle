import os
import requests
import json
token = os.environ['gh_token']

def rest_call(url):
    headers = {'Authorization': 'token {}'.format(token)}
    url = 'https://api.github.com/repos/ansible/ansible/pulls/41414/commits'
    r = requests.get(url, headers=headers)
    return json.loads(r.content)