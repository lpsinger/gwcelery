# Bootstrap setuptools installation.
setup_requires = ['setuptools >= 30.3.0']
try:
    import pkg_resources
    pkg_resources.require(setup_requires)
except:
    from ez_setup import use_setuptools
    use_setuptools()

import sys
from setuptools import setup
if {'pytest', 'test', 'ptr'}.intersection(sys.argv):
    setup_requires.append('pytest-runner')
if {'build_sphinx'}.intersection(sys.argv):
    setup_requires.extend(['celery_singleton', 'recommonmark', 'sphinx'])

setup(setup_requires=setup_requires)
