import common, sql
import os, json
import subprocess, shlex
from dateutil import parser as dt
import dateutil
import requests, json
import logging, coloredlogs
coloredlogs.install()
ecosystem = 'pip'
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
    
def get_release_info(package, version):
    release_date = prior_release = None
    
    url = 'https://pypi.org/pypi/{}/json'.format(package)
    page = requests.get(url)
    assert page.status_code == 200
    data = json.loads(page.content)
    assert 'releases' in data

    releases = data['releases']
    if version in releases.keys():
        if len(releases[version]) > 0:
            release_date = (dt.parse(releases[version][-1]['upload_time_iso_8601'])).astimezone(dateutil.tz.tzutc())
        
        versions = version_sorting(list(releases.keys()))
        idx = versions.index(version)
        if idx > 0:
            prior_release = versions[idx-1]

    return release_date, prior_release

def check_prior_release():
    q='''select *
        from release_info ri
        join package p on ri.package_id = p.id
        where ecosystem = 'pip';'''
    results = sql.execute(q)

    for item in results:
        package, version, prior_release = item['name'], item['version'], item['prior_release']
        print(package, version, prior_release)
        release_date = prior_release = None
        try:
            url = 'https://pypi.org/pypi/{}/json'.format(package)
            page = requests.get(url)
            assert page.status_code == 200
            data = json.loads(page.content)
            assert 'releases' in data

            releases = data['releases']
            if version in releases.keys():
                if len(releases[version]) > 0:
                    release_date = (dt.parse(releases[version][-1]['upload_time_iso_8601'])).astimezone(dateutil.tz.tzutc())
                
                versions = list(releases.keys())

                for i in range(len(versions)):
                    for j in range(i+1, len(versions)):
                        if PythonVersion.Version(versions[i]) == PythonVersion.Version(versions[j]):
                            print(versions[i],versions[j])
                            logging.info('eequal')
        except Exception as e:
            print(e)
                

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
        print(package, package_id, version)
        if not isValidVersion(version):
            print('release version invalid')
            logging.info(version)
            continue
        publish_date, prior_release = get_release_info(package,version)
        sql.execute('insert into release_info values(null,%s,%s,%s,%s)',(package_id, version, publish_date, prior_release))