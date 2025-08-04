@echo off
echo Testing Enhanced Validation Routing...
echo =====================================

REM Activate virtual environment
call venv\Scripts\activate.bat

REM Create outputs directory if it doesn't exist
if not exist outputs mkdir outputs

REM Run the test script
python.exe test_enhanced_routing.py

echo.
echo Test completed. Check outputs/enhanced_routing_test_results.json for detailed results.
pause