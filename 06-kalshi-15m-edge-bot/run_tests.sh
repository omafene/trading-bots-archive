#!/bin/bash
# Test runner script

echo "========================================="
echo "Running Kalshi Bot Test Suite"
echo "========================================="
echo ""

# Install test dependencies if needed
pip3 install -q -r requirements-test.txt

# Run tests with coverage
pytest tests/ -v --cov=. --cov-report=term-missing --cov-report=html

echo ""
echo "========================================="
echo "Test Results Summary"
echo "========================================="
echo "HTML coverage report: htmlcov/index.html"
echo ""
