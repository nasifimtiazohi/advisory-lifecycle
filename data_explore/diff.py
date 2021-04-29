from pydriller import RepositoryMining
import logging
logging.basicConfig()
logger = logging.getLogger('BBProposalGenerator')
logger.setLevel(logging.INFO)


def change_complexity(repo_path, prior_release_commit, cur_release_commit):
    commits = {}
    files = {}
    
    ''' we will filter out: 1. merge commits from commit count
        2. bots from author count; [bot] in login'''

    for commit in RepositoryMining(repo_path, from_commit = prior_release_commit,\
                        to_commit =cur_release_commit, only_no_merge = True).traverse_commits():
        if commit.hash == prior_release_commit:
            continue

        c = {
            'author_name': commit.author.name,
            'author_email': commit.author.email,
            'committer_name': commit.committer.name,
            'committer_email': commit.committer.email
        }
        assert commit.hash not in commits
        commits[commit.hash] = c

        
        for m in commit.modifications:
            file = m.new_path
            if not file:
                file = m.old_path
            assert file

            if file not in files:
                files[file] = {
                    'loc_added' : 0,
                    'loc_removed': 0
                }

            files[file]['loc_added'] += m.added
            files[file]['loc_removed'] += m.removed
        
    return commits, files



if __name__ == '__main__':
    repo_path = '/Volumes/nasifhdd/temp/26/url-parse'
    prior_release = 'bc9da1ec19a86199be663a7f0ba40091834d73f7'
    cur_release = 'b21a365bc441d8be4022458266a4d9f311a725a6'
    print(change_complexity(repo_path, prior_release, cur_release))

