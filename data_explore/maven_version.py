#CREDIT: https://github.com/suru33/maven-version-comparator/blob/main/maven_version.py
#only the qualifiers have been modified in this field

import operator
import re
import sys
from functools import reduce


def error(s):
    print(s, file=sys.stderr)
    exit(1)


def split_alphanum(s):
    rv = []
    split = re.split(r'(\d+|\D+)', s)
    for i in split:
        i = i.strip()
        if i:
            if i.isnumeric():
                rv.append(int(i))
            else:
                rv.append(i)
    return rv


def get_or_else(li, idx, default=None):
    try:
        return li[idx]
    except IndexError:
        return default


class MavenVersion:
    all_qualifiers = (
        ['alpha', 'a'],
        ['beta', 'b'],
        #nextm comes from next-m as in next milestone
        ['milestone', 'm','nextm'], 
        #pr comes from prerelease,
        ['pr','preview','criteriapreview','pre'],
        ['rc', 'cr', 'criterirarc'],
        ['snapshot'],
        #release equates to final
        ['', 'ga', 'final', 'release'],
        ['sp'],
        ['v', 'sec', 'incubating','incubatingm', 'dtexperimental','sr','hadoop']
    )

    def __init__(self, version):
        if not version:
            error(f'Version is empty')

        self._v = self.version = version.strip().lower()
        self.create_version()
        self.transform()

    def __str__(self):
        return f'{self.__class__.__name__}({self._v}, {self.version})'

    def __repr__(self):
        return self.__str__()

    def __eq__(self, other):
        return self.version == other.version

    def __gt__(self, other):
        return self.version > other.version

    def __lt__(self, other):
        return self.version < other.version

    def create_version(self):
        split = reduce(operator.concat, [i.split('.') for i in self._v.split('-')])
        rv = []
        for i in split:
            if i.isnumeric():
                rv.append(int(i))
            elif i.isalnum():
                rv.extend(split_alphanum(i))
            else:
                error(f'Invalid version name: {self._v}')

        self.version = rv

    def transform(self):
        i = 0
        major_version = get_or_else(self.version, i)
        if major_version is not None and type(major_version) is int:
            i += 1
        else:
            major_version = 0

        minor_version = get_or_else(self.version, i)
        if minor_version is not None and type(minor_version) is int:
            i += 1
        else:
            minor_version = 0

        patch_version = get_or_else(self.version, i)
        if patch_version is not None and type(patch_version) is int:
            i += 1
        else:
            patch_version = 0

        qualifier = self.version[i:]
        if qualifier:
            qualifier = split_alphanum(''.join(map(lambda x: str(x), qualifier)))
            i = 0
            qualifier_prefix = get_or_else(qualifier, i)
            if qualifier_prefix is not None and type(qualifier_prefix) is int:
                i += 1
            else:
                qualifier_prefix = 0
            qualifier_type = get_or_else(qualifier, i)
            if qualifier_type is not None and type(qualifier_type) is str:
                i += 1
                for ix, qualifiers in enumerate(self.all_qualifiers):
                    if qualifier_type in qualifiers:
                        qualifier_type = ix
                        break
            else:
                qualifier_type = 5
            if type(qualifier_type) is not int:
                error(f'Invalid qualifier found in: {self._v}')
            qualifier_suffix = get_or_else(qualifier, i)
            if qualifier_suffix is not None and type(qualifier_suffix) is int:
                i += 1
            else:
                qualifier_suffix = 0

            if i != len(qualifier):
                error(f'Invalid qualifier found in: {self._v}')
            qualifier = [qualifier_prefix, qualifier_type, qualifier_suffix]
        else:
            # 6 = ['', 'ga', 'final']
            qualifier = [0, 6, 0]

        self.version = major_version, minor_version, patch_version, *qualifier

if __name__ == '__main__':
    v='2.0.5'
    print(v)
    v1 = MavenVersion(v)
    print(v1)