import sys

from setuptools import setup, find_packages


setup(
    name='hyperxyzzy',
    version='1.0',
    description='A simple tool to recursively traverse HTTP URLs, reporting an in/out relationship graph of hyperlink references in json format.',
    long_description=open('README.rst').read(),
    author='Jeff Quast',
    author_email='contact@jeffquast.com',
    license='MIT',
    packages=find_packages(exclude=['ez_setup']),
    install_requires=[
        'requests >= 1.1.0',
        'beautifulsoup4 >= 4.3.1',
        ],
    tests_require=['nose'],
    test_suite='nose.collector',
    url='https://jeffquast.com/resume.pdf',
    include_package_data=True,
    classifiers=[
        'Intended Audience :: Developers',
        'Natural Language :: English',
        'Development Status :: 5 - Production/Stable',
        'Environment :: Console',
        'License :: OSI Approved :: MIT License',
        'Operating System :: POSIX',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.2',
        'Programming Language :: Python :: 3.3',
        'Topic :: Software Development :: User Interfaces',
        ],
    keywords=['http', 'hyperlink', 'json', 'reporting'],
)
