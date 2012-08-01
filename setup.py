"""
Flask-Snooze
--------------

Backend-agnostic REST API provider for Flask.

Links
`````

* `development version
  <http://github.com/ahri/flask-snooze>`_

"""
from setuptools import setup

setup(
    name='Flask-Snooze',
    version='0.1.4',
    url='http://github.com/ahri/flask-snooze',
    license='MIT',
    author='Adam Piper',
    author_email='adam@ahri.net',
    description='Backend agnostic REST API provider for Flask',
    long_description=__doc__,
    py_modules=['flask_snooze'],
    test_suite="nose.collector",
    zip_safe=False,
    platforms='any',
    include_package_data=True,
    install_requires=[
        'Flask>=0.8',
    ],
    tests_require=[
        'Flask-Testing>=0.3',
        'nose>=1.1.2',
        'Flask-SQLAlchemy>=0.16',
        'SQLAlchemy>=0.7.8',
    ],
    classifiers=[
        'Development Status :: 4 - Beta',
        'Environment :: Web Environment',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Topic :: Internet :: WWW/HTTP :: Dynamic Content',
        'Topic :: Software Development :: Libraries :: Python Modules'
    ]
)
