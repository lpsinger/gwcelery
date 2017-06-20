# Bootstrap setuptools installation.
try:
    import pkg_resources
    pkg_resources.require("setuptools >= 0.7")
except:
    from ez_setup import use_setuptools
    use_setuptools()

from setuptools import setup, find_packages
import gwcelery

setup(
    name='gwcelery',
    version=gwcelery.__version__,
    author='Leo Singer',
    author_email='leo.singer@ligo.org',
    description=gwcelery.__doc__.splitlines()[1],
    long_description=gwcelery.__doc__,
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Environment :: Console',
        'Intended Audience :: Science/Research',
        'License :: OSI Approved :: GNU General Public License v2 or later (GPLv2+)',
        'Operating System :: POSIX',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3.6',
        'Topic :: Internet',
        'Topic :: Scientific/Engineering :: Astronomy'
    ],
    license='GPL-2+',
    install_requires=[
        'celery[redis]',
        'celery_singleton',
        'ligo-gracedb',
        'ligo-lvalert'
    ],
    packages=find_packages(),
    package_data={
        '': ['*.ini']
    }
)
