"""
Setup configuration for sandbox_runner (Module 3)
"""

from setuptools import setup, find_packages

setup(
    name="sandbox_runner",
    version="1.0.3",
    description="Module 3: Deterministic sandbox command runner (polished)",
    author="AIEL-0 Factory",
    python_requires=">=3.11",
    packages=find_packages(),
    package_data={
        "sandbox_runner": ["py.typed"],
    },
    install_requires=[
        # No runtime dependencies (stdlib only)
    ],
    extras_require={
        "dev": [
            "pytest>=7.4.0",
            "pytest-timeout>=2.1.0",
            "ruff>=0.1.0",
            "mypy>=1.5.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "sandbox-runner=sandbox_runner.__main__:main",
        ],
    },
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Software Development :: Quality Assurance",
    ],
)
