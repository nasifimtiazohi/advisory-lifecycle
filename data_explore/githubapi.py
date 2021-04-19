import os
import requests
import json
token = os.environ['gh_token']
headers = {'Authorization': 'token {}'.format(token)}

def rest_call(url):
    r = requests.get(url, headers=headers)
    return json.loads(r.content)

def run_query(query, variables): 
    request = requests.post('https://api.github.com/graphql', 
    json={'query': query, 'variables':variables}, headers=headers)
    if request.status_code == 200:
        return request.json()['data']
    else:
        raise Exception("Query failed to run by returning code of {}. {}".format(
                request.status_code, variables))


def get_release_note(owner, name, version):
    query = '''query ($repo_owner: String!, $repo_name: String!, $after: String){ 
                    repository(owner: $repo_owner , name: $repo_name){
                        releases(first:100, after: $after){
                            totalCount
                            nodes{
                                id
                                name
                                publishedAt
                                url
                                tagCommit{
                                    oid
                                }
                                tagName
                            }
                            pageInfo{
                                hasNextPage
                                endCursor
                            }
                        }
                    }
                }'''
    variables = {
            "repo_owner": owner,
            "repo_name": name,
            "after": None
            }
    
    totalCount=None
    releases = []
    while True:
        data=  run_query(query, variables)

        if not data or 'repository' not in data:
            return None
        data = data['repository']
        if not data or 'releases' not in data or not data['releases']:
            return None
        data= data['releases']
        
        totalCount=data['totalCount']
        #print(totalCount)
        releases.extend(data['nodes'])
        
        for node in data['nodes']:
            #print(node['name'], node['tagName'])
            if (node['name'] and node['name'].strip().endswith(version)) or (node['tagName'] and node['tagName'].strip().endswith(version)):
                return node

        if data['pageInfo']['hasNextPage']:
            variables["after"]=data['pageInfo']['endCursor']
        else:
            break

    if len(releases)==totalCount:
        return None
    else:
        raise Exception('graphql call not functioning properly')

if __name__=='__main__':
    print(get_release_note('swagger-api','swagger-ui','3.0.14'))