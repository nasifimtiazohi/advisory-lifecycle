import common, sql
import os, json
import subprocess, shlex
import dateutil
from dateutil import parser as dt
import requests, json
import logging, coloredlogs
coloredlogs.install()
ecosystem = 'RubyGems'
           
def get_repository_url(package):
    repository = None

    try:
        url = 'https://rubygems.org/api/v1/gems/{}.json'.format(package)
        page = requests.get(url)
        data = json.loads(page.content)
        if 'source_code_uri' in data:
            repository = data['source_code_uri']
        if not repository:
            repository = common.search_for_github_repo(package, data)
    except Exception as e:
        logging.info(e)
    
    print(package, repository)
    if repository:
        return repository
    else:
        return common.norepo
    
def get_release_info(package,version):
    #ruby gems return it as sorted:
    #https://rubygems.org/gems/carrierwave/versions, https://rubygems.org/gems/rails_admin/versions
    release_date = prior_release = None
    
    #some custom fixing
    if package == 'bundler' and version == '2.0':
        version = '2.0.0'
    if package == 'rubocop' and version == '0.49':
        version = '0.49.0'

    url = 'https://rubygems.org/api/v1/versions/{}.json'.format(package)
    print(url)
    page = requests.get(url)
    if page.status_code == 200:
        data = json.loads(page.content)
        assert isinstance(data, list)

        versions = []
        for item in data:
            cur = item['number']
            versions.append(cur)
            if cur == version:
                release_date = dt.parse(item['created_at']).astimezone(dateutil.tz.tzutc())
        
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
    print(len(packages))
    for item in packages:
        package_id, package, version = item['package_id'], item['package'], item['version']
        publish_date, prior_release = get_release_info(package,version)
        print(package, package_id, version, publish_date, prior_release)
        sql.execute('insert into release_info values(null,%s,%s,%s,%s)',(package_id, version, publish_date, prior_release))
        