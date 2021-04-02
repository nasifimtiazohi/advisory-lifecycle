'''
get github release note
'''
import sql
import os
from git import Repo 
import logging, coloredlogs
from dateutil import parser as dt
import requests, json
import subprocess, shlex
coloredlogs.install()
root_path = os.getcwd()
repo_path = root_path +'/temp'
norepo = 'no repository listed'
manualcheckup = 'manual checkup needed'

import collections
def flatten(dictionary, parent_key=False, separator='.'):
    """
    Turn a nested dictionary into a flattened dictionary
    :param dictionary: The dictionary to flatten
    :param parent_key: The string to prepend to dictionary's keys
    :param separator: The string used to separate flattened keys
    :return: A flattened dictionary
    """

    items = []
    for key, value in dictionary.items():
        new_key = str(parent_key) + separator + key if parent_key else key
        if isinstance(value, collections.MutableMapping):
            items.extend(flatten(value, new_key, separator).items())
        elif isinstance(value, list):
            for k, v in enumerate(value):
                items.extend(flatten({str(k): v}, new_key).items())
        else:
            items.append((new_key, value))
    return dict(items)

def search_for_github_repo(package, data):
    data = flatten(data)
    for k in data.keys():
        if isinstance(data[k], str) and '\n' not in data[k] and data[k].startswith('https://github.com') and package in data[k]:
            url = data[k]
            if url.endswith('.git'):
                url=url[:-len('.git')]
            return url[:url.find('.com/')+5] + '/'.join( url[url.find('.com/')+5:].split('/')[:2] )
    return None


def getPackagesToSearchRepository(ecosystem):
    q = '''select *
            from package
            where ecosystem = %s
            and repository_url is null'''
    results =  sql.execute(q,(ecosystem))
    return results

def getPackagesToProcessRelease(ecosystem):
    q = '''select distinct p.id as package_id, p.name as package, version
        from fixing_releases fr
        join advisory a on fr.advisory_id = a.id
        join package p on a.package_id = p.id
        where ecosystem=%s and version != %s
        and concat(package_id, version)
        not in (select concat(package_id, version) from release_info);'''
    results =  sql.execute(q,(ecosystem,manualcheckup))
    return results
    
def parse_sha_from_commit_reference(name, url):
    ''' returns a list of shas'''

    links_with_40bit_sha =  ['github', 'gitlab','bitbucket','git.openssl','git.savannah','git.videolan','git-wip-us','gitbox','pagure']
    for l in links_with_40bit_sha:
        if '#diff' in url:
            url = url[:url.find('#diff')]
        
        #case - last 40 bit is sha 
        sha = url[-40:]
        rest = url[:-40]
        if rest.endswith('commit/') or rest.endswith('commits/') or rest.endswith('h=') or rest.endswith('id=') or rest.endswith('/c/'):
            return [sha]
        
        if 'github' in url and 'pull' in url:
            return parse_sha_from_github_PR_reference(name,url)
        
        if 'git.moodle.org' in url:
            #there are five for the same package moodle. check manually
            return ['manually check git moodle']
        if 'gitbox.apache.org' in url:
            return ['manually check git moodle']
        
        if 'svn.apache.org' in url:
            return ['not git']
        
        if 'github.com' in url and 'commit/' in url:
            s='commit/'
            sha = url[url.find(s) +len(s):]
            if len(sha) < 40:
                return ['short commit']
        
        if 'bitbucket' in url and 'commits/' in url:
            s='commits/'
            sha = url[url.find(s) +len(s):]
            if len(sha) < 40:
                return ['short commit']
            
        if 'compare' in url:
            return []
        
        invalid_urls =[
            'https://github.com/theupdateframework/tuf/commits/develop',
            'https://github.com/alkacon/apollo-template/commits/branch_10_5_x',
            'https://hg.tryton.org/trytond/rev/f58bbfe0aefb',
            #bitbucket repos are private
            'https://bitbucket.org/rick446/easywidgets/commits/cb446d6b0b5f9597c3761e61facfa1fac34b8e5c?at=default',
            'https://bitbucket.org/conservancy/kallithea/commits/ae947de541d5630e5505c7c8ded05cd37c7f232b?at=0.2',
            'https://bitbucket.org/cthedot/cssutils/commits/4077971c214b4f2eb4889a3ff0cb940e9e5d26a5?at=TAG_0.9.6a2',
            'https://bitbucket.org/cthedot/cssutils/commits/4ff52ad59c129e908a9250fd00cfed1aaf9d15f8?at=TAG_0.9.6a2'
        ]
        if url in invalid_urls:
            return []

        if url == 'https://github.com/shopware/platform/search?q=NEXT-9174&type=Commits':
            return ['78f3728a342359dc033a0994d2277e1ddbe53769','fb7c8909404bdbb51194f149c1c7950d38ca2f97']
        if url == 'https://github.com/cyu/rack-cors/commit/3f51048cf2bb893d58bde3dfa499220210d785d00':
            return '3f51048cf2bb893d58bde3dfa499220210d785d0'
        if url == 'https://github.com/apache/felix/commit/b5917272f7a45f1c6c245df2ced9aa32caef53c7?diff=split':
            return 'b5917272f7a45f1c6c245df2ced9aa32caef53c7'
        if url == 'https://github.com/Rich-Harris/devalue/commits?author=pi0':
            return ['14cae90d1fcd5e0083e3a1741238e017684890d7','751ed46deb404f5ed5d3ed49ee400903792530d5','fe3d061a833a0e2b1176fbf4ee74c6fb7ef8f082']
        if url=='https://github.com/sinatra/sinatra/commit/8aa6c42ef724f93ae309fb7c5668e19ad547eceb#commitcomment-27964109':
            return ['8aa6c42ef724f93ae309fb7c5668e19ad547eceb']
        if url == 'https://github.com/openstack/keystonemiddleware/blob/cbe9accc06a80ef8b0013983e96818379452e7da/releasenotes/notes/bug-1490804-87c0ff8e764945c1.yaml':
            return ['96ab58e6863c92575ada57615b19652e502adfd8']
        if url == 'https://github.com/apache/lucene-solr/commit/926cc4d65b6d2cc40ff07f76d50ddeda947e3cc4%23diff-5ec4e4f72cf2a1f5d475f0283ec684db':
            return ['926cc4d65b6d2cc40ff07f76d50ddeda947e3cc4']
        if url == 'https://github.com/sparklemotion/nokogiri/issues/1992':
            return ['83018426d0af80295c2c2fe1eaba1d6da00e73a9']
    
    # TODO check following conditions
    # anonscm - last 40 chars but only for cocoapods and link not working - so don't bother
    # https://josm.openstreetmap.de/changeset - scrape date from web link

    logging.info(url)
    exit()
    return [manualcheckup]

def parse_sha_from_github_compares(name,url):
    #TODO figure out how to do
    pass


def parse_sha_from_github_PR_reference(name, url):
    prefix = 'https://github.com/'
    assert url.startswith(prefix)

    url = url[len(prefix):]
    url = url.split('/')[:4]

    #sanitize pull number
    i=0
    while i<len(url[-1]):
        if not url[-1][i].isdigit():
            break
        i+=1
    url[-1] = url[-1][:i]
    

    assert url[2] == 'pull'
    url[2] = 'pulls'
    endpoint = 'https://api.github.com/repos/' + '/'.join(url) + '/commits'
    commits = json.loads(requests.get(endpoint).content)
    if not isinstance(commits, list):
        return [manualcheckup]
    shas = []
    for commit in commits:
        shas.append(commit['sha'])
    return shas

def parse_isue():
    #issue , bug, JIRA
    # if github issue then take issue date
    pass

def parse_repository_url_from_references(id, name, url):
    if 'github' in url or 'gitlab' in url:
        if url.endswith('.git'):
                url=url[:-len('.git')]
        return url[:url.find('.com/')+5] + '/'.join( url[url.find('.com/')+5:].split('/')[:2] )
    elif 'svn.apache.org' in url:
        return 'not git'
    elif url == 'https://bitbucket.org/ianb/paste/commits/fcae59df8b56d2587e295593bee8a6d517ef2105':
        return norepo
    else:
        print ('i am here fuck it',id,name,url)
        exit() #TODO: replace with norepo afterwards or handle other repos

def get_fix_commits():
    q='''select distinct a.id, a.package_id, p.name, p.repository_url 
        from advisory a
        join fixing_releases fr on a.id = fr.advisory_id
        join package p on a.package_id = p.id
        where a.id not in
        (select advisory_id from fix_commits)
        and repository_url is not null;'''
    results = sql.execute(q)

    for item in results:
        advisory_id, package_id, package, repo_url = item['id'], item['package_id'], item['name'], item['repository_url']
        print(advisory_id, package_id, package, repo_url)

        q = '''select *
            from advisory_references
            where advisory_id = %s;'''
        results = sql.execute(q,(advisory_id))

        commits = []
        for item in results:
            if 'commit' in item['name'].lower() or 'commit' in item['url'].lower():
                sha = parse_sha_from_commit_reference(item['name'], item['url'])
                if sha:
                    logging.info(sha)
                    commits.append(sha)
                    if repo_url == norepo:
                        repo_url = parse_repository_url_from_references(package_id, package, item['url'])
                        logging.info(repo_url)
                        #sql.execute('update package set repository_url=%s where id=%s',(repo_url,package_id))
                            
        # for sha in commits:
        #     try:
        #         sql.execute('insert into fix_commits values(%s,%s,%s,null,null)',(advisory_id, package_id, sha))
        #     except sql.pymysql.IntegrityError as error:
        #         if error.args[0] == sql.PYMYSQL_DUPLICATE_ERROR:
        #             pass
        #             #safely continue
        #         else:
        #             print(error)
        #             exit()
        
    
    #TODO: PR?
    '''look for both github and pull and then extract the commits involved'''
    ''' but some can be missed in the above way. check if name contain github pr as well and inspect the url'''
    # if 'github' in url and 'pull' in url:
    #     pass
    # elif 'github' in name and 'PR' in name:
    #     pass
    print('hey I am done')

def get_commit_of_release(repo, package_id, release):
    logging.info(release)
    '''repo is a gitpython object, while version is a string taken from ecosystem data'''
    # get closest matching tag, go to that commit and ensure the dependency file updated to that version in recent commits, at least for npm
    tags = repo.tags
    candidate_tags = []
    for tag in tags:
        if release in tag.path:
            candidate_tags.append(tag)
    
    if not candidate_tags:
        return None
    elif len(candidate_tags) == 1:
        tag = candidate_tags[0]
    else:
        logging.info('too many tags')
        print(candidate_tags)
        package = sql.execute('select name from package where id=%s',(package_id,))[0]['name']
        new_candidates = []
        for tag in candidate_tags:
            if package in tag.path:
                new_candidates.append(tag)
        candidate_tags = new_candidates
    
    if not candidate_tags:
        return None
    elif len(candidate_tags) == 1:
        tag = candidate_tags[0]
    else:
        logging.info('still too many tags')
        print(candidate_tags)
        exit()

    try:
        #tag object is not guaranteed to have a message attribute
        sql.execute('update release_info set tage_message=%s where package_id=%s',(tag.message,package_id))
    except:
        pass

    return tag.commit

def analyze_diff(diff):
    pass

def update_fix_commit_info(repo, package_id):
    results = sql.execute('select * from fix_commits where package_id=%s',(package_id))
    for item in results:
        sha = item['commit_sha']
        try:
            commit_date = dt.parse(repo.git.show("--no-patch --no-notes --pretty=%cd {}".format(sha).split()))
            sql.execute('update fix_commits set commit_date=%s where package_id=%s and commit_sha=%s',(commit_date,package_id,sha))
        except:
            #bad commit object, inspect why
            logginf.info('bad commit object')
            print(sha, package_id)
            exit()

def sanitize_repo_url(repo_url):
    http = 'https://'
    assert repo_url.startswith(http)
    s = repo_url[len(http):]
    
    #below rule covers github, gitlab, bitbucket, foocode, eday, qt
    s = http + '/'.join(s.split('/')[:3])

    return s

def clone_git_repository(url):
    url = sanitize_repo_url(url)
    repo_name = url.split('/')[-1]

    os.chdir(repo_path)
    os.system('git clone {}.git > clone.log 2>&1'.format(url))

    try:
        repo = Repo(root_path + '/temp/' + repo_name)
        return repo
    except:
        print("invalid url:")
        logging.info(url)
        exit()

def analyze_change_complexity():
    q='''select *
            from advisory a
            join fixing_releases fr on a.id = fr.advisory_id
            join release_info ri on fr.version = ri.version and ri.package_id=a.package_id
            join package p on a.package_id = p.id
            where repository_url is not null
            and repository_url != %s;'''
    results = sql.execute(q,(norepo,))
    
    t = 0
    for item in results:
        repo_url, package_id, release, prior_release = item['repository_url'], item['package_id'], item['ri.version'], item['prior_release']
        print(repo_url, package_id, release, prior_release)
        repo = clone_git_repository(repo_url)

        #update commit dates in fix commits
        update_fix_commit_info(repo, package_id)

        cur_commit, prior_commit = get_commit_of_release(repo, package_id, release), get_commit_of_release(repo, package_id, prior_release)
        print(cur_commit, prior_commit)
        #TODO update db and get diff between the two and analyze complexity 

        t+=1
        if t>=5:
            break
        # os.chdir(root_path + '/temp/')
        # os.system('rm -rf {}'.format(repo_name))



if __name__=='__main__':
    #analyze_change_complexity()
    get_fix_commits()

