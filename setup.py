"""
Setup script for Binance Trading Bot
"""

from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

with open("requirements.txt", "r", encoding="utf-8") as fh:
    requirements = [line.strip() for line in fh if line.strip() and not line.startswith("#")]

setup(
    name="binance-trading-bot",
    version="1.0.0",
    author="Trading Bot Team",
    author_email="contact@example.com",
    description="Professional Binance trading bot with backtesting, testnet, and live trading",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/binance-trading-bot",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Financial and Insurance Industry",
        "Topic :: Office/Business :: Financial :: Investment",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.11",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.11",
    install_requires=requirements,
    entry_points={
        "console_scripts": [
            "trading-bot=bot_main:main",
        ],
    },
)