import common, sql
import os, json
import subprocess, shlex
from dateutil import parser as dt
from bs4 import BeautifulSoup as BS
import pandas as pd
import requests
import logging, coloredlogs
coloredlogs.install()
import time
ecosystem = 'Go'


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

if __name__ == '__main__':
    #get repository remote url of packages
    packages = common.getPackagesToSearchRepository(ecosystem)
    for item in packages:
        id, repo = item['id'], get_repository_url(item['name'])
        print(item['name'],repo)
        sql.execute('update package set repository_url=%s where id = %s',(repo,id))