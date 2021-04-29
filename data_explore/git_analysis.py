import common, sql, githubapi, diff
import requests, json
import os, json
import subprocess, shlex
from dateutil import parser as dt
import logging, coloredlogs
from git import Repo
coloredlogs.install()
from pathlib import Path
root_path = '/Volumes/nasifhdd'
import common
import dateutil
import difflib
import re
import shutil
data_path = root_path +'/temp'
invalid_git_remote = 'invalid remote git url'
from changelog import locate_changelog
import pandas as pd
from multiprocessing import Pool

def is_git_repository(path):
    os.chdir(path)
    files = subprocess.check_output(shlex.split('ls -a'), stderr = subprocess.STDOUT, encoding = '437').split()
    return '.git' in files

def clone_git_repository(package_id, repo_url):
    #custom path for big repos
    if repo_url == 'https://github.com/liferay/liferay-portal':
        return '/Users/nasifimtiaz/repos/liferay-portal'
    if repo_url.startswith('https://hg.') or repo_url.startswith('https://svn.'):
        return invalid_git_remote
    ignore_urls = ['https://gradle.com']
    if repo_url in ignore_urls:
        return invalid_git_remote 

    url = sanitize_repo_url(repo_url)
    repo_name = url.split('/')[-1]
    
    repo_path = data_path + '/{}/{}'.format(package_id,repo_name) #already exists or to be created here
    if Path(repo_path).is_dir() and is_git_repository(repo_path):
        os.chdir(repo_path)
        os.system('git pull > pull.log 2>&1')
        return repo_path
    
    os.chdir(data_path)
    try:
        os.mkdir(str(package_id))
    except FileExistsError:
        os.system('rm -rf ./{} > rm.log 2>&1'.format(package_id))
        os.mkdir(str(package_id))
    os.chdir('./{}'.format(package_id))
    os.system('git clone {}.git > {}_clone.log 2>&1'.format(url, repo_name))

    if Path(repo_path).is_dir() and is_git_repository(repo_path):
        return repo_path
    else:
        print("invalid url:")
        logging.info(url)
        return invalid_git_remote
        
def sanitize_repo_url(repo_url):
    http = 'https://'
    assert repo_url.startswith(http)
    
    s='https://gitbox.apache.org/repos/asf?p='
    url = repo_url
    if url.startswith(s):
        url = url[len(s):]
        assert url.count('.git') == 1
        url = url[:url.find('.git')]
        return 'https://gitbox.apache.org/repos/asf/'+url

    
    s = repo_url[len(http):]

    #custom
    if s.startswith('svn.opensymphony.com'):
        return repo_url

    #below rule covers github, gitlab, bitbucket, foocode, eday, qt
    sources = ['github', 'gitlab', 'bitbucket', 'foocode', 'eday', 'q', 'opendev']
    flag = False
    for source in sources:
        if source in s:
            flag = True
    assert flag

    if s.endswith('.git'):
        s=s[:-len('.git')]
    s = http + '/'.join(s.split('/')[:3])

    return s

def check_commit_validity(repo_path, sha):
    os.chdir(repo_path)
    assert len(sha)==39 or len(sha) == 40
    try:
        output = subprocess.check_output(shlex.split('git cat-file -t {}'.format(sha)), 
                    stderr = subprocess.STDOUT, encoding="437").strip()
        return output == 'commit'
    except:
        return False

def get_commit_date_from_local_repo(path, sha):
    os.chdir(path)
    commit_date = dt.parse(subprocess.check_output(shlex.split("git show --no-patch --no-notes --pretty=%cd {}".format(sha)),
                            stderr= subprocess.STDOUT, encoding = '437'))
    commit_date = commit_date.astimezone(dateutil.tz.tzutc())
    return commit_date

def get_author_date_from_local_repo(path, sha):
    os.chdir(path)
    author_date = dt.parse(subprocess.check_output(shlex.split("git show --no-patch --no-notes --pretty=%ad {}".format(sha)),
                            stderr= subprocess.STDOUT, encoding = '437'))
    author_date = author_date.astimezone(dateutil.tz.tzutc())
    return author_date

def get_commit_message_from_local_repo(repo_path,sha):
    os.chdir(repo_path)
    msg =  subprocess.check_output(shlex.split("git log --format=%B -n 1 {}".format(sha)),
                            stderr= subprocess.STDOUT, encoding = '437')
    return msg.strip()

def get_commit_of_release(tags, package, release):
    '''tags is a gitpython object, while release is a string taken from ecosystem data'''
    release = release.strip()
    release_tag = None #store return value
    candidate_tags = []
    for tag in tags:
        if tag.name.strip().endswith(release):
            candidate_tags.append(tag)
    if not candidate_tags:
        for tag in tags:
            if tag.name.strip().endswith(release.replace('.','-')) or tag.name.strip().endswith(release.replace('.','_')):
                candidate_tags.append(tag)  
    
    if len(candidate_tags) == 1:
        release_tag = candidate_tags[0]
    elif len(candidate_tags) > 1:
        new_candidates = []
        for tag in candidate_tags:
            if package in tag.name:
                new_candidates.append(tag)
        candidate_tags = new_candidates
    
    if not release_tag:
        if len(candidate_tags) == 1:
            release_tag = candidate_tags[0]
        elif len(candidate_tags) > 1:
            print('too many candidate tags')
            logging.info(candidate_tags)
            exit()
        else:
            #in previous pass there were too many candidate tags, e.g., 2.4.3 , v2.4.3
            #not considering them to be fully sure
            pass      

    if release_tag:
        return release_tag.commit
    return None

def get_full_sha_for_short_shas(repo_path, sha):
    os.chdir(repo_path)
    fullsha= subprocess.check_output(shlex.split("git rev-parse {}".format(sha)),
                            stderr= subprocess.STDOUT, encoding = '437')
    fullsha = fullsha.strip()
    assert len(fullsha) == 39 or len(fullsha) == 40
    return fullsha

def process_fix_commit_dates():
    
    def get_referenced_urls(advisory_id, sha):
        q='''select url from processed_reference_url
                where advisory_id=%s
                and sha = %s;'''
        results = sql.execute(q,(advisory_id,sha))
        urls = set()
        for item in results:
            url = common.parse_repository_url_from_references(item['url'])
            urls.add(url)
        return urls
    
    def is_repo_matched(advisory_id, sha, repo_url):
        repo_url = sanitize_repo_url(repo_url)
        reference_urls = get_referenced_urls(advisory_id, sha)
        for url in reference_urls:
            print("two urls:" ,url, repo_url)
            if 'opendev' in url:
                url = requests.get(url).url
                if repo_url.split('/')[-1] in url:
                    return True
            if 'bitbucket' in url:
                if repo_url.split('/')[-1] == url.split('/')[-1]:
                    return True
            if 'repos/asf?p=' in url and '.git' in url:
                package = url[url.find('repos/asf?p=') + len ('repos/asf?p='):]
                package = package[:package.find('.git')]
                if package in repo_url:
                    return True
            
            if url in common.repos_to_avoid:
                return False

            url = sanitize_repo_url(url)
            if repo_url ==  url:
                return True
            if requests.get(url).url == repo_url or requests.get(repo_url).url == url:
                return True
        return False

    q = '''select *
            from fix_commits fc
            join package p on fc.package_id = p.id
            where ecosystem = 'Go'
            and commit_date is null
            and invalid is null
            and repository_url != %s
            and commit_sha != 'not git';'''
    results = sql.execute(q, (common.norepo,))
    c=0
    for item in results:
        advisory_id, package_id, repo_url, sha = item['advisory_id'], item['package_id'], item['repository_url'], item['commit_sha']
        print(advisory_id, package_id, repo_url, sha)
        repo_path = clone_git_repository(package_id, repo_url)
        if repo_path == invalid_git_remote:
            sql.execute('update fix_commits set invalid = %s where advisory_id =%s and package_id =%s and commit_sha = %s',(invalid_git_remote, advisory_id, package_id, sha ))
            continue 
        if sha.startswith('short commit: '):
            if is_repo_matched(advisory_id, sha, repo_url):
                original = sha
                short_sha = sha[len('short commit: '):]
                sha = get_full_sha_for_short_shas(repo_path, short_sha)
                sql.execute('update fix_commits set commit_sha = %s where advisory_id =%s and commit_sha = %s',(sha, advisory_id, original))
                sql.execute('update processed_reference_url set sha = %s where advisory_id =%s and sha = %s',(sha, advisory_id, original))
                print('full sha from short',short_sha, sha)
            else:
                sql.execute('update fix_commits set invalid = %s where advisory_id =%s and package_id =%s and commit_sha = %s',('repo not matched', advisory_id, package_id, sha ))  
                continue
        valid_commit = check_commit_validity(repo_path, sha)
        commit_date = author_date = None
        if valid_commit:
            if is_repo_matched(advisory_id, sha, repo_url):
                commit_date, author_date = get_commit_date_from_local_repo(repo_path, sha), get_author_date_from_local_repo(repo_path,sha)
            #hand checked custom
            elif (repo_url == 'https://github.com/ckeditor/ckeditor5/tree/master/packages/ckeditor5-link' and sha == 'a23590ec1e4742f2483350af1332bd209c780e1a') \
                or (repo_url == 'https://github.com/apollographql/federation/tree/master/gateway-js/' and sha == '8f7ffe43b05ab8200f805697c6005e4e0bca080a') \
                    or sha == '47cef07bb09779df15620799f3763d1b8d32307a' or sha == 'f6e0f545401a1b039a54605dba2d7afa5a6477e2' or \
                    (advisory_id == 'SNYK-JAVA-ORGAPACHEQPID-30714' and sha == '669cfff838d2798fa89b9db546823e6245433d4e'):
                commit_date, author_date = get_commit_date_from_local_repo(repo_path, sha), get_author_date_from_local_repo(repo_path,sha) 
            else:
                # check commit messages as a reliable heuristic
                msg = get_commit_message_from_local_repo(repo_path,sha)
                reference_urls = get_referenced_urls(advisory_id, sha)
                flag = False 
                for url in reference_urls:
                    logging.info(url)
                    if 'github' in url:
                        repo_name = '/'.join(url.split('/')[-2:])
                        endpoint='https://api.github.com/repos/{}/commits/{}'.format(repo_name,sha)
                        commit = githubapi.rest_call(endpoint)
                        assert 'commit' in commit.keys()
                        reference_msg = commit['commit']['message'].strip()
                        print('difference is: ', [li for li in difflib.ndiff(msg, reference_msg) if li[0] != ' '])
                        if msg.replace('\r','') == reference_msg.replace('\r',''):
                            flag=True
                            break
                if flag:
                    commit_date, author_date = get_commit_date_from_local_repo(repo_path, sha), get_author_date_from_local_repo(repo_path,sha)
                else:
                    print('here came, not sure about this case',)
                    #check the custome queries
                    exit()
        else:
            if is_repo_matched(advisory_id, sha, repo_url):
                #https://docs.github.com/en/github/committing-changes-to-your-project/commit-exists-on-github-but-not-in-my-local-clone
                url = sanitize_repo_url(repo_url)
                repo_name = '/'.join(url.split('/')[-2:])
                endpoint='https://api.github.com/repos/{}/commits/{}'.format(repo_name,sha)
                commit = githubapi.rest_call(endpoint)
                if 'commit' not in commit.keys():
                    sql.execute('update fix_commits set invalid = %s where advisory_id =%s and package_id =%s and commit_sha = %s',('invalid github link', advisory_id, package_id, sha ))  
                else:
                    commit_date, author_date = dt.parse(commit['commit']['committer']['date']), dt.parse(commit['commit']['author']['date'])
                    commit_date, author_date = commit_date.astimezone(dateutil.tz.tzutc()), author_date.astimezone(dateutil.tz.tzutc())
            else:
                sql.execute('update fix_commits set invalid = %s where advisory_id =%s and package_id =%s and commit_sha = %s',('repo not matched', advisory_id, package_id, sha ))  
        if commit_date:
            assert author_date
            sql.execute('update fix_commits set commit_date = %s, author_date = %s where advisory_id =%s and package_id =%s and commit_sha = %s',(commit_date, author_date, advisory_id, package_id, sha ))       
    
    logging.info('FIX COMMIT DATE PROCESSING DONE')

def parse_release_type(release):
    if '-' in release or release.count('.') > 2:
        return 'prerelease'

    parts = release.split('.')
    
    if len(parts) == 3 and int(parts[-1]) > 0:
        return 'patch'
    
    if len(parts) > 1 and int(parts[1]) > 0:
        return 'minor'
    
    return 'major'

def process_all_release_commits(repo_url):
    conn = sql.create_db_connection() # a connection specific for this function which goes into multiprocessing

    def results_per_package(repo_url):
        q='''select *
            from advisory a
            join fixing_releases fr on a.id = fr.advisory_id
            join release_info ri on fr.version = ri.version and ri.package_id=a.package_id
            join package p on a.package_id = p.id
            where repository_url is not null
            and repository_url != %s
            and ecosystem != 'Go'
            and ri.version != 'manual checkup needed'
            and prior_release != 'manual checkup needed' 
            and (concat(a.package_id, ri.version) not in
            (select concat(package_id, version) from release_commit)
            or concat(a.package_id, ri.prior_release) not in
            (select concat(package_id, version) from release_commit))
            and p.repository_url = %s'''
        results = sql.execute(q,(common.norepo, repo_url), connection  = conn)
        return results

    results = results_per_package(repo_url)
    package_id = results[0]['package_id']
    repo_path = clone_git_repository(package_id, repo_url)
    if repo_path == invalid_git_remote:
        #logging.info(repo_path)
        return 
    os.chdir(repo_path)
    repo = Repo(repo_path)
    assert not repo.bare 
    tags = repo.tags
    
    for item in results:
        advisory_id, package_id, package_name, release, prior_release = item['advisory_id'], item['package_id'], item['name'], item['ri.version'], item['prior_release']
        print(package_id, release, prior_release)
        releases = [release, prior_release]
        for release in releases:
            if release == common.manualcheckup:
                return 
            head_commit = get_commit_of_release(tags, package_name, release)
            try:
                sql.execute('insert into release_commit values(%s,%s,%s)',(package_id, release, head_commit), connection = conn)
            except sql.pymysql.IntegrityError as error:
                if error.args[0] == sql.PYMYSQL_DUPLICATE_ERROR:
                    pass
                    #safely continue
                else:
                    print(error)
                    exit() 
    
    conn.close()

def get_release_commits():
    q='''select distinct p.repository_url
        from advisory a
        join fixing_releases fr on a.id = fr.advisory_id
        join release_info ri on fr.version = ri.version and ri.package_id=a.package_id
        join package p on a.package_id = p.id
        where repository_url is not null
        and repository_url != %s
        and ecosystem != 'Go'
        and ri.version != 'manual checkup needed'
        and prior_release != 'manual checkup needed' 
        and (concat(a.package_id, ri.version) not in
        (select concat(package_id, version) from release_commit)
        or concat(a.package_id, ri.prior_release) not in
        (select concat(package_id, version) from release_commit))
        '''
    repository_urls = sql.execute(q,(common.norepo,))
    repo_urls = [row['repository_url'] for row in repository_urls]
    pool = Pool(os.cpu_count())
    pool.map(process_all_release_commits, repo_urls)          

def acc_mp(item):
    #multiprocessing function for analyze_change_complexity
    conn = sql.create_db_connection()

    def get_commit_head(package_id, version):
        q='''select *
            from release_commit
            where package_id =%s and version = %s'''
        results = sql.execute(q,(package_id, version))
        assert len(results) == 1
        if results:
            return results[0]['commit']
        else:
            return None

    l = []
    for k in item.keys():
        l.append(item[k])
    advisory_id, package_id, repo_url, release_id, fixing_release, prior_release = l
    print(advisory_id, package_id, repo_url, release_id, fixing_release, prior_release)

    repo_path = clone_git_repository(package_id, repo_url)
    if repo_path == invalid_git_remote:
        return

    fixing_relese_commit = get_commit_head(package_id, fixing_release)
    prior_release_commit = get_commit_head(package_id, prior_release)

    if not fixing_relese_commit or not prior_release_commit:
        return
    
    release_type = parse_release_type(fixing_release)
    try:
        sql.execute('insert into release_type values(%s,%s)',(release_id, release_type), connection = conn)
    except sql.pymysql.IntegrityError as error:
        if error.args[0] == sql.PYMYSQL_DUPLICATE_ERROR:
            pass
            #safely continue
        else:
            print(error)
            exit() 

    commits, files = diff.change_complexity(repo_path, prior_release_commit, fixing_relese_commit)

    for k in commits.keys():
        try:
            sql.execute('insert into change_commit values(%s,%s,%s,%s,%s,%s)',
                        (release_id, k, commits[k]['author_name'],commits[k]['author_email'],commits[k]['committer_name'],commits[k]['committer_email'] ),
                        connection = conn)
        except sql.pymysql.IntegrityError as error:
            if error.args[0] == sql.PYMYSQL_DUPLICATE_ERROR:
                pass
                #safely continue
            else:
                print(error)
                exit() 
    
    for k in files.keys():
        try:
            sql.execute('insert into change_file values(%s,%s,%s,%s)',
                    (release_id,k,files[k]['loc_added'],files[k]['loc_removed']),
                    connection = conn)
        except sql.pymysql.IntegrityError as error:
            if error.args[0] == sql.PYMYSQL_DUPLICATE_ERROR:
                pass
                #safely continue
            else:
                print(error)
                exit() 
    
    conn.close()

def analyze_change_complexity():
    q = '''select advisory_id, p.id as package_id, repository_url, ri.id as release_id, ri.version as fixing_release, prior_release
            from advisory a
            join package p on a.package_id = p.id
            join fixing_releases fr on a.id = fr.advisory_id
            join release_info ri on p.id = ri.package_id and ri.version = fr.version
            where ri.prior_release != %s
            and (
                    ri.id not in (select release_info_id from change_file) or
                    ri.id not in (select release_info_id from change_commit) or
                    ri.id not in (select release_info_id from release_type)
                )
            and ecosystem != 'Maven' '''
    results = sql.execute(q,(common.manualcheckup,))
    pool  = Pool(os.cpu_count())
    pool.map(acc_mp, results)
      

def get_changelog():
    q = '''select distinct a.package_id, repository_url
        from advisory a
        join package p on a.package_id = p.id
        join fixing_releases fr on a.id = fr.advisory_id
        join manual_sample ms on a.id = ms.advisory_id
        where a.type != 'Malicious Package'
        and version != 'manual checkup needed'
        and p.ecosystem != 'cocoapods'
        and repository_url != 'no repository listed'
        and a.package_id not in
        (select package_id from changelog);'''
    results = sql.execute(q)
    
    for item in results:
        package_id, repo_url = item['package_id'], item['repository_url']
        print('processing ',package_id)
        repo_name = repo_url.split('/')[-1]
        repo_path = clone_git_repository(package_id, sanitize_repo_url(repo_url))  
        if repo_path == invalid_git_remote:
            continue

        candidates = locate_changelog(repo_path)
        changelog_urls = []
        for s in candidates:
            s = s[len('/Users/nasifimtiaz/repos/advisory-lifecycle/data_explore/temp/{}/{}'.format(package_id,repo_name)):]
            s = sanitize_repo_url(repo_url) + '/blob/master' + s
            changelog_urls.append(s)
        
        if not changelog_urls:
            sql.execute('insert into changelog values(%s,%s)',(package_id,'no changlog found in script'))
        else:
            for url in changelog_urls:
                sql.execute('insert into changelog values(%s,%s)',(package_id,url))


        os.chdir('../..')
        shutil.rmtree('./{}'.format(package_id), ignore_errors=True)

def get_tag_date(path, tag):
    os.chdir(path)
    tag_date = dt.parse(subprocess.check_output(shlex.split('git for-each-ref --format="%(creatordate)" "{}"'.format(tag.path)),
                            stderr= subprocess.STDOUT, encoding = '437'))
    tag_date = tag_date.astimezone(dateutil.tz.tzutc())
    return tag_date

def get_all_tags(package_id, repo_url):
    url = sanitize_repo_url(repo_url)
    repo_path = clone_git_repository(package_id, repo_url)
    repo = Repo(repo_path)
    if repo_path == invalid_git_remote:
        logging.info(repo_path)
        return []
    os.chdir(repo_path)
    repo = Repo(repo_path)
    assert not repo.bare

    tags = repo.tags
    releases = {}
    for tag in tags:
        releases[tag.name] = {}
        releases[tag.name]['pd_commit'] = tag.commit
        releases[tag.name]['tag_date'] = get_tag_date(repo_path,tag)

    return releases
        
if __name__=='__main__':
    #process_fix_commit_dates()
    #get_release_commits()
    analyze_change_complexity()
    #get_changelog()