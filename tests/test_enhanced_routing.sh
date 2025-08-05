#!/bin/bash

echo "Testing Enhanced Validation Routing..."
echo "====================================="

# Activate virtual environment
source venv/bin/activate

# Create outputs directory if it doesn't exist
mkdir -p outputs

# Run the test script
python3 test_enhanced_routing.py

echo ""
echo "Test completed. Check outputs/enhanced_routing_test_results.json for detailed results."