'''
get github release note
'''
import sql

def getPackagesToSearchRepository(ecosystem):
    q = '''select *
            from package
            where ecosystem = %s
            and id not in
            (select package_id from repository);'''
    results =  sql.execute(q,(ecosystem))
    return results

def getPackagesToProcessRelease(ecosystem):
    q = '''select distinct p.id as package_id, p.name as package, version
        from fixing_releases fr
        join advisory a on fr.advisory_id = a.id
        join package p on a.package_id = p.id
        where ecosystem=%s and version != 'manual checkup needed'
        and concat(package_id, version)
        not in (select concat(package_id, version) from release_info);'''
    results =  sql.execute(q,(ecosystem))
    return results
    

def parse_sha_from_commit_reference(name, url):
    links_with_40bit_sha =  ['github', 'gitlab','bitbucket','openssl','git.savannah','git.videolan','git-wip-us']
    for l in links_with_40bit_sha:
        if l in url.lower():
            return url[-40:]
    
    # TODO check following conditions
    # how to handle svn links - are they mostly old? we can get them from scraping the webpage that the url lands
    # anonscm - last 40 chars but only for cocoapods and link not working - so don't bother
    # git.moodle : if ends with h=40 chars otherwise MDL - contains multiple commits
    # https://josm.openstreetmap.de/changeset - scrape date from web link

def parse_sha_from_github_PR_reference(name, url):
    '''look for both github and pull and then extract the commits involved'''
    ''' but some can be missed in the above way. check if name contain github pr as well and inspect the ur'''
    pass

def parse_iisue():
    #issue , bug, JIRA
    if github issue then take issue date
    pass


# Release Note
# Exploit
# Changelog
# Advisory (ies)
# Additional Information
# Blog
# PoC
# Diff
# Announcement
# Vulnerable Code / Details (vulnerab)
# NVD
# HackerOne
# Google Group Forum
# Documentation
# Mailing list
# Vulnerabil
# Hacker News
# Disclosure