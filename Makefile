# Makefile for Binance Trading Bot

.PHONY: help install test lint format clean run-backtest run-testnet run-live docker-build docker-run

help:
	@echo "Available commands:"
	@echo "  make install       - Install dependencies"
	@echo "  make test          - Run tests"
	@echo "  make lint          - Run linter"
	@echo "  make format        - Format code"
	@echo "  make clean         - Clean temporary files"
	@echo "  make run-backtest  - Run backtest mode"
	@echo "  make run-testnet   - Run testnet mode"
	@echo "  make run-live      - Run live mode"
	@echo "  make docker-build  - Build Docker image"
	@echo "  make docker-run    - Run Docker container"

install:
	pip install -r requirements.txt
	pip install -e .

test:
	pytest tests/ -v --cov=core --cov-report=html

lint:
	flake8 core/ tests/ --max-line-length=100 --ignore=E203,W503
	mypy core/ --ignore-missing-imports

format:
	black core/ tests/ --line-length=100

clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	rm -rf build/ dist/ .pytest_cache/ .mypy_cache/ htmlcov/

run-backtest:
	@echo "1" | python bot_main.py

run-testnet:
	@echo "2" | python bot_main.py

run-live:
	@echo "3" | python bot_main.py

docker-build:
	docker build -t binance-trading-bot:latest .

docker-run:
	docker-compose up -d

docker-logs:
	docker-compose logs -f trading-bot

docker-stop:
	docker-compose down