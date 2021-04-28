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
ecosystem = 'Go'
import git_analysis as ga


def get_repository_url(package):
    repository = None
    
    url = 'https://pkg.go.dev/{}'.format(package)
    page = requests.get(url)
    
    soup = BS(page.content, 'html.parser')
    elems = soup.findAll("div",class_='UnitMeta')
    if not elems:
        repository = common.norepo
    else:
        assert len(elems) == 1
        soup = elems[0]
        links = soup.findAll("a")
        assert len(links) == 1
        repository = (links[0].text).strip()
    
    return repository

def get_release_info(package,version, repo_url):
    prior_release = release_date = None 
    releases = ga.get_all_tags(package_id, repo_url)
    candidate_tags = []
    for k in releases.keys():
        if k.endswith(version):
            candidate_tags.append(k)
    if len(candidate_tags) == 1:
        release_date =  releases[candidate_tags[0]]['tag_date'].astimezone(dateutil.tz.tzutc())


    return release_date, prior_release


if __name__ == '__main__':
    #get repository remote url of packages
    packages = common.getPackagesToSearchRepository(ecosystem)
    for item in packages:
        id, repo = item['id'], get_repository_url(item['name'])
        print(item['name'],repo)
        sql.execute('update package set repository_url=%s where id = %s',(repo,id))
    
    #get release info (publish date and prior release) for each fixing release
    packages = common.getPackagesToProcessRelease(ecosystem)
    for item in packages:
        package_id, package, version, repo_url = item['package_id'], item['package'], item['version'], item['repo_url']
        print(repo_url)
        publish_date, prior_release = get_release_info(package,version, repo_url)
        print(package, package_id, version, publish_date, prior_release)
        sql.execute('insert into release_info values(null,%s,%s,%s,%s)',(package_id, version, publish_date, prior_release))