from setuptools import setup, find_packages

setup(
    name="agent-insight-sdk",
    version="0.1.0",
    description="AI Agent 可观测性探针 SDK",
    author="Agent-Insight Team",
    packages=find_packages(),
    install_requires=[
        "httpx>=0.24.0",
    ],
    python_requires=">=3.10",
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
)
