import pathlib
from setuptools import setup


setup(
    name="joppy",
    version="0.1.0",
    packages=["joppy"],
    description="Python API for Joplin",
    long_description=(pathlib.Path(__file__).parent / "README.md").read_text(),
    long_description_content_type="text/markdown",
    url="https://github.com/marph91/joppy",
    author="Martin Dörfelt",
    author_email="martin.d@andix.de",
    license="Mozilla Public License version 2.0",
    classifiers=[
        "License :: OSI Approved :: Mozilla Public License 2.0 (MPL 2.0)",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
    ],
    python_requires=">=3.6",
    install_requires=["requests"],
)
