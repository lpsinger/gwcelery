import sys

import versioneer
import pkg_resources
from setuptools import setup


def get_requirements(filename):
    with open(filename, 'r') as f:
        return [str(r) for r in pkg_resources.parse_requirements(f)]


setup_requires = ['setuptools >= 30.3.0']
if {'pytest', 'test', 'ptr'}.intersection(sys.argv):
    setup_requires.extend(get_requirements('test-requirements.txt'))
if {'build_sphinx'}.intersection(sys.argv):
    setup_requires.extend(get_requirements('docs-requirements.txt'))

setup(install_requires=get_requirements('requirements.txt'),
      setup_requires=setup_requires,
      version=versioneer.get_version(),
      cmdclass=versioneer.get_cmdclass())
