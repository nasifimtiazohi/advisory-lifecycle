'''
1. get repository link from npm homepage
2. get release publish date
3. get last release before fix
'''


import common, sql
import os, json
import subprocess, shlex
from dateutil import parser as dt
import dateutil
from distutils.version import LooseVersion, StrictVersion

ecosystem = 'npm'



def get_repository_url(package):
    ''' npm repo command gets the subdirectory of a package within a git repository '''
    try:
        lines = subprocess.check_output(shlex.split('npm repo {} --browser=false'.format(package)), 
                    stderr=subprocess.STDOUT, encoding="437").split('\n')[:-1]
    except:
        #non-zero exit status likely means no repository listed
        return common.norepo
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
        d =  dt.parse(d[version])
        d = d.astimezone(dateutil.tz.tzutc())
        return d
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
        return common.manualcheckup

    d = json.loads(lines)
    if version in d:
        idx = d.index(version) 
        if idx == 0:
            return common.manualcheckup
        else:
            return d[idx-1]
    else:
        return common.manualcheckup
    
def check_prior_release():
    q='''select *
        from release_info ri
        join package p on ri.package_id = p.id
        where ecosystem = 'npm';'''
    results = sql.execute(q)

    for item in results:
        package, version, prior_release = item['name'], item['version'], item['prior_release']
        print(package, version, prior_release)
        flag = True
        try:
            lines = subprocess.check_output(shlex.split('npm view {} versions --json'.format(package)), 
                            stderr=subprocess.STDOUT, encoding="437")
        except Exception as e:
            print(e)
            flag = False
            assert prior_release == common.manualcheckup

        if flag:
            d = json.loads(lines)
            d = common.semver_sorting(d)
            if version in d:
                idx = d.index(version) 
                if idx == 0:
                    assert prior_release == common.manualcheckup
                else:
                    assert prior_release == d[idx-1]
        

if __name__ == '__main__':
    #get repository remote url of packages
    packages = common.getPackagesToSearchRepository(ecosystem)
    for item in packages:
        id, repo = item['id'], get_repository_url(item['name'])
        sql.execute('update package set repository_url=%s where id = %s',(repo,id))
    
    #get release info (publish date and prior release) for each fixing release
    packages = common.getPackagesToProcessRelease(ecosystem)
    for item in packages:
        id, package, version = item['package_id'], item['package'], item['version']
        publish_date = get_release_publish_date(package, version)
        prior_release = get_prior_release(package, version)
        sql.execute('insert into release_info values(null,%s,%s,%s,%s)',(id, version, publish_date, prior_release))
    
   

    
