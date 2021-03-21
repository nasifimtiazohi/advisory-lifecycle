# lag from commit to release
## How to look for release date?
    - npm: `npm view {package} time -- json`
    - Maven: https://mvnrepository.com/artifact/com.capitalone.dashboard/core/3.6.9
## How to look for commit date?
    - parse github information. If commit, direct commit date. If PR, commit dates and Pr merge dates 


# change complexty
## How to locate the nearest release in its own branch with which we will measure differences? This would also need to know semver formatting change.
    - for npm : `npm view {} versions` gives versions in order, just take the last one before fixing release.
## Measure unrelated changes
    - If we have fix commit. we can measure unrelated commits. (What if other commits are also vulnerability fixes?)


# Where to look for release notes?
- Repository (Probably only this is enough)
    - github release note
    - changelog.md
    - external links given in readme
- Homepage
- Package Manager


