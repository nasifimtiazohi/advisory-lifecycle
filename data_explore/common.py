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
norepo = 'no repository listed'
manualcheckup = 'manual checkup needed'
notgit = 'not git'
short_commits = 0
import collections
import githubapi
import semantic_version
import githubapi
import git_analysis as ga

repos_to_avoid = [
            'https://github.com/rapid7/metasploit-framework',
            'https://github.com/github/advisory-review',
            'https://github.com/rubysec/ruby-advisory-db',
            'https://salsa.debian.org/security-tracker-team/security-tracker',
            'https://github.com/FriendsOfPHP/security-advisories',
            'https://github.com/snyk/vulndb-internal'
        ]

bitbucket_urls = [
    #bitbucket repos are private and may be mercurial 
    'https://bitbucket.org/rick446/easywidgets/commits/cb446d6b0b5f9597c3761e61facfa1fac34b8e5c?at=default',
    'https://bitbucket.org/conservancy/kallithea/commits/ae947de541d5630e5505c7c8ded05cd37c7f232b?at=0.2',
    'https://bitbucket.org/cthedot/cssutils/commits/4077971c214b4f2eb4889a3ff0cb940e9e5d26a5?at=TAG_0.9.6a2',
    'https://bitbucket.org/cthedot/cssutils/commits/4ff52ad59c129e908a9250fd00cfed1aaf9d15f8?at=TAG_0.9.6a2',
    'https://bitbucket.org/birkenfeld/pygments-main/commits/0036ab1c99e256298094505e5e92fdacdfc5b0a8',
    'https://bitbucket.org/birkenfeld/pygments-main/commits/6b4baae517b6aaff7142e66f1dbadf7b9b871f61?at=default',
    'https://bitbucket.org/ianb/paste/commits/fcae59df8b56d2587e295593bee8a6d517ef2105',
    'https://bitbucket.org/rick446/easywidgets/pull-requests/3',
    'https://bitbucket.org/birkenfeld/pygments-main/pull-requests/501/fix-shell-injection-in/diff',
    'https://bitbucket.org/xi/libyaml/pull-request/1/fix-cve-2013-6393/diff'
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
        if isinstance(data[k], str) and '\n' not in data[k] and data[k].startswith('https://github.com') and package.lower() in data[k].lower():
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
        and repository_url != 'no repository listed'
        and concat(package_id, version)
        not in (select concat(package_id, version) from release_info);'''
    results =  sql.execute(q,(ecosystem,manualcheckup))
    return results
    
def parse_sha_from_commit_reference(url):
    ''' returns a list of shas'''
    links_with_40bit_sha =  ['github', 'gitlab','bitbucket','git.openssl','git.savannah','git.videolan','git-wip-us','gitbox','pagure']
    short_commit_length = 20
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
            if len(sha) < short_commit_length:
                sha = 'short commit: ' + sha 
                return [sha]
            else:
                if len(sha) == 39:
                    return [sha]

        
        if 'bitbucket' in url and 'commits/' in url:
            s='commits/'
            sha = url[url.find(s) +len(s):]
            if len(sha) < short_commit_length:
                sha = 'short commit: ' + sha 
                return [sha]
            else:
                if len(sha) == 39:
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

def parse_sha_from_github_compares(url):
    if url == 'https://github.com/moby/moby/compare/769acfec2928c47a35da5357d854145b1036448d...b6a9dc399be31c531e3753104e10d74760ed75a2':
        return ['3162024e28c401750388da3417a44a552c6d5011','545b440a80f676a506e5837678dd4c4f65e78660','614a9690e7d78be0501fbb0cfe3ecc7bf4fca638','b6a9dc399be31c531e3753104e10d74760ed75a2']
    pass

def parse_sha_from_github_PR_reference(url):
    logging.info(url)
    prefix = 'https://github.com/'

    if url == 'https://cwiki.apache.org/confluence/display/WW/S2-054':
        return []
    if url == 'https://github.com/blakeembrey/no-case/issues/17':
        return [] 
    if url == 'https://review.opendev.org/725894':
        return ['ba89d27793c2d3a26ad95642660fa9bd820ed3be']
    if url == 'https://github.com/borgbackup/borg/blob/1.1.3/docs/changes.rst#version-113-2017-11-27':
        return []
    if 'http://cxf.apache.org/security-advisories.data' in url:
        return []
    if url == 'https://github.com/shy2850/node-server/issues/10':
        return []
    if url in bitbucket_urls:
        return []
    assert url.startswith(prefix)
    for avoid in repos_to_avoid:
        if url.startswith(avoid):
            return []

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
    if url == 'https://github.com/deeplearning4j/deeplearning4j/pull/6630':
        return []
    if 'pull' not in url and '/commit/' in url:
        #already heandled in commit case
        return []
    if url == 'https://github.com/node-modules/charset/issues/10':
        url = 'https://github.com/node-modules/charset/pull/11'
    if url == 'https://github.com/openshift/origin/issues/3951':
        url = 'https://github.com/openshift/origin/pull/10830'
    if url == 'https://github.com/ask/celery/pull/544':
        url = 'https://github.com/celery/celery/pull/544/commits'

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

def parse_repository_url_from_references(url):
    if 'https://salsa.debian.org/security-tracker-team/security-tracker' in url:
        return 'https://salsa.debian.org/security-tracker-team/security-tracker'
    if 'github' in url or 'gitlab' in url:
        if url.endswith('.git'):
                url=url[:-len('.git')]
        return url[:url.find('.com/')+5] + '/'.join( url[url.find('.com/')+5:].split('/')[:2] )
    
    s='https://gitbox.apache.org/repos/asf?p='
    if url.startswith(s):
        url = url[len(s):]
        assert url.count('.git') == 1
        url = url[:url.find('.git')]
        return 'https://github.com/apache/'+url
    
    s='https://git-wip-us.apache.org/repos/asf?p='
    if url.startswith(s):
        url = url[len(s):]
        assert url.count('.git') == 1
        url = url[:url.find('.git')]
        return 'https://github.com/apache/'+url
    
    if 'https://pagure.io/ipsilon' in url:
        return 'https://github.com/ipsilon-project/ipsilon'
    
    if 'bitbucket' in url:
        return url[:url.find('.org/')+5] + '/'.join( url[url.find('.org/')+5:].split('/')[:2] )
    elif 'svn.apache.org' in url:
        return notgit
    elif url in bitbucket_urls:
        return norepo
    elif 'git.moodle.org' in url:
        return 'https://github.com/moodle/moodle'
    elif 'https://git.spip.net/spip/spip' in url:
        return 'https://github.com/spipremix/spip'
    elif 'opendev' in url:
        return url
    else:
        print ('i am here fuck it', url)
        exit() #manually inspect

def process_repo(package_id,url):
        repo_url = parse_repository_url_from_references(url)
        current_value = sql.execute('select repository_url from package where id =%s',(package_id,))[0]['repository_url']

        if repo_url in repos_to_avoid:
            return current_value
        
        if repo_url == notgit or repo_url == manualcheckup:
                return current_value

        if current_value == norepo:
            sql.execute('update package set repository_url=%s where id=%s',(repo_url,package_id))
            sql.execute('insert into repository_inferred values(%s)',(package_id,))
        else:
            archived_repos = [
                'https://github.com/bundler/bundler',
                'https://github.com/ansible/ansible-modules-core',
                'https://github.com/apache/tomcat80',
                'https://github.com/ansible/ansible-modules-extras',
                'https://github.com/apache/tomcat55',
                'https://github.com/npm/npm'
            ]
            if repo_url in archived_repos:
                return current_value
            
            ignore_packages = [288, 289, 67, 73, 163, 188, 209, 210, 242, 248, 249, 271, 272, 307, 478,480,491,531,602,706,778,844,1226,1329,2924,      3203,            3462,               3622, 3201, 3305, 3891, 
                    562, 563, 1180, 843, 875, 1192, 1193, 1243, 1267, 1314, 1319, 1332, 1390, 1391, 1506, 3742, 3889, 3895,
                    1585, 1587, 1707, 1708, 1738, 1739, 1740, 1742, 1778, 1852, 1913, 1970, 1993, 2016, 2062, 2335, 2357, 2534, 2542, 2622, 3157, 3164,
                    2684, 2848, 3086, 2905
            ]
            if package_id in ignore_packages:
                return current_value
            
            if repo_url == notgit:
                return current_value
            
            #current value sanitization
            if 'github' in current_value and current_value.endswith('.git'):
                current_value = current_value[:-4]
            if current_value.endswith('/'):
                current_value = current_value[:-1]
            if 'bitbucket' in current_value and current_value.endswith('/src'):
                current_value = current_value[:-4]
            
            

            if current_value != repo_url:
                item = sql.execute('select * from package where id =%s',(package_id,))[0]
                package_name, ecosystem = item['name'], item['ecosystem']
                if 'cefsharp' in package_name and 'cefsharp' in current_value:
                    return current_value
                if package_name in current_value and 'github' in current_value:
                    return current_value
                if 'fisheye.hudson-ci' in current_value:
                    sql.execute('update package set repository_url=%s where id=%s',(repo_url,package_id))
                    sql.execute('insert into repository_inferred values(%s)',(package_id,))
                    return repo_url
                if (package_name=='com.sksamuel.diff:diff' and repo_url=='https://github.com/kpdecker/jsdiff') \
                    or (package_name=='yiisoft/yii2' and repo_url == 'https://github.com/yiisoft/yii2') \
                    or (package_name=='org.springframework.cloud:spring-cloud-netflix-zuul' and repo_url=='https://github.com/spring-cloud/spring-cloud-netflix') \
                    or (package_name=='org.webjars.npm:electron' and repo_url =='https://github.com/electron/electron') \
                    or('com.softwaremill.akka-http-session:core' in package_name and repo_url=='https://github.com/softwaremill/akka-http-session') \
                    or (package_name=='plone.app.dexterity' and repo_url=='https://github.com/plone/plone.app.dexterity') \
                    or (package_name=='getkirby/panel' and repo_url=='https://github.com/getkirby/kirby') \
                    or (package_name=='typo3/cms-core' and repo_url=='https://github.com/TYPO3/TYPO3.CMS') \
                    or (package_name == 'froala-editor' and repo_url=='https://github.com/froala/wysiwyg-editor') \
                    or (package_name=='plone' and repo_url=='https://github.com/plone/Products.CMFPlone') \
                    or (package_name=='org.webjars.npm:vue' and repo_url == 'https://github.com/vuejs/vue') \
                    or (package_name=='org.eclipse.milo:sdk-client' and repo_url=='https://github.com/eclipse/milo') \
                    or (package_name=='org.apache.tomcat:coyote' and repo_url=='https://github.com/apache/tomcat') \
                    or (package_name=='django-allauth' and repo_url == 'https://github.com/pennersr/django-allauth') \
                    or (package_name == 'com.diffplug.spotless:spotless-maven-plugin' and repo_url == 'https://github.com/diffplug/spotless') \
                    or ('io.spray:spray-json' in package_name and repo_url == 'https://github.com/spray/spray-json') \
                    or ('io.spray:spray-httpx' in package_name and repo_url == 'https://github.com/spray/spray') \
                    or (package_name=='datatables' and repo_url == 'https://github.com/DataTables/DataTables')  \
                    or (package_name == 'org.jruby:jruby' and repo_url == 'https://github.com/jruby/jruby') \
                    or (package_name=='org.apache.maven.shared:maven-shared-utils' and repo_url == 'https://github.com/apache/maven-shared-utils') \
                    or (package_name == 'com.github.noraui:noraui' and repo_url == 'https://github.com/NoraUi/NoraUi') \
                    or (package_name == 'com.zeroc:icegrid' and repo_url == 'https://github.com/zeroc-ice/ice') \
                    or (package_name.endswith('tinymce') and repo_url=='https://github.com/tinymce/tinymce') \
                    or (package_name == 'org.webjars.bower:jquery' and repo_url=='https://github.com/jquery/jquery'):
                    sql.execute('update package set repository_url=%s where id=%s',(repo_url,package_id))
                    return repo_url
                if current_value.endswith(package_name) or current_value.endswith(package_name.split('/')[-1]):
                    #fairly reliable heuristic
                    return current_value
                if ecosystem=='Maven' and current_value.endswith(package_name.split(':')[-1]):
                    return current_value
                if ecosystem=='Composer' and repo_url.endswith(package_name):
                    sql.execute('update package set repository_url=%s where id=%s',(repo_url,package_id))
                    sql.execute('insert into repository_inferred values(%s)',(package_id,))
                    return repo_url
                #check redirection
                if requests.get(current_value).url == repo_url:
                    sql.execute('update package set repository_url=%s where id=%s',(repo_url,package_id))
                    return repo_url
                if requests.get(repo_url).url == current_value:
                    return current_value
                if current_value.lower() == repo_url.lower():
                    return current_value
                #check possible fork
                if current_value.split('/')[-1] == repo_url.split('/')[-1]:
                    return current_value
                #check gitbox repo
                s='https://gitbox.apache.org/repos/asf?p='
                if current_value.startswith(s):
                    current_value = current_value[len(s):]
                    assert current_value.count('.git') == 1
                    current_value = current_value[:current_value.find('.git')]
                    if repo_url.split('/')[-1] == current_value:
                        sql.execute('update package set repository_url=%s where id=%s',(repo_url,package_id))
                        package_name.endswith('tinymce') and repo_url=='https://github.com/tinymce/tinymce'
                        return repo_url
                #check git-wip-us repo
                s='https://git-wip-us.apache.org/repos/asf?p='
                if current_value.startswith(s):
                    current_value = current_value[len(s):]
                    assert current_value.count('.git') == 1
                    current_value = current_value[:current_value.find('.git')]
                    if repo_url.split('/')[-1] == current_value:
                        sql.execute('update package set repository_url=%s where id=%s',(repo_url,package_id))
                        package_name.endswith('tinymce') and repo_url=='https://github.com/tinymce/tinymce'
                        return repo_url
                if current_value == 'http://java.net/projects/mojarra/sources':
                    if repo_url == 'https://github.com/eclipse-ee4j/mojarra':
                        sql.execute('update package set repository_url=%s where id=%s',(repo_url,package_id))
                        package_name.endswith('tinymce') and repo_url=='https://github.com/tinymce/tinymce'
                        return repo_url
                if package_name.lower().endswith('datatables') and current_value.lower().endswith('datatables'):
                    return current_value
                if current_value.startswith(repo_url):
                    s='/tree/master'
                    if current_value.endswith(s) and current_value[:current_value.find(s)]==repo_url:
                        sql.execute('update package set repository_url=%s where id=%s',(repo_url,package_id))
                        return repo_url

                    parts = current_value.split('/')
                    if package_name.split('/')[-1] in parts[-1]:
                        return current_value
                    if 'node' in parts[-1]:
                        return current_value
                    
                    if parts[-2] == 'tree' and parts[-1].startswith('v'):
                        sql.execute('update package set repository_url=%s where id=%s',(repo_url,package_id))
                        return repo_url
    
            print(current_value, repo_url)
            assert current_value == repo_url

        return repo_url

def get_fix_commits():
    q='''select distinct a.id, a.package_id, p.name, p.repository_url
        from advisory a
        join fixing_releases fr on a.id = fr.advisory_id
        join package p on a.package_id = p.id
        where ecosystem != 'cocoapods' '''
    results = sql.execute(q)

    for item in results:
        advisory_id, package_id, package, repo_url = item['id'], item['package_id'], item['name'], item['repository_url']
        print(advisory_id, package_id, package, repo_url)

        q = '''select *
            from advisory_references
            where advisory_id = %s'''
        results = sql.execute(q,(advisory_id))
        
        commits = []
        for item in results:
            # fix commit may has commits from other repositories, when we check validity of the git commit, 
            # we will find that the url it comes from is different than the repository url
            if 'commit' in item['name'].lower() or 'commit' in item['url'].lower():
                shas = parse_sha_from_commit_reference(item['url'])
                if shas:
                    if manualcheckup in shas:
                        print(item['url'])
                        logging.info(sha)
                        exit()
                    for sha in shas:
                        commits.append((item['url'],sha))
                    repo_url = process_repo(package_id, item['url'])
                        
            if 'pull' in item['name'].lower() or 'PR' in item['name'] or '/pull/' in item['url'].lower():
                shas = parse_sha_from_github_PR_reference(item['url'])
                if shas:
                    if manualcheckup in shas:
                        print(item['url'])
                        logging.info(sha)
                        exit()
                    for sha in shas:
                        commits.append((item['url'],sha))
                    repo_url = process_repo(package_id, item['url'])
                
            if 'compare' in item['url']:
                shas = parse_sha_from_github_compares(item['url'])
                if shas:
                    if manualcheckup in shas:
                        print(item['url'])
                        logging.info(sha)
                        exit()
                    for sha in shas:
                        commits.append((item['url'],sha))
                    repo_url = process_repo(package_id, item['url'])
               
        for (item['url'],sha) in commits:
            try:
                sql.execute('insert into fix_commits values(%s,%s,%s,null,null)',(advisory_id, package_id, sha))
                sql.execute('insert into processed_reference_url values(%s,%s,%s)',(advisory_id,item['url'],sha))
            except sql.pymysql.IntegrityError as error:
                if error.args[0] == sql.PYMYSQL_DUPLICATE_ERROR:
                    pass
                    #safely continue
                else:
                    print(error)
                    exit()

    custom_fix_commits()
    logging.info('FIX COMMIT PROCESSING DONE')

def clean_Repo():
    q = '''select * from package
    where repository_url not like %s
    and repository_url not like 'no repository listed'
    and repository_url != 'not git';'''
    results = sql.execute(q,('http%',))

    for item in results:
        url, id = item['repository_url'], item['id']
        s = 'github.com'
        assert s in url
        url = url[url.find(s):]
        if url.endswith('.git'):
            url = url[:-len('.git')]
        url = 'https://' + url
        sql.execute('update package set repository_url = %s where id = %s',(url,id))

def custom_fix_commits():
    custom_queries = [
                "insert into fix_commits values('SNYK-JS-APOLLOGATEWAY-174915', 1852,'8f7ffe43b05ab8200f805697c6005e4e0bca080a', null,null )",
                "insert into fix_commits values('SNYK-PHP-LIGHTSAMLLIGHTSAML-72139', 2335,'47cef07bb09779df15620799f3763d1b8d32307a',null, null)",
                "insert into fix_commits values('SNYK-PHP-TYPO3CMS-73594', 272,'f6e0f545401a1b039a54605dba2d7afa5a6477e2', null,null )"
            ]
    print('inserting custom fix commmits: ', len(custom_queries))
    for q in custom_queries:
        try:
            sql.execute(q)
        except sql.pymysql.IntegrityError as error:
                if error.args[0] == sql.PYMYSQL_DUPLICATE_ERROR:
                    pass
                    #safely continue
                else:
                    print(error)
                    exit()

def semver_sorting(l):
    for i in range(0,len(l)):
        for j in range(i+1,len(l)):
            if semantic_version.Version(l[i]) > semantic_version.Version(l[j]):
                l[i], l [j] = l[j], l[i]
    return l

def get_release_note_info():
    q = '''select distinct package_id, repository_url, version
        from advisory a
        join package p on a.package_id = p.id
        join fixing_releases fr on a.id = fr.advisory_id
        where type != 'Malicious Package'
        and version != 'manual checkup needed'
        and ecosystem != 'cocoapods'
        and repository_url != 'no repository listed'
        and repository_url like %s 
        and concat(package_id,version) not in
        (select concat(package_id,version) from release_note);'''
    results = sql.execute(q,('https://github.com%',))
    
    for item in results:
        package_id, repo_url, version = item['package_id'], item['repository_url'], item['version']
        repo_url = ga.sanitize_repo_url(repo_url)
        owner, name = repo_url.split('/')[-2:]
        print(owner,name, version)
        node = githubapi.get_release_note(owner,name, version)
        if node:
            sql.execute('insert into release_note values(%s,%s,%s,%s,%s,%s,%s)',(package_id,version, node['name'],node['url'],
                            dt.parse(node['publishedAt']), node['tagName'], node['tagCommit']['oid']))
        else:
            sql.execute('insert into release_note values(%s,%s,%s,%s,%s,%s,%s)',(package_id,version,None,'not found through script',None,None,None))


if __name__=='__main__':
    #analyze_change_complexity()
    #get_fix_commits()
    get_release_note_info()

