#!/usr/bin/env python3
"""
Local test script for the CSV validator using puremagic.
Tests various file types including the test_files directory and synthetic examples.
"""

import json
import base64
from pathlib import Path
from typing import Dict, Any, List
import sys

# Import the puremagic version of lambda handler
from lambda_function_puremagic import lambda_handler

class TestCase:
    def __init__(self, name: str, content: bytes, filename: str, expected_csv: bool, description: str = ""):
        self.name = name
        self.content = content
        self.filename = filename
        self.expected_csv = expected_csv
        self.description = description

def create_test_cases() -> List[TestCase]:
    """Create a comprehensive list of test cases."""
    test_cases = []
    
    # 1. Test files from test_files directory
    test_files_dir = Path("test_files")
    if test_files_dir.exists():
        # PDF file
        pdf_file = test_files_dir / "IdentificationBooklet_web.pdf"
        if pdf_file.exists():
            test_cases.append(TestCase(
                "real_pdf", 
                pdf_file.read_bytes(), 
                pdf_file.name, 
                False,
                "Real PDF document"
            ))
        
        # CSV file
        csv_file = test_files_dir / "contribution_strategy_census.csv"
        if csv_file.exists():
            test_cases.append(TestCase(
                "real_csv", 
                csv_file.read_bytes(), 
                csv_file.name, 
                True,
                "Real CSV file with census data"
            ))
        
        # JPEG file
        jpeg_file = test_files_dir / "cat.jpeg"
        if jpeg_file.exists():
            test_cases.append(TestCase(
                "real_jpeg", 
                jpeg_file.read_bytes(), 
                jpeg_file.name, 
                False,
                "Real JPEG image"
            ))
    
    # 2. Synthetic CSV test cases
    test_cases.extend([
        TestCase(
            "simple_csv",
            "name,age,city\nJohn,30,New York\nJane,25,Los Angeles".encode(),
            "simple.csv",
            True,
            "Simple CSV with 3 columns"
        ),
        
        TestCase(
            "csv_with_quotes",
            'Product,Price,Description\n"Laptop",999.99,"High-end gaming laptop"\n"Mouse",29.99,"Wireless mouse"'.encode(),
            "products.csv",
            True,
            "CSV with quoted fields"
        ),
        
        TestCase(
            "csv_many_columns",
            "id,name,email,phone,address,city,state,zip,country,notes\n1,John Doe,john@example.com,555-1234,123 Main St,Anytown,CA,12345,USA,Test user\n2,Jane Smith,jane@example.com,555-5678,456 Oak Ave,Somewhere,NY,67890,USA,Another user".encode(),
            "users.csv",
            True,
            "CSV with many columns"
        ),
        
        TestCase(
            "csv_no_extension",
            "header1,header2,header3\nvalue1,value2,value3\nval4,val5,val6".encode(),
            "data.txt",
            True,
            "CSV content but .txt extension"
        ),
    ])
    
    # 3. Non-CSV test cases
    test_cases.extend([
        TestCase(
            "plain_text",
            "This is just a plain text file.\nIt has multiple lines.\nSome lines have commas, but not in a structured way.\nThis is more like a document.".encode(),
            "document.txt",
            False,
            "Plain text with occasional commas"
        ),
        
        TestCase(
            "json_file",
            '{"name": "John", "age": 30, "city": "New York", "hobbies": ["reading", "swimming"]}'.encode(),
            "data.json",
            False,
            "JSON file"
        ),
        
        TestCase(
            "html_file",
            "<html><head><title>Test</title></head><body><h1>Hello, World!</h1><p>This is a test page.</p></body></html>".encode(),
            "page.html",
            False,
            "HTML file"
        ),
        
        TestCase(
            "xml_file",
            '<?xml version="1.0"?><root><item name="test" value="123"/><item name="another" value="456"/></root>'.encode(),
            "data.xml",
            False,
            "XML file"
        ),
        
        TestCase(
            "inconsistent_commas",
            "name,age\nJohn,30\nJane\nBob,25,extra".encode(),
            "bad.csv",
            False,
            "Inconsistent comma structure"
        ),
    ])
    
    # 4. Edge cases
    test_cases.extend([
        TestCase(
            "single_line_csv",
            "name,age,city".encode(),
            "header_only.csv",
            False,
            "CSV with only header row"
        ),
        
        TestCase(
            "empty_file",
            b"",
            "empty.csv",
            False,
            "Empty file"
        ),
        
        TestCase(
            "single_column_csv",
            "names\nJohn\nJane\nBob".encode(),
            "single_col.csv",
            False,
            "Single column (no commas)"
        ),
        
        TestCase(
            "csv_with_empty_lines",
            "name,age,city\nJohn,30,NYC\n\nJane,25,LA\n\nBob,35,Chicago".encode(),
            "with_blanks.csv",
            True,
            "CSV with empty lines"
        ),
    ])
    
    return test_cases

def run_test(test_case: TestCase) -> Dict[str, Any]:
    """Run a single test case locally."""
    print(f"\n🧪 Testing: {test_case.name}")
    print(f"   Description: {test_case.description}")
    print(f"   Filename: {test_case.filename}")
    print(f"   Expected CSV: {test_case.expected_csv}")
    
    # Prepare event for lambda handler
    event = {
        "file_content": base64.b64encode(test_case.content).decode(),
        "filename": test_case.filename
    }
    
    try:
        result = lambda_handler(event, None)
        
        # Parse the result (it's in lambda response format)
        if 'body' in result:
            body = json.loads(result['body']) if isinstance(result['body'], str) else result['body']
        else:
            body = result
        
        actual_csv = body.get("success", False)
        mimetype = body.get("mimetype", "unknown")
        message = body.get("message", "")
        puremagic_details = body.get("puremagic_details", {})
        
        passed = actual_csv == test_case.expected_csv
        status = "✅ PASS" if passed else "❌ FAIL"
        
        print(f"   Result: {status}")
        print(f"   MIME Type: {mimetype}")
        print(f"   Actual CSV: {actual_csv}")
        print(f"   Message: {message}")
        
        if puremagic_details:
            print(f"   PureMagic Extension: {puremagic_details.get('extension', 'N/A')}")
            print(f"   PureMagic Confidence: {puremagic_details.get('confidence', 'N/A')}")
            if puremagic_details.get('all_matches'):
                print(f"   All Matches: {len(puremagic_details['all_matches'])} found")
                for i, match in enumerate(puremagic_details['all_matches'][:3]):  # Show first 3
                    print(f"     {i+1}. {match['mime']} (conf: {match['confidence']})")
        
        return {
            "test_name": test_case.name,
            "passed": passed,
            "expected": test_case.expected_csv,
            "actual": actual_csv,
            "mimetype": mimetype,
            "message": message,
            "puremagic_details": puremagic_details
        }
        
    except Exception as e:
        print(f"   ❌ ERROR: {str(e)}")
        return {
            "test_name": test_case.name,
            "passed": False,
            "error": str(e),
            "expected": test_case.expected_csv
        }

def main():
    """Run all test cases and report results."""
    print("🚀 Running CSV Validator Tests (PureMagic Version)")
    print("=" * 60)
    
    test_cases = create_test_cases()
    results = []
    
    print(f"\nFound {len(test_cases)} test cases")
    
    for test_case in test_cases:
        result = run_test(test_case)
        results.append(result)
    
    # Summary
    print("\n" + "=" * 60)
    print("📊 TEST SUMMARY")
    print("=" * 60)
    
    passed_tests = [r for r in results if r["passed"]]
    failed_tests = [r for r in results if not r["passed"]]
    error_tests = [r for r in results if "error" in r]
    
    print(f"Total Tests: {len(results)}")
    print(f"✅ Passed: {len(passed_tests)}")
    print(f"❌ Failed: {len(failed_tests)}")
    print(f"🚨 Errors: {len(error_tests)}")
    
    if failed_tests:
        print("\n❌ FAILED TESTS:")
        for test in failed_tests:
            if "error" not in test:
                print(f"   - {test['test_name']}: expected {test['expected']}, got {test['actual']}")
    
    if error_tests:
        print("\n🚨 ERROR TESTS:")
        for test in error_tests:
            print(f"   - {test['test_name']}: {test['error']}")
    
    # Detailed breakdown by category
    print("\n📈 BREAKDOWN BY EXPECTED RESULT:")
    csv_tests = [r for r in results if r["expected"] == True]
    non_csv_tests = [r for r in results if r["expected"] == False]
    
    csv_passed = len([r for r in csv_tests if r["passed"]])
    non_csv_passed = len([r for r in non_csv_tests if r["passed"]])
    
    print(f"CSV Files (should be detected): {csv_passed}/{len(csv_tests)} passed")
    print(f"Non-CSV Files (should be rejected): {non_csv_passed}/{len(non_csv_tests)} passed")
    
    # Exit code based on results
    if len(failed_tests) == 0 and len(error_tests) == 0:
        print("\n🎉 All tests passed!")
        return 0
    else:
        print(f"\n💥 {len(failed_tests) + len(error_tests)} tests failed or had errors")
        return 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
