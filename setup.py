import sys

# Bootstrap setuptools installation.
try:
    import pkg_resources
    pkg_resources.require("setuptools >= 0.7")
except:
    from ez_setup import use_setuptools
    use_setuptools()

from setuptools import setup, find_packages

tests_require = ['pytest']
try:
    from unittest import mock
except ImportError:
    tests_require += ['mock']

needs_pytest = {'pytest', 'test', 'ptr'}.intersection(sys.argv)

setup(
    name='gwcelery',
    version='0.0.1',
    author='Leo Singer',
    author_email='leo.singer@ligo.org',
    description='Hipster pipeline for annotating LIGO events',
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Environment :: Console',
        'Intended Audience :: Science/Research',
        'License :: OSI Approved :: GNU General Public License v2 or later (GPLv2+)',
        'Operating System :: POSIX',
        'Programming Language :: Python :: 2.7',
        'Topic :: Internet',
        'Topic :: Scientific/Engineering :: Astronomy'
    ],
    license='GPL-2+',
    install_requires=[
        'astropy',
        'celery[redis]',
        'celery_singleton >= 0.1.1',
        'ligo-gracedb',
        'ligo-lvalert',
        'pyxmpp'
    ],
    packages=find_packages(),
    package_data={
        '': ['*.html', '*.json']
    },
    entry_points={
        'console_scripts': [
            'gwcelery = gwcelery:start'
        ]
    },
    setup_requires=['pytest-runner'] if needs_pytest else [],
    tests_require=tests_require
)
