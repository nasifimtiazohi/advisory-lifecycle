from version_differ.version_differ import *
import common, sql 
from multiprocessing import Pool

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
            and ri.id not in (select release_id from version_diff)
            order by rand()'''
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
        if eco != 'Go':
            files = get_version_diff_stats(eco, package, old_version, new_version)
        else:
            files = go_get_version_diff_stats(package, repo_url, old_version, new_version)
        for file in files.keys():
            q = '''insert into version_diff values(%s,%s,%s,%s)'''
            sql.execute(q, (release_id, file, files[file]['loc_added'], files[file]['loc_removed'])
                    , connection= conn)
        

    except:
        pass

def process_version_diff():
    results = get_release_data()
    pool  = Pool(os.cpu_count())
    pool.map(pvd_mp, results) 

    


if __name__ == '__main__':
    process_version_diff()