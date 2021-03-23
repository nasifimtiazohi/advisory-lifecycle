'''
get github release note
'''
import sql
import os
from git import Repo 
root_path = os.getcwd()

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

    return None

def parse_sha_from_github_PR_reference(name, url):
    '''look for both github and pull and then extract the commits involved'''
    ''' but some can be missed in the above way. check if name contain github pr as well and inspect the url'''
    if 'github' in url and 'pull' in url:
        pass
    elif 'github' in name and 'PR' in name:
        pass


def parse_isue():
    #issue , bug, JIRA
    # if github issue then take issue date
    pass


def get_commits():
    q='''select distinct a.id
        from advisory a
        join fixing_releases fr on a.id = fr.advisory_id
        and a.id not in
        (select advisory_id from fix_commits);'''
    advisory_ids = map(lambda x: x['id'], sql.execute(q))

    for id in advisory_ids:
        print(id)
        q = '''select *
            from advisory_references
            where advisory_id = %s;'''
        results = sql.execute(q,(id))

        commits = []
        for item in results:
            if 'commit' in item['name'].lower() or 'commit' in item['url'].lower():
                sha = parse_sha_from_commit_reference(item['name'], item['url'])
                if sha:
                    commits.append(sha)
        
        for sha in commits:
            try:
                sql.execute('insert into fix_commits values(%s,%s,null,null)',(id,sha))
            except sql.pymysql.IntegrityError as error:
                if error.args[0] == sql.PYMYSQL_DUPLICATE_ERROR:
                    pass
                    #safely continue
                else:
                    print(error)
                    exit()


def get_commit_of_release(repo, release):
    '''repo is a gitpython object, while version is a string taken from ecosystem data'''
    # get closest matching tag, go to that commit and ensure the dependency file updated to that version in recent commits, at least for npm
    tags = repo.tags
    candidate_tags = []
    for tag in tags:
        if release in tag.path:
            candidate_tags.append(tag)
    assert len(candidate_tags) == 1
    tag = candidate_tags[0]
    try:
        message = tag.message
        #insert into database.

    return tag.commit


def analyze_change_complexity():
    q='''select *
        from advisory a
        join fixing_releases fr on a.id = fr.advisory_id
        join release_info ri on fr.version = ri.version and ri.package_id=a.package_id
        join repository r on a.package_id = r.package_id;'''
    results = sql.execute(q)
    
    for item in results:
        repo_url, release, prior_release = item['url'], item['ri.version'], item['prior_release']
        print(repo_url, release, prior_release)
        repo_name = repo_url.split('/')[-1]

        os.chdir(root_path + '/temp/')
        os.system('git clone {}.git'.format(repo_url))

        repo = Repo.init(root_path + '/temp/' + repo_name)
        #get commit of the tags with release
        cur_commit, prior_commit = get_commit_of_release(repo,release), get_commit_of_release(repo,prior_release)
        #TODO update db and get diff between the two and analyze complexity 
    
        break
        os.chdir(root_path + '/temp/')
        os.system('rm -rf {}'.format(repo_name))




if __name__=='__main__':
    analyze_change_complexity()

