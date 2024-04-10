from pathlib import Path
from setuptools import find_packages, setup

setup(
    name='funktools',
    version='0.14.3',
    packages=find_packages(),
    python_requires='>=3.10',
    url='https://github.com/cevans87/funktools',
    license='mit',
    author='cevans',
    author_email='c.d.evans87@gmail.com',
    description='Python 3.10+ async/sync memoize and rate decorators',
    extras_require={
        'base': (base := ['pydantic']),
        'sql_cache': (sql_cache := base + ['sqlalchemy']),
        'sqlite_cache': (sqlite_cache := sql_cache + ['aiosqlite']),
        'requirements': (requirements := base + sql_cache + sqlite_cache),
        'test': (test := requirements + ['pytest', 'pytest-asyncio', 'pytest-cov']),
    },
    install_requires=base,
)
