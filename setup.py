from pathlib import Path
from setuptools import find_packages, setup

setup(
    name='functools',
    version='0.14.2',
    packages=find_packages(),
    python_requires='>=3.12',
    url='https://github.com/cevans87/funktools',
    license='mit',
    author='cevans',
    author_email='c.d.evans87@gmail.com',
    description='Python 3.10+ decorator library',
    extras_require={
        'base': (base := [
            *filter(None, (Path(__file__).parent / 'pip_requirements.txt').read_text().splitlines())
        ]),
        'test': (test := base + [
            *filter(None, (Path(__file__).parent / 'test' / 'pip_requirements.txt').read_text().splitlines())
        ]),
    },
    install_requires=base,
)
