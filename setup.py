""" Setup for python-panasonic-comfort-cloud """

from setuptools import setup

with open("README.md", "r") as fh:
    long_description = fh.read()

setup(
    name='pcomfortcloud',
    version='0.0.14',
    description='Read and change status of Panasonic Comfort Cloud devices',
    long_description=long_description,
    long_description_content_type="text/markdown",
    url='http://github.com/lostfields/python-panasonic-comfort-cloud',
    author='Lostfields',
    license='MIT',
    classifiers=[
       'Topic :: Home Automation',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
    ],
    keywords='home automation panasonic climate',
    install_requires=['requests>=2.20.0'],
    packages=['pcomfortcloud'],
    package_data={'': ['certificatechain.pem']},
    zip_safe=False,
    entry_points={
        'console_scripts': [
            'pcomfortcloud=pcomfortcloud.__main__:main',
        ]
    })
