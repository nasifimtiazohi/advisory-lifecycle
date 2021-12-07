from version_differ.version_differ import *
import common, sql 
from multiprocessing import Pool
from bs4 import BeautifulSoup as BS
import os, time
#libraryio_token = os.environ['libraryio_token']

temp = 'select * from file_extensions'
temp = sql.execute(temp)
source_file = {}
for item in temp:
    if item['source'] == 1:
        source_file[item['format']] = True
    else:
        source_file[item['format']] = False

def get_release_data():
    q = '''select advisory_id, p.ecosystem as ecosystem, p.id as package_id,
    p.name as package, p.repository_url as repo_url,
    repository_url, ri.id as release_id, 
    ri.version as fixing_release, prior_release
            from advisory a
            join package p on a.package_id = p.id
            join fixing_releases fr on a.id = fr.advisory_id
            join release_info ri on p.id = ri.package_id and ri.version = fr.version
            where ri.prior_release != %s
            and ri.prior_release != 'branch does not match'
            and ri.prior_release != 'not valid semver formatting'
            and repository_url != %s
            and ri.id not in (select distinct release_id from version_diff)
            and ri.id not in (select distinct release_id from version_diff_with_no_head_commit)
            and ri.id not in (select distinct release_id from version_diff_with_no_package_file)
            and p.ecosystem = 'pip'
            order by rand()
            '''
    results = sql.execute(q,(common.manualcheckup,common.norepo))
    return results

def custom_fixing(package, version):
    if package == 'bundler' and version == '2.0':
        version = '2.0.0'
    if package == 'rubocop' and version == '0.49':
        version = '0.49.0'
    
    return package, version

def pvd_mp(item):
    '''multi-processing function for process_version_diff'''

    conn = sql.create_db_connection()

    release_id, eco, package, repo_url, new_version, old_version = item['release_id'], item['ecosystem'], item['package'], item['repo_url'], item['fixing_release'], item['prior_release']
    print(release_id, eco, package, new_version, old_version)

    #some custom fixing
    custom_fixing(package, new_version)
    custom_fixing(package, old_version)
    

    try:
        diff_stats = get_version_diff_stats(eco, package, old_version, new_version)
        files = diff_stats['diff']
        #TODO: need to filter out files with zero loc change (file renamed) as logic got updated in the latest version-differ
        if files is None:
            q = 'insert into version_diff_with_no_head_commit values (%s)'
            args = [release_id]
        elif files:
            q =  'insert into version_diff values'
            args = []
            for file in files.keys():
                q += ''' (%s,%s,%s,%s), '''
                args.extend([release_id, file, files[file]['loc_added'], files[file]['loc_removed']])    
            q = q[:-2] #remove trailing comma
        else:
            assert len(files) == 0
            q = 'insert into version_diff_with_no_package_file values (%s)'
            args = [release_id]

        sql.execute(q, tuple(args), connection= conn)
    except:
        pass

    

def process_version_diff():
    results = get_release_data()
    print(len(results))
    pool  = Pool(os.cpu_count())
    pool.map(pvd_mp, results) 



    


def file_is_a_source_file(file):
    if '.' not in file:
        return False
    
    ext = file.split('.')[-1]
    if ext not in source_file:
        return False
    else:
        return source_file[ext]

    
rq3 = {}

def process_rq3():
    q = '''select distinct release_id from version_diff where release_id not in (select release_id from rq3)'''
    rids = sql.execute(q)
    for rid in rids:
        rid = rid['release_id']

        q = 'select * from version_diff where release_id = %s'
        results = sql.execute(q,(rid,))

        files_changed = 0 
        loc_changed = 0
        for item in results:
            rid, file, loc_added, loc_removed = item['release_id'], item['filepath'], item['loc_added'], item['loc_removed']
            if file_is_a_source_file(file):
                files_changed+=1
                loc_changed += (loc_added + loc_removed)

        
    
        q = 'insert into rq3 values (%s,%s,%s)'
        sql.execute(q,(rid, files_changed, loc_changed))

def parse_release_type(release):
    ''' TODO: parse unknown-patch from common.fix_release_type'''
    if '-' in release or release.count('.') > 2:
        return 'prerelease'

    parts = release.split('.')
    
    try:
        t = int(parts[2])
        t = int(parts[1])
        t = int(parts[0])
    except:
        return 'unknown' 

    if len(parts) == 3 and int(parts[-1]) > 0:
        return 'patch'
    
    if len(parts) > 1 and int(parts[1]) > 0:
        return 'minor'
    
    return 'major'


def release_type():
    q = '''select distinct release_id, version
        from rq3 join
        release_info ri on rq3.release_id = ri.id
        where release_id not in
        (select release_info_id from release_type);'''
    results = sql.execute(q)
    print(len(results))

    q = 'insert into release_type values(%s, %s)'
    for item in results:
        rid, version = item['release_id'], item['version']
        rt = parse_release_type(version)
        print(rid, rt)
        sql.execute(q,(rid,rt))

def fix_release_type():
    q = '''select *
            from release_type rt
            join release_info ri
            on rt.release_info_id=ri.id
            where type = 'prerelease';'''
    results = sql.execute(q)

    for item in results:
        rid, version = item['release_info_id'], item['version']
        
        suffix = ['.RELEASE', '.FINAL', '.Final']
        for s in suffix:
            if version.endswith(s):
                rt = parse_release_type(version[:-len(s)])
                q = 'update release_type set type=%s where release_info_id=%s'
                print(rid, rt)
                sql.execute(q,(rt, rid))


def get_download_count(ecosystem, package, package_id):

    package = package.replace('/','%2F')
    if ecosystem == 'Composer':
        platform = 'packagist'
    elif ecosystem == 'Go':
        platform = 'go'
    elif ecosystem == 'Maven':
        platform = 'maven'
    elif ecosystem == 'npm':
        platform = 'npm'
    elif ecosystem == 'NuGet':
        platform = 'nuget'
    elif ecosystem == 'pip':
        platform = 'pypi'
    elif ecosystem == 'RubyGems':
        platform = 'rubygems'
    
    
        
    url = "https://libraries.io/api/{}/{}?api_key={}".format(platform, package, libraryio_token)
    page = requests.get(url)
    print(package_id, page)
    if not page.status_code == 200:
        return 0
    
    data = json.loads(page.content)
    dep_repos = data['dependent_repos_count']
    rev_deps = data['dependents_count']
    stars = data['stars']
    q = 'insert into package_usage values(%s,%s,%s,%s)'
    sql.execute(q,(package_id, rev_deps, dep_repos, stars))


    
def process_package_usage():
    q = '''select *
        from package
        where id not in (select package_id from package_usage)
        and ecosystem = 'pip' '''
    results = sql.execute(q)

    counter = 0
    for item in results:
        if counter == 50:
            time.sleep(60)
            counter = 0

        id, name, ecosystem = item['id'], item['name'], item['ecosystem']
        try:
            get_download_count(ecosystem, name, id)
        except:
            pass
        counter+=1


if __name__ == '__main__':
    #process_version_diff()
    process_rq3()
    
