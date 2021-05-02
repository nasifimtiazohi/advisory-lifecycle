import common, sql
import os, json
import subprocess, shlex
from dateutil import parser as dt
import dateutil
from bs4 import BeautifulSoup as BS
import pandas as pd
import requests
import logging, coloredlogs
coloredlogs.install()
import time 
ecosystem = 'Maven'
import maven_version
from maven_version import error, MavenVersion


from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
DRIVER_PATH = '/usr/local/bin/chromedriver'


def setup_driver():
    WINDOW_SIZE = "1920,1080"
    options = webdriver.ChromeOptions()
    options.add_argument("--headless")
    options.add_argument("--window-size=%s" % WINDOW_SIZE)
    options.add_argument("--enable-javascript")
    driver = webdriver.Chrome(executable_path=DRIVER_PATH, options=options)
    driver.implicitly_wait(10)
    return driver

def get_repository_url(package):
    assert package.count(':') == 1
    group, artifact = package.split(':')

    driver = setup_driver()
    url = 'https://search.maven.org/artifact/{}/{}'.format(group,artifact)
    logging.info(url)
    
    page = driver.get(url)
    url = None
    try:
        #we have to make sure the JavaScript content has loaded
        WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.XPATH, '/html/body/app-root/div/app-artifacts/div/app-artifact-description')))
        df = pd.read_html(driver.page_source)[0]
        df = df.loc[df[0] == 'Source code']
        assert len(df) == 1
        assert len(df[1].values) == 1
        url = df[1].values[0]
    except Exception as e:
        logging.error(e)
        url=common.norepo
    
    driver.quit()
    logging.info(url)
    return url

def sanitize_repo_url():
    #git@ at the beginning mistake
    s='git@github.com:'
    q='''select *
        from package
        where repository_url like %s;'''
    results = sql.execute(q,('%{}%'.format(s)))
    print('results to be sanitized:', len(results))
    for item in results:
        id, url = item['id'], item['repository_url']
        url = url.strip()
        url = url[url.find(s)+len(s):]
        url = 'https://github.com/' + url
        print(url)
        sql.execute('update package set repository_url=%s where id = %s',(url,id))

def isValidVersion(v):
    try:
        v = MavenVersion(v)
        return True
    except:
        return False

def parse_mavenrepo_page(url):
    page = requests.get(url)
    if page.status_code == 200:
        versions = {}
        allValid = True #if all versions are valid

        soup = BS(page.content, "html.parser")
        pres = soup.find_all("pre")
        assert len(pres) == 1
        pre = pres[0]
        lines = pre.text.strip().split('\n')
        for line in lines:
            if '../' in line or 'xml' in line or '$' in line or 'md5' in line or 'sha' in line or 'KEYS' in line:
                #not versions
                continue

            # if 'java' in line or 'jre' in line: 
            #     #handle it differently
            #     # #or jdbc, dev, amd, dmr, npm
            #     continue

            line = line.split(' ')
            line = list(filter(('').__ne__, line))
            if len(line) == 4:
                version = line[0]
                assert version.endswith('/')
                version = version[:-1]
                if version.startswith('v'):
                    version = version[1:]
                time= line[1] + ' ' + line[2]
                time = dt.parse(time).astimezone(dateutil.tz.tzutc())
                
            elif line and line[0].endswith('/'):
                version = line[0][:-1]
                time = None 
            
            else:
                print('check this case')
                logging.info(line)
                exit()
            
            if isValidVersion(version):
                versions[version] = time
            else:
                logging.info(version)
                allValid = False

        return versions, allValid

    else:
        return None, False

def maven_sort(versions):
    l = list(versions.keys())
    for i in range(len(l)):
        for j in range(i+1, len(l)):
            v1 , v2 = MavenVersion(l[i]), MavenVersion(l[j])
            if v1 > v2:
                l[i],l[j]=l[j],l[i]
    
    i = 1
    while i < len(l):
        if MavenVersion(l[i]) == MavenVersion(l[i-1]):
            if versions[l[i]] == None:
                del l[i]
            elif versions[l[i-1]] == None:
                l[i],l[i-1] == l[i-1], l [i]
                del l[i]
            else:
                i+=1
        else:
            i+=1
            
    return l

def get_release_info(package,version):
    publish_date = prior_release = None
    skip = True #temporary logic for now to only work with valid ones
    url = 'https://repo1.maven.org/maven2/' + package.replace('.','/').replace(':','/')
    print(url)
    versions, allValid = parse_mavenrepo_page(url)
    if versions and allValid:
        skip = False
        if version in versions:
            publish_date = versions[version]
            sorted_versions = maven_sort(versions)
            if version in sorted_versions:
                idx = sorted_versions.index(version)
                if idx  == 0:
                    logging.info('PLEASE CHECK WHAT THE MATTER WITH THIS')
                    logging.info(version)
                else:
                    prior_release = sorted_versions[idx-1]

    return publish_date, prior_release, skip

def get_release_date(package, version):
    publish_date = prior_release = None
    skip = True #temporary logic for now to only work with valid ones
    url = 'https://repo1.maven.org/maven2/' + package.replace('.','/').replace(':','/')
    print(url)
    versions, allValid = parse_mavenrepo_page(url)
    if versions and version in versions:
        return versions[version]

if __name__=='__main__':
    # #get repository remote url of packages
    # packages = common.getPackagesToSearchRepository(ecosystem)
    # for item in packages:
    #     id, repo = item['id'], get_repository_url(item['name'])
    #     sql.execute('update package set repository_url=%s where id = %s',(repo,id))
    
    # sanitize_repo_url()

    # #get release info (publish date and prior release) for each fixing release
    # packages = common.getPackagesToProcessRelease(ecosystem)
    # for item in packages:
    #     package_id, package, version = item['package_id'], item['package'], item['version']
    #     publish_date, prior_release, skip = get_release_info(package,version)
    #     print(package_id, version, publish_date, prior_release, skip)
    #     if not skip:
    #        sql.execute('insert into release_info values(null,%s,%s,%s,%s)',(package_id, version, publish_date, prior_release))
    #        pass 

    
    #get release info (publish date and prior release) for each fixing release
    packages = common.getPackagesToProcessReleaseDate(ecosystem)
    for item in packages:
        package_id, package, version = item['package_id'], item['package'], item['version']
        publish_date = get_release_date(package,version)
        prior_release = None 
        if publish_date:
            print(package_id, version, publish_date, prior_release)
            sql.execute('insert into release_info values(null,%s,%s,%s,%s)',(package_id, version, publish_date, prior_release))
s
    