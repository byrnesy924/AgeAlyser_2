from setuptools import find_packages, setup

with open("README.md", "r") as f:
    long_description = f.read()

setup(
    name="age_alyser",
    version="0.0.1",
    description="A python package for extracting key features of an AOE2 recorded games",
    package_dir={"": "age-alyser"},
    packages=find_packages(where="age-alyser"),
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/byrnesy924/AgeAlyser_2",
    author="Benjamin Byrnes",
    author_email="b.byrnesy@gmail.com",
    license="MIT",
    classifiers=[
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3.11",
        "Operating System :: OS Independent",
    ],
    install_requires=["mgz>=1.8.26", "pandas>=2.2.2", "numpy>=2.0.0", "scipy>=1.14.0", "shapely>=2.0.5"],
    extras_require={
        "dev": ["pytest>=7.0", "twine>=4.0.2"],
    },
    python_requires=">=3.11",
)