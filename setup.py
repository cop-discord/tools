from setuptools import setup, find_packages
with open("requirements.txt",'r') as file:
    requirements = file.readlines()

packages = ['tools']
readme = open('README.md', 'r').read()

setup(
    name='tools',
    version='0.0.1',
    packages=find_packages(),
    author='Cop',
    author_email='cop@catgir.ls',
    description='A collection of useful tools',
    requirements=requirements,
    install_requires = requirements,
    long_description=readme,
    long_description_content_type='text/x-rst',
    url='https://github.com/cop-discord/tools',
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
    ],
)