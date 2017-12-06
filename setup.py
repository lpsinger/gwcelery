import sys

from setuptools import setup, find_packages

tests_require = ['pytest >= 3.0']
try:
    from unittest import mock
except ImportError:
    tests_require += ['mock']

needs_pytest = {'pytest', 'test', 'ptr'}.intersection(sys.argv)

setup(
    name='GWCelery',
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
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.6',
        'Topic :: Internet',
        'Topic :: Scientific/Engineering :: Astronomy',
        'Topic :: Scientific/Engineering :: Physics'
    ],
    license='GPL-2+',
    install_requires=[
        'astropy',
        'celery[redis] >= 4.1.0',
        'celery_singleton >= 0.1.1',
        'dnspython',
        'ligo-gracedb',
        'pygcn',
        'pyxmpp2',
        'six'
    ],
    packages=find_packages(),
    package_data={
        '': ['*.html', '*.json', '*.xml', '*.xml.gz']
    },
    entry_points={
        'console_scripts': [
            'gwcelery = gwcelery:app.start'
        ]
    },
    setup_requires=['pytest-runner'] if needs_pytest else [],
    tests_require=tests_require
)
