import pathlib
from setuptools import setup


setup(
    name="joppy",
    version="0.2.1",
    packages=["joppy"],
    # https://stackoverflow.com/a/70386281/7410886
    package_data={
        "joppy": ["py.typed"],
    },
    description="Python API for Joplin",
    long_description=(pathlib.Path(__file__).parent / "README.md").read_text(),
    long_description_content_type="text/markdown",
    url="https://github.com/marph91/joppy",
    author="Martin Dörfelt",
    author_email="martin.d@andix.de",
    license="Mozilla Public License version 2.0",
    # https://pypi.org/classifiers
    classifiers=[
        "License :: OSI Approved :: Mozilla Public License 2.0 (MPL 2.0)",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Typing :: Typed",
    ],
    python_requires=">=3.7",
    install_requires=["requests"],
)
