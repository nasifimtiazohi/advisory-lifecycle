import common, sql
import os, json
import subprocess, shlex
from dateutil import parser as dt

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

def sanitize_repo_url(repo_url):
    http = 'https://'
    assert repo_url.startswith(http)
    s = repo_url[len(http):]
    
    #below rule covers github, gitlab, bitbucket, foocode, eday, qt
    s = http + '/'.join(s.split('/')[:3])

    return s

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
    pass



