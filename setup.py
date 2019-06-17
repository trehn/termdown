try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup

setup(
    name="termdown",
    version="1.15.0",
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
        "Programming Language :: Python :: 2.7",
        "Programming Language :: Python :: 3",
        "Topic :: Utilities",
    ],
    install_requires=[
        "click >= 2.0",
        "pyfiglet >= 0.7",
        "python-dateutil",
    ],
    py_modules=['termdown'],
    entry_points={
        'console_scripts': [
            "termdown=termdown:main",
        ],
    },
)
