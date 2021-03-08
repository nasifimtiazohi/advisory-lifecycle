import os
import requests
import json
from datetime import datetime, timezone
from dateutil import parser as dt
import time

headers = {"Authorization": "token {}".format(os.environ['gh_token'])}

def run_query(query, variables): 
        request = requests.post('https://api.github.com/graphql', 
        json={'query': query, 'variables':variables}, headers=headers)
        if request.status_code == 200:
            return request.json()['data']
        else:
            raise Exception("Query failed to run by returning code of {}. {}".format(
                    request.status_code, query))


def fetchNextSet():
    query = '''
        # Type queries into this side of the screen, and you will 
# see intelligent typeaheads aware of the current GraphQL type schema, 
# live syntax, and validation errors highlighted within the text.

# We'll get you started with a simple query showing your username!
query ($after: String){ 
            securityAdvisories(first:100, after: $after){
    						totalCount
                nodes{
                  cvss{
                    score
                    vectorString
                  }
                  cwes (first:100){
                    edges{
                      node
                      {
                        description
                        cweId
                        name
                      }
                    }
                  }
                  ghsaId
                  identifiers{
                    type
                    value
                  }
                  notificationsPermalink
                  origin
                  permalink
                  publishedAt
                  references{
                    url
                  }
                  severity
                  summary
                  updatedAt
                  vulnerabilities(first:100){
                    edges{
                      node{
                        firstPatchedVersion{
                          identifier
                        }
                        package{
                          ecosystem
                          name
                        }
                        severity
                        updatedAt
                        vulnerableVersionRange
                      }
                    }
                  }
                  withdrawnAt
                }
                
                pageInfo{
                hasNextPage
                endCursor
                }
            }
  					rateLimit{
              cost
              nodeCount
              remaining
              resetAt
            }
            }
    '''
    variables = {
        "after" : None
    }

    totalCount = None
    advisories = []
    while True:
        data = run_query(query, variables)
        totalCount=data['securityAdvisories']['totalCount']
        advisories.extend(data['securityAdvisories']['nodes'])

        if data['securityAdvisories']['pageInfo']['hasNextPage']:
            variables["after"] = data['securityAdvisories']['pageInfo']['endCursor']
            resetAt = dt.parse(data['rateLimit']['resetAt'])
            now_utc = datetime.now(timezone.utc)
            sleep_sec = (resetAt - now_utc).seconds
            print('fetched ',len(advisories))
            # if sleep_sec > 0:
            #     time.sleep(sleep_sec)
        else:
            break
    
    if len(advisories)==totalCount:
        #print(totalCount , ' advisories has been fetched')
        return advisories
    else:
        raise Exception('graphql call not functioning properly,')

if __name__=='__main__':
    advisories = fetchNextSet()
    with open('ghsa.json','w') as file:
        json.dump(advisories,file)
