from setuptools import find_packages, setup

setup(
    name="termdown",
    version="2.0.0",
    description="Countdown timer for your terminal",
    author="Torsten Rehn",
    author_email="torsten@rehn.email",
    license="GPLv3",
    url="https://github.com/trehn/termdown",
    keywords=[
        "console",
        "countdown",
        "curses",
        "stopwatch",
        "terminal",
        "timer",
    ],
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Environment :: Console :: Curses",
        "License :: OSI Approved :: GNU General Public License v3 (GPLv3)",
        "Natural Language :: English",
        "Operating System :: MacOS :: MacOS X",
        "Operating System :: POSIX",
        "Operating System :: Unix",
        "Programming Language :: Python :: 3",
        "Topic :: Utilities",
    ],
    packages=find_packages(),
    install_requires=[
        "art",
        "Pillow",
        "python-dateutil",
        "windows-curses ; platform_system=='Windows'",
    ],
    entry_points={
        "console_scripts": [
            "termdown=termdown.cli:main",
        ],
    },
)
