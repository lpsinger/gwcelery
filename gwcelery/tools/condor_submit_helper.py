"""
Wrapper script to get the Redis broker URL from condor and launch another tool.

In a job running under HTCondor, the environment variable `_CONDOR_MACHINE_AD`
is the path of a text file that contains the machine's ClassAd attributes. The
`ClientMachine` attribute records the hostname of the machine that has claimed
the machine on which the job is running, i.e., the submit machine. We assume
that the Redis server is running on the submit machine.
"""
import os
import re
import sys


def get_classad_attribute(filename, attrib):
    pattern = r'^' + re.escape(attrib) + r'\s*=\s*"(.*)"\s*$'
    regex = re.compile(pattern)
    with open(filename, 'r') as f:
        for line in f:
            match = regex.match(line)
            if match is not None:
                return match.group(1)
    raise ValueError(
        f'ClassAd attribute "{attrib}" not found in file "{filename}"')


def main():
    filename = os.environ['_CONDOR_MACHINE_AD']
    hostname = get_classad_attribute(filename, 'ClientMachine')
    os.environ['CELERY_BROKER_URL'] = f'redis://{hostname}'
    os.execvp(sys.argv[1], sys.argv[1:])
