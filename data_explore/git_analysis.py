import common, sql, githubapi
import requests, json
import os, json
import subprocess, shlex
from dateutil import parser as dt
import logging, coloredlogs
coloredlogs.install()
from pathlib import Path
root_path = os.getcwd()
import common
import dateutil
import difflib
import re
data_path = root_path +'/temp'
invalid_git_remote = 'invalid remote git url'

def is_git_repository(path):
    os.chdir(path)
    files = subprocess.check_output(shlex.split('ls -a'), stderr = subprocess.STDOUT, encoding = '437').split()
    return '.git' in files

def clone_git_repository(package_id, repo_url):
    url = sanitize_repo_url(repo_url)
    repo_name = url.split('/')[-1]
    
    repo_path = data_path + '/{}/{}'.format(package_id,repo_name) #already exists or to be created here
    if Path(repo_path).is_dir() and is_git_repository(repo_path):
        return repo_path
    

    os.chdir(data_path)
    try:
        os.mkdir(str(package_id))
    except FileExistsError:
        os.system('rm -rf ./{}'.format(package_id))
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
    s = repo_url[len(http):]
    
    #below rule covers github, gitlab, bitbucket, foocode, eday, qt
    sources = ['github', 'gitlab', 'bitbucket', 'foocode', 'eday', 'q']
    flag = False
    for source in sources:
        if source in s:
            flag = True
    assert flag

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
            print(url, repo_url)
            url = sanitize_repo_url(url)
            if repo_url ==  url:
                return True
            if requests.get(url).url == repo_url or requests.get(repo_url).url == url:
                return True
        return False

    q = '''select *
            from fix_commits fc
            join package p on fc.package_id = p.id
            where ecosystem = 'npm'
            and commit_date is null
            and invalid is null;'''
    results = sql.execute(q)
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
                    or sha == '47cef07bb09779df15620799f3763d1b8d32307a' or sha == 'f6e0f545401a1b039a54605dba2d7afa5a6477e2':
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



if __name__=='__main__':
    #print(is_git_repository('/Users/nasifimtiaz/repos/advisory-lifecycle/data_explore/temp'))
    #print(get_commit_date_from_local_repo('/Users/nasifimtiaz/repos/advisory-lifecycle/data_explore/temp/salt','955d7304719b26ad6ab8dcff902f9692a919c280'))
    process_fix_commit_dates()
    