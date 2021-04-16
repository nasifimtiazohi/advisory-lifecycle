import os
import subprocess, shlex

#https://keepachangelog.com/en/1.0.0/
#Call it CHANGELOG.md. Some projects use HISTORY, NEWS or RELEASES.
_changelog_keywords = ['change','history','news','release']

#https://www.infoworld.com/article/3336202/markdown-vs-alternatives-for-software-documentation.html
_documentation_formats = ['md','txt','rst', 'adoc','org',]

def is_git_repository(path):
    os.chdir(path)
    files = subprocess.check_output(shlex.split('ls -a'), stderr = subprocess.STDOUT, encoding = '437').split()
    return '.git' in files

def is_documentation(file):
    for format in _documentation_formats:
        if file.lower().endswith(format):
            return True
    return False

def locate_changelog(path):
    assert is_git_repository(path)
    candidates = []
    for root, dirs, files in os.walk(path):
        for file in files:
            for keyword in _changelog_keywords:
                if keyword in file.lower() and is_documentation(file):
                    candidates.append(os.path.join(root,file))
    return candidates
                    


if __name__=='__main__':
    print(locate_changelog('/Users/nasifimtiaz/repos/advisory-lifecycle/data_explore/temp/braces'))