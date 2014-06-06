try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup

setup(
    name="termdown",
    version="1.1",
    description="Countdown timer for your terminal",
    author="Torsten Rehn",
    author_email="torsten@rehn.email",
    license="GPLv3",
    url="https://github.com/trehn/termdown",
    keywords=["terminal", "timer", "countdown", "curses"],
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Environment :: Console :: Curses",
        "License :: OSI Approved :: GNU General Public License v3 (GPLv3)",
        "Natural Language :: English",
        "Programming Language :: Python :: 2.7",
        "Programming Language :: Python :: 3",
        "Topic :: Utilities",
    ],
    install_requires=[
        "click",
        "pyfiglet",
        "python-dateutil",
    ],
    py_modules=['termdown'],
    entry_points={
        'console_scripts': [
            "termdown=termdown:main",
        ],
    },
)
