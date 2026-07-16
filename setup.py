from pathlib import Path
import re

from setuptools import find_packages, setup


ROOT = Path(__file__).parent


def read_text(name: str) -> str:
    return (ROOT / name).read_text(encoding="utf-8")


def read_version() -> str:
    init_file = read_text("CanvasCTk/__init__.py")
    match = re.search(r'^__version__ = ["\']([^"\']+)["\']', init_file, re.MULTILINE)
    if not match:
        raise RuntimeError("Unable to find CanvasCTk.__version__")
    return match.group(1)


setup(
    name="CanvasCTk",
    version=read_version(),
    description="Reusable CustomTkinter canvas UI framework.",
    long_description=read_text("README.md"),
    long_description_content_type="text/markdown",
    author="Tupi",
    license="MIT",
    python_requires=">=3.10",
    packages=find_packages(include=["CanvasCTk", "CanvasCTk.*"], exclude=["examples", "examples.*"]),
    include_package_data=True,
    package_data={"CanvasCTk": ["themes/*.json"]},
    install_requires=[
        "customtkinter>=5.2.2,<6",
        "Pillow>=10,<13",
        "imageio[ffmpeg]>=2.34,<3",
    ],
    keywords=["customtkinter", "tkinter", "canvas", "gui", "widgets"],
    classifiers=[
        "Development Status :: 4 - Beta",
        "Environment :: Win32 (MS Windows)",
        "Environment :: X11 Applications",
        "Environment :: MacOS X",
        "Intended Audience :: Developers",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Programming Language :: Python :: 3.13",
        "Programming Language :: Python :: 3.14",
        "Topic :: Software Development :: User Interfaces",
    ],
    project_urls={
        "Homepage": "https://github.com/Tupir/CanvasCTk",
        "Repository": "https://github.com/Tupir/CanvasCTk",
        "Issues": "https://github.com/Tupir/CanvasCTk/issues",
    },
)
