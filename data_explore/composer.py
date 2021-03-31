import common, sql
import os, json
import subprocess, shlex
from dateutil import parser as dt
import requests, json
import logging, coloredlogs
coloredlogs.install()
ecosystem = 'Composer'

def get_repository_url(package):
    repository = None
    assert package.count('/') == 1

    try:
        url = 'https://repo.packagist.org/p2/{}.json'.format(package)
        page = requests.get(url)
        data = json.loads(page.content)
        data = data['packages'][package][0]
        data = data['source']['url']
        assert data.endswith('.git')
        repository = data[:-len('.git')]

        # if 'source_code_uri' in data:
        #     repository = data['source_code_uri']
        if not repository:
            repository = common.search_for_github_repo(package, data)
    except Exception as e:
        logging.info(e)
    
    print(package, repository)
    if repository:
        return repository
    else:
        return common.norepo

if __name__=='__main__':
    #get repository remote url of packages
    packages = common.getPackagesToSearchRepository(ecosystem)
    for item in packages:
        id, repo = item['id'], get_repository_url(item['name'])
        sql.execute('update package set repository_url=%s where id = %s',(repo,id))