# for version details, https://api.nuget.org/v3-flatcontainer/htmlsanitizer/index.json
# for each version, https://api.nuget.org/v3/registration3/htmlsanitizer/index.json
# for a specific version, https://api.nuget.org/v3/registration3/htmlsanitizer/5.0.274-beta.json
# version releases can jump, in betweens not officially released

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

if __name__=='__main__':
    #print(get_repository_url('lodash'))
    #get repository remote url of packages
    packages = common.getPackagesToSearchRepository(ecosystem)
    for item in packages:
        id, repo = item['id'], get_repository_url(item['name'])
        print(item['name'],repo)
        sql.execute('update package set repository_url=%s where id = %s',(repo,id))


