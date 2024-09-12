#!/usr/bin/env python

"""The setup script."""

from setuptools import setup, find_packages

with open("README.md") as readme_file:
    readme = readme_file.read()

requirements = []

test_requirements = []

setup(
    author="Akram Zaytar",
    author_email="akramzaytar@microsoft.com",
    python_requires=">=3.6",
    classifiers=[
        "Development Status :: 2 - Pre-Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Natural Language :: English",
        "Programming Language :: Python :: 3"
    ],
    description="An Earth Engine app that finds similar regions wrt a reference region given some spatiotemporal variables.",
    entry_points={
        "console_scripts": [
            "region_similarity=region_similarity.scripts.app:main",
        ],
    },
    install_requires=requirements,
    license="MIT license",
    long_description=readme,
    include_package_data=True,
    keywords="region_similarity",
    name="region_similarity",
    packages=find_packages(include=["region_similarity", "region_similarity.*"]),
    url="https://github.com/microsoft/region_similarity",
    version="0.1.0",
    zip_safe=False,
)
