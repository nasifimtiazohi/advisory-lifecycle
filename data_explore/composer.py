import common, sql
import os, json
import subprocess, shlex
from dateutil import parser as dt
import dateutil
import requests, json
import logging, coloredlogs
coloredlogs.install()
ecosystem = 'Composer'
from packaging import version as PythonVersion

def isValidVersion(v):
    try:
        v = PythonVersion.Version(v)
        return True
    except:
        logging.info(v)
        return False

def version_sorting(vers):
    temp=[]
    for v in vers:
        if isValidVersion(v):
            temp.append(v)
    vers=temp

    #https://stackoverflow.com/a/58035970/1445015
    return sorted(vers, key=lambda x: PythonVersion.Version(x))

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

def get_release_info(package, version):
    #composer api sends release as properly sorted: https://packagist.org/packages/drupal/core
    release_date = prior_release = None
    
    url = 'https://repo.packagist.org/p2/{}.json'.format(package)
    print(url)
    page = requests.get(url)
    if page.status_code == 200:
        data = json.loads(page.content)
        assert 'packages' in data and package in data['packages']

        releases = data['packages'][package]
        versions = []
        for item in releases:
            cur = item['version']
            if cur.startswith('v'):
                cur =  cur[1:]
            versions.append(cur)
            if version == cur:
                if 'time' in item:
                    release_date = dt.parse(item['time']).astimezone(dateutil.tz.tzutc())
        
        if version in versions:
            idx = versions.index(version)
            if idx < len(versions) - 1: #oldest
                prior_release = versions[idx+1] #sorted from recent to oldest
        else:
            logging.info(version)

    return release_date, prior_release

if __name__=='__main__':
    #get repository remote url of packages
    packages = common.getPackagesToSearchRepository(ecosystem)
    for item in packages:
        id, repo = item['id'], get_repository_url(item['name'])
        sql.execute('update package set repository_url=%s where id = %s',(repo,id))
    
    #get release info (publish date and prior release) for each fixing release
    packages = common.getPackagesToProcessRelease(ecosystem)
    for item in packages:
        package_id, package, version = item['package_id'], item['package'], item['version']
        publish_date, prior_release = get_release_info(package,version)
        
        print(package, package_id, version, publish_date, prior_release)
        sql.execute('insert into release_info values(null,%s,%s,%s,%s)',(package_id, version, publish_date, prior_release))