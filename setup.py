from setuptools import setup, find_packages

setup(
    name="chameleon",
    version="1.0.0",
    packages=find_packages(),
    py_modules=["chameleon"],
    install_requires=[
        "Pillow",
        "pillow-heif"
    ],
    entry_points={
        "console_scripts": [
            "chameleon=chameleon:main",
        ]
    },
)
