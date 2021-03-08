import sys
import json 
import sql
from dateutil import parser as dt


def getPackageId(package, ecosystem):
    ''' returns packageId if exists, else creates '''
    selectQ = 'select id from package where name=%s and ecosystem=%s'
    results = sql.execute(selectQ,(package,ecosystem))
    if not results:
        insertQ = 'insert into package values (null,%s,%s)'
        sql.execute(insertQ,(package,ecosystem))
        results = sql.execute(selectQ,(package,ecosystem))
    return results[0]['id']

with open("../snyk/data/ghsa.json") as file:
    data = json.load(file)

for advisory in data:

    id = advisory['ghsaId']
    score = advisory['cvss'].get('score',None)
    vector = advisory['cvss'].get('vectorString',None)

    cve = None
    for e in advisory['identifiers']:
        if e['type']=='CVE':
            if e['value'] != '':
                cve=e['value']
                assert cve.count('CVE') == 1
    
    origin = advisory['origin']
    publish = dt.parse(advisory['publishedAt'])
    severity = advisory['severity']
    summary = advisory['summary']
    withdrawn =  advisory['withdrawnAt']
    if withdrawn:
        withdrawn = dt.parse(withdrawn)

    q='insert into advisory values(%s,%s,%s,%s,%s,%s,%s,%s,%s)'
    print(id,score,vector,cve,origin,publish,severity, summary,withdrawn)
    sql.execute(q,(id,score,vector,cve,origin,publish,severity, summary,withdrawn))
    
    for e in advisory['vulnerabilities']['edges']:
        data = e['node']
        package = data['package']['name']
        ecosystem = data['package']['ecosystem']
        packageId = getPackageId(package, ecosystem)
        if data['firstPatchedVersion'] is None:
            patch = None
        else:
            patch = data['firstPatchedVersion']['identifier']
        range = data['vulnerableVersionRange']
        q='insert into advisory_package values(%s,%s,%s,%s)'
        print(id,packageId,patch,range)
        sql.execute(q,(id,packageId,patch,range))



            
   