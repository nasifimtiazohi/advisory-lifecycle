# for version details, https://api.nuget.org/v3-flatcontainer/htmlsanitizer/index.json
# for each version, https://api.nuget.org/v3/registration3/htmlsanitizer/index.json
# for a specific version, https://api.nuget.org/v3/registration3/htmlsanitizer/5.0.274-beta.json
# version releases can jump, in betweens not officially released

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
ecosystem = 'NuGet'



def get_repository_url(package):
    repository = common.norepo
    
    url = 'https://www.nuget.org/packages/{}/'.format(package)
    page = requests.get(url)
    
    soup = BS(page.content, 'html.parser')
    uls = soup.findAll("ul",class_='list-unstyled ms-Icon-ul')
    for ul in uls:
        lis = ul.findAll("li")
        for li in lis:
            link = li.find("a")
            if link:
                text = link.text.strip()
                if text == 'Source repository':
                    return link['href']
        
        #if source repo not there, check project site
        for li in lis:
            link = li.find("a")
            if link:
                text = link.text.strip()
                if text == 'Project Site':
                    site = link['href']
                    if 'github.com' in site:
                        return site

    return repository


def get_prior_release(package,version):
    prior_release = None
    url = 'https://api.nuget.org/v3-flatcontainer/{}/index.json'.format(package)
    print(url)
    page = requests.get(url)
    if page.status_code == 200:
        data = json.loads(page.content)
        if 'versions' in data:
            versions = data['versions']
            if version in versions:
                idx = versions.index(version)
                if idx > 0:
                    prior_release = versions[idx-1]

    return prior_release

def get_release_date(pacakge, version):
    release_date = None
    url = 'https://api.nuget.org/v3/registration3/{}/{}.json'.format(package, version)
    print(url)
    page = requests.get(url)
    if page.status_code == 200:
        data = json.loads(page.content)
        if 'published' in data:
            release_date = dt.parse(data['published']).astimezone(dateutil.tz.tzutc())
    
    if release_date == dt.parse('1900-01-01 00:00:00+00:00'):
        release_date = None
    
    return release_date
    

if __name__=='__main__':
    #print(get_repository_url('lodash'))
    #get repository remote url of packages
    packages = common.getPackagesToSearchRepository(ecosystem)
    for item in packages:
        id, repo = item['id'], get_repository_url(item['name'])
        sql.execute('update package set repository_url=%s where id = %s',(repo,id))
    
     #get release info (publish date and prior release) for each fixing release
    packages = common.getPackagesToProcessRelease(ecosystem)
    for item in packages:
        id, package, version = item['package_id'], item['package'], item['version']
        publish_date = get_release_date(package, version)
        prior_release = get_prior_release(package, version)
        print(id, package, version, publish_date, prior_release)
        sql.execute('insert into release_info values(null,%s,%s,%s,%s)',(id, version, publish_date, prior_release))


