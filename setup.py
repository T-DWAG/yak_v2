#!/usr/bin/env python3
"""
Setup script for Yak Similarity Analyzer
"""

from setuptools import setup, find_packages
import os

# Read the README file
def read_readme():
    if os.path.exists('README.md'):
        with open('README.md', 'r', encoding='utf-8') as f:
            return f.read()
    return ''

# Read requirements
def read_requirements():
    if os.path.exists('requirements.txt'):
        with open('requirements.txt', 'r', encoding='utf-8') as f:
            return [line.strip() for line in f if line.strip() and not line.startswith('#')]
    return []

setup(
    name='yak-similarity-analyzer',
    version='2.0.0',
    description='AI-powered yak image similarity analyzer with enterprise security features',
    long_description=read_readme(),
    long_description_content_type='text/markdown',
    author='Claude Code AI',
    author_email='support@example.com',
    url='https://github.com/yourusername/yak-similarity-analyzer',
    
    packages=find_packages('src'),
    package_dir={'': 'src'},
    
    install_requires=read_requirements(),
    
    extras_require={
        'dev': [
            'pytest>=7.0.0',
            'pytest-cov>=4.0.0',
            'flake8>=5.0.0',
            'black>=22.0.0',
        ],
        'gpu': [
            'torch>=2.0.0',
            'torchvision>=0.15.0',
        ]
    },
    
    python_requires='>=3.9',
    
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Intended Audience :: Science/Research',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
        'Topic :: Scientific/Engineering :: Artificial Intelligence',
        'Topic :: Scientific/Engineering :: Image Recognition',
        'Topic :: Security',
    ],
    
    keywords='yak, image, similarity, AI, YOLO, computer vision, security, authorization',
    
    entry_points={
        'console_scripts': [
            'yak-analyzer=src.app:main',
        ],
    },
    
    include_package_data=True,
    package_data={
        '': ['*.md', '*.txt', '*.json', '*.html', '*.css', '*.js'],
    },
    
    project_urls={
        'Bug Reports': 'https://github.com/yourusername/yak-similarity-analyzer/issues',
        'Source': 'https://github.com/yourusername/yak-similarity-analyzer',
        'Documentation': 'https://github.com/yourusername/yak-similarity-analyzer/blob/main/README.md',
    },
)