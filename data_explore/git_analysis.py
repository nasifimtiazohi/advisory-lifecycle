import common, sql
import os, json
import subprocess, shlex
from dateutil import parser as dt
import logging, coloredlogs
coloredlogs.install()
from pathlib import Path
root_path = os.getcwd()
data_path = root_path +'/temp'

def is_git_repository(path):
    #do ls -a, check if .git is there
    return True

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
        Path('./{}'.format(package_id)).rmdir()
        os.mkdir(str(package_id))
    os.chdir('./{}'.format(package_id))
    os.system('git clone {}.git > {}_clone.log 2>&1'.format(url, repo_name))

    if Path(repo_path).is_dir() and is_git_repository(repo_path):
        return repo_path
    else:
        print("invalid url:")
        logging.info(url)
        exit()
        
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

def get_commit_date():
    q = '''select *
        from fix_commits fc
        join package p on fc.package_id = p.id
        where ecosystem = 'npm';'''
    results = sql.execute(q)
    for item in results:
        package_id, repo_url, sha = item['package_id'], item['repository_url'], item['commit_sha']
        print(package_id, repo_url, sha)
        #TODO: check if short commit, then parse full commit separately
        repo_path = clone_git_repository(package_id, repo_url)
        print(check_commit_validity(repo_path, sha))
        break



if __name__=='__main__':
    get_commit_date()