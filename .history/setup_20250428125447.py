"""Setup file for media_manager package."""
from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

with open("requirements.txt", "r", encoding="utf-8") as fh:
    requirements = [line.strip() for line in fh if line.strip() and not line.startswith("#")]

setup(
    name="media_manager",
    version="0.1.0",
    author="Your Name",
    author_email="your.email@example.com",
    description="A Telegram-based media downloader and organizer",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/media_manager",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: End Users/Desktop",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
    python_requires=">=3.8",
    install_requires=requirements,
    entry_points={
        "console_scripts": [
            "media-manager=media_manager.main:main",
            "media-manager-downloader=media_manager.downloader.run_downloader:main",
            "media-manager-watcher=media_manager.watcher.run_watcher:main",
        ],
    },
)