'''
1. get repository link from npm homepage
2. get release publish date
3. get last release before fix
'''

import common, sql
import os, json
import subprocess, shlex
from dateutil import parser as dt
ecosystem = 'npm'

def get_repository_url(package):
    ''' npm repo command gets the subdirectory of a package within a git repository '''
    try:
        lines = subprocess.check_output(shlex.split('npm repo {} --browser=false'.format(package)), 
                    stderr=subprocess.STDOUT, encoding="437").split('\n')[:-1]
    except:
        #non-zero exit status likely means no repository listed
        return 'no repository listed'
    assert len(lines) ==3
    repo_url = lines[1].strip()
    return repo_url

def get_release_publish_date(package, version):
    try:
        lines = subprocess.check_output(shlex.split('npm view {} time --json'.format(package)), 
                        stderr=subprocess.STDOUT, encoding="437")
    except:
        #likely npm doesn't have the package listed in this name
        return None
    
    d = json.loads(lines)
    if version in d:
        return dt.parse(d[version])
    else:
        return None

def get_prior_release(package, version):
    #get the prior release on the branch in semver format
    # npm lists the versions alphabetically so makes life easy
    try:
        lines = subprocess.check_output(shlex.split('npm view {} versions --json'.format(package)), 
                        stderr=subprocess.STDOUT, encoding="437")
    except:
        #likely npm doesn't have the package listed in this name
        return 'manual checkup needed'

    d = json.loads(lines)
    if version in d:
        idx = d.index(version) 
        if idx == 0:
            return 'manual checkup needed'
        else:
            return d[idx-1]
    else:
        return 'manual checkup needed'
    


if __name__ == '__main__':
    #get repository remote url of packages
    packages = common.getPackagesToSearchRepository(ecosystem)
    for item in packages:
        id, repo = item['id'], get_repository_url(item['name'])
        sql.execute('insert into repository values(%s,%s)',(id,repo))
    
    # get release info (publish date and prior release) for each fixing release
    packages = common.getPackagesToProcessRelease(ecosystem)
    for item in packages:
        id, package, version = item['package_id'], item['package'], item['version']
        print(id, package, version)
        publish_date = get_release_publish_date(package, version)
        prior_release = get_prior_release(package, version)
        print(package, version, publish_date, prior_release)
        sql.execute('insert into release_info values(%s,%s,%s,%s)',(id, version, publish_date, prior_release))
    
    # get commits for fixed advisories
    

    
