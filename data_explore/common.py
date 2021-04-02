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
notgit = 'not git'
short_commits = 0
import collections
import githubapi



bitbucket_urls = [
    #bitbucket repos are private and may be mercurial 
    'https://bitbucket.org/rick446/easywidgets/commits/cb446d6b0b5f9597c3761e61facfa1fac34b8e5c?at=default',
    'https://bitbucket.org/conservancy/kallithea/commits/ae947de541d5630e5505c7c8ded05cd37c7f232b?at=0.2',
    'https://bitbucket.org/cthedot/cssutils/commits/4077971c214b4f2eb4889a3ff0cb940e9e5d26a5?at=TAG_0.9.6a2',
    'https://bitbucket.org/cthedot/cssutils/commits/4ff52ad59c129e908a9250fd00cfed1aaf9d15f8?at=TAG_0.9.6a2',
    'https://bitbucket.org/birkenfeld/pygments-main/commits/0036ab1c99e256298094505e5e92fdacdfc5b0a8',
    'https://bitbucket.org/birkenfeld/pygments-main/commits/6b4baae517b6aaff7142e66f1dbadf7b9b871f61?at=default',
    'https://bitbucket.org/ianb/paste/commits/fcae59df8b56d2587e295593bee8a6d517ef2105',
    'https://bitbucket.org/rick446/easywidgets/pull-requests/3'
]

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
            return parse_sha_from_github_PR_reference(url)
        
        if 'svn.apache.org' in url:
            return [notgit]
        
        if 'github.com' in url and 'commit/' in url:
            s='commit/'
            sha = url[url.find(s) +len(s):]
            if len(sha) < 40:
                sha = 'short commit: ' + sha 
                return [sha]
        
        if 'bitbucket' in url and 'commits/' in url:
            s='commits/'
            sha = url[url.find(s) +len(s):]
            if len(sha) < 40:
                sha = 'short commit: ' + sha 
                return [sha]
            
        if 'compare' in url:
            return []
        
        invalid_urls =[
            'https://github.com/theupdateframework/tuf/commits/develop',
            'https://github.com/alkacon/apollo-template/commits/branch_10_5_x',
            'https://hg.tryton.org/trytond/rev/f58bbfe0aefb',
        ]
        if url in invalid_urls or url in bitbucket_urls:
            return []

        #custom data, hand curated
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
        if url == 'https://github.com/AsyncHttpClient/async-http-client/issues/197':
            return ['db6716ad2f10f5c2d5124904725017b2ba8c3434']
        if url == 'https://git-wip-us.apache.org/repos/asf?p=qpid-jms.git;h=669cfff':
            return '669cfff838d2798fa89b9db546823e6245433d4e'
        if url == 'https://bitbucket.org/ianb/virtualenv/changeset/8be37c509fe5':
            return ['92c20503841d3d687fc2cbd1da9d42a5dee38dbf','c90b0daf83c610f3df4cd78e4c9ff925e6105c0f']
        if url == 'https://github.com/nprapps/pym.js/issues/170':
            return ['c3552a6cf2532664c17bd6a318fb3cf8e4cf2f97']
        if url == 'http://git.moodle.org/gw?p=moodle.git&a=search&h=HEAD&st=commit&s=MDL-69340':
            return ['e8632a4ad0b4da3763cbbe5949594aa449b483bb']
        if url == 'http://git.moodle.org/gw?p=moodle.git&a=search&h=HEAD&st=commit&s=MDL-64410':
            return ['54c2b176040c4cd65d921bf10123b5146eb486f5','fe41810304f282feaffede659232a5e2c825d344']
        if url == 'http://git.moodle.org/gw?p=moodle.git&a=search&h=HEAD&st=commit&s=MDL-64706':
            return ['c430bed525c4c7e6e5a1c0f7222bc323cf9b6245']
        if url == 'http://git.moodle.org/gw?p=moodle.git&a=search&h=HEAD&st=commit&s=MDL-62702':
            return ['898d5d05a0c3ae6795db0241bf3cb5951213d45c','1a8b1f2724a651220133ee5dcc9362980b91e1f0','d8a7e1f78d8c5ab49bcdf1f334b316837791a28a']
        if url == 'http://git.moodle.org/gw?p=moodle.git&a=search&h=HEAD&st=commit&s=MDL-68410':
            return ['2cd534a7df3867813e3aad42db615865149a58c6']
        if url == 'https://github.com/bcgit/bc-java/commit/5cb2f05':
            return ['5cb2f0578e6ec8f0d67e59d05d8c4704d8e05f83']
        if url == 'https://gitbox.apache.org/repos/asf?p=activemq.git;h=aa8900c':
            return ['aa8900ca70e6f9422490c1a03627400375d3ff83']
        

        if 'git.moodle.org' in url:
            #there are five for the same package moodle. check manually
            return [manualcheckup]
        if 'gitbox.apache.org' in url:
            return [manualcheckup]
        # anonscm - last 40 chars but only for cocoapods and link not working - so don't bother

    logging.info(url)
    exit()
    return [manualcheckup]

def parse_sha_from_github_compares(name,url):
    if url == 'https://github.com/moby/moby/compare/769acfec2928c47a35da5357d854145b1036448d...b6a9dc399be31c531e3753104e10d74760ed75a2':
        return ['3162024e28c401750388da3417a44a552c6d5011','545b440a80f676a506e5837678dd4c4f65e78660','614a9690e7d78be0501fbb0cfe3ecc7bf4fca638','b6a9dc399be31c531e3753104e10d74760ed75a2']
    pass

def parse_sha_from_github_PR_reference(url):
    logging.info(url)
    prefix = 'https://github.com/'

    if url == 'https://cwiki.apache.org/confluence/display/WW/S2-054':
        return []
    if url == 'https://review.opendev.org/725894':
        return ['ba89d27793c2d3a26ad95642660fa9bd820ed3be']
    if url in bitbucket_urls:
        return []
    assert url.startswith(prefix)

    redundunt_urls = [
        'https://github.com/josdejong/mathjs/issues/821',
        'https://github.com/josdejong/mathjs/issues/822',
        'https://github.com/davideicardi/confinit/issues/1',
        'https://github.com/geminabox/geminabox/blob/master/CHANGELOG.md#01310-2017-11-13'
    ]
    if url == 'https://github.com/shopware/platform/search?q=NEXT-9174&type=Commits':
        return ['fb7c8909404bdbb51194f149c1c7950d38ca2f97','78f3728a342359dc033a0994d2277e1ddbe53769']
    if url == 'https://github.com/nhn/tui.editor/issues/733':
        return ['4a68b068a1389c3f31ca587008a4afe53e3ced0b','91f8421947bce6c3a0ce602c95186f338adb5ad3']
    if url in redundunt_urls:
        return []
    if 'pull' not in url and '/commit/' in url:
        #already heandled in commit case
        return []
    if url == 'https://github.com/node-modules/charset/issues/10':
        url = 'https://github.com/node-modules/charset/pull/11'

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
    commits = githubapi.rest_call(endpoint)
    if not isinstance(commits, list):
        logging.info(str(commits))
        exit()
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
    elif url in bitbucket_urls:
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
                    if manualcheckup in sha:
                        print(item['url'])
                        logging.info(sha)
                        exit()
                    commits.append(sha)
                    if repo_url == norepo:
                        repo_url = parse_repository_url_from_references(package_id, package, item['url'])
                        logging.info(repo_url)
                        #sql.execute('update package set repository_url=%s where id=%s',(repo_url,package_id))
                        #sql.execute('insert into repository_inferred values(%s)',(package_id,))
            if 'pull' in item['name'].lower() or 'PR' in item['name'] or '/pull/' in item['url'].lower():
                sha = parse_sha_from_github_PR_reference(item['url'])
                if sha:
                    if manualcheckup in sha:
                        print(item['url'])
                        logging.info(sha)
                        exit()
                    commits.append(sha)
                    if repo_url == norepo:
                        repo_url = parse_repository_url_from_references(package_id, package, item['url'])
                        logging.info(repo_url)

                            
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

