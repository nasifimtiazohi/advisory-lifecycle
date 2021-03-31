import common, sql
import os, json
import subprocess, shlex
from dateutil import parser as dt
import requests, json
import logging, coloredlogs
coloredlogs.install()
ecosystem = 'pip'

def get_repository_url(package):
    repository = None

    try:
        url = 'https://pypi.org/pypi/{}/json'.format(package)
        page = requests.get(url)
        data = json.loads(page.content)
        if 'project_urls' in data['info'] and 'Source Code' in data['info']['project_urls']:
            repository = data['info']['project_urls']['Source Code']
        else: 
            repository = common.search_for_github_repo(package, data)
    except Exception as e:
        logging.info(e)
    
    print(package, repository)
    if repository:
        return repository
    else:
        return common.norepo
    
def get_prior_release(package, version):
    #same api
    pass




if __name__=='__main__':
    #get repository remote url of packages
    packages = common.getPackagesToSearchRepository(ecosystem)
    for item in packages:
        id, repo = item['id'], get_repository_url(item['name'])
        sql.execute('update package set repository_url=%s where id = %s',(repo,id))
