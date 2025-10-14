#!/usr/bin/env python3
"""
Setup script for System Optimizer Pro
"""

from setuptools import setup, find_packages
from pathlib import Path

# Read the README file
readme_file = Path(__file__).parent / "README.md"
long_description = readme_file.read_text() if readme_file.exists() else ""

setup(
    name="system-optimizer-pro",
    version="1.0.0",
    description="Advanced system optimization and automation framework with plugin architecture",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="System Optimizer Pro Team",
    author_email="info@system-optimizer-pro.dev",
    url="https://github.com/your-username/system-optimizer-pro",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    python_requires=">=3.8",
    install_requires=[
        "croniter>=2.0.0",
        "pyyaml>=6.0",
        "requests>=2.31.0",
        "psutil>=5.9.0",
        "flask>=3.0.0",
        "fastapi>=0.100.0",
        "uvicorn>=0.23.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "pytest-cov>=4.0.0",
            "black>=23.0.0",
            "flake8>=6.0.0",
            "mypy>=1.0.0",
        ],
        "web": [
            "jinja2>=3.1.0",
            "werkzeug>=3.0.0",
        ],
        "monitoring": [
            "prometheus-client>=0.17.0",
            "grafana-api>=1.0.0",
        ]
    },
    entry_points={
        "console_scripts": [
            "system-optimizer=main:main",
            "sop=main:main",
        ],
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Environment :: Console",
        "Environment :: Web Environment",
        "Intended Audience :: System Administrators",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: POSIX :: Linux",
        "Operating System :: MacOS",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: System :: Systems Administration",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: System :: Monitoring",
    ],
    keywords="system optimization automation plugins monitoring scheduling backup",
    project_urls={
        "Bug Reports": "https://github.com/your-username/system-optimizer-pro/issues",
        "Source": "https://github.com/your-username/system-optimizer-pro",
        "Documentation": "https://system-optimizer-pro.readthedocs.io/",
    },
    include_package_data=True,
    zip_safe=False,
)