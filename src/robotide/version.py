# Automatically generated by 'package.py' script.

VERSION = '0.39'
RELEASE = 'final'
TIMESTAMP = '20110927-091910'

def get_version(sep=' '):
    if RELEASE == 'final':
        return VERSION
    return VERSION + sep + RELEASE
