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
ecosystem = 'Maven'

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



if __name__=='__main__':
    #get repository remote url of packages
    packages = common.getPackagesToSearchRepository(ecosystem)
    c=0
    for item in packages:
        id, repo = item['id'], get_repository_url(item['name'])
        sql.execute('update package set repository_url=%s where id = %s',(repo,id))

    
    