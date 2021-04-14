from pydriller import RepositoryMining

repo_path = '/Users/nasifimtiaz/repos/advisory-lifecycle/data_explore/temp/kafe'
prior_release = '23a7af9bee56dd95600505ee1a14fbcc2abe54c6'
cur_release = '2b3851e1508b58f3f417457317fd688796c61c2c'


def change_complexity(repo_path, prior_release_commit, cur_release_commit):
    commit_count = loc_change = 0
    files = set()
    authors = set()
    committers = set()
    methods = set()
    ''' we will filter out: 1. merge commits?
        potentially: commits by bot?'''

    for commit in RepositoryMining(repo_path, from_commit = prior_release_commit,\
                        to_commit =cur_release_commit, only_no_merge = True).traverse_commits():
        if commit.hash == prior_release_commit:
            continue

        commit_count += 1
        
        for m in commit.modifications:
            files.add(m.filename)
            parsed_diff = m.diff_parsed
            loc_change += m.added + m.removed 
            #print(m.changed_methods) #changed methods is broken for most programming lan?
            map(methods.add, m.changed_methods)
        
        if 'bot' not in commit.committer.name:
            authors.add((commit.author.name, commit.author.email))
            committers.add((commit.committer.name, commit.committer.email))
        else:
            logging.info(commit.committer.name)
    
    print(authors)
    return commit_count, len(files), loc_change, len(methods), len(authors)

print(change_complexity(repo_path, prior_release, cur_release))


                    
