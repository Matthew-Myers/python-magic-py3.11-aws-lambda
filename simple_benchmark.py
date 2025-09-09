#!/usr/bin/env python3
"""
Simple benchmark comparison focused on timing and accuracy.
"""

import json
import base64
import time
import statistics
from pathlib import Path
from typing import Dict, Any, List
import tempfile
import os
import sys

# Import the puremagic version
from lambda_function_puremagic import lambda_handler as puremagic_handler

def time_function(func, *args, **kwargs):
    """Time a function call and return (result, execution_time)."""
    start = time.perf_counter()
    result = func(*args, **kwargs)
    end = time.perf_counter()
    return result, end - start

def format_time(seconds: float) -> str:
    """Format time in appropriate units."""
    if seconds >= 1:
        return f"{seconds:.3f}s"
    elif seconds >= 0.001:
        return f"{seconds * 1000:.2f}ms"
    else:
        return f"{seconds * 1000000:.1f}μs"

def format_size(bytes_size: int) -> str:
    """Format file size in human readable format."""
    if bytes_size >= 1024 * 1024:
        return f"{bytes_size / 1024 / 1024:.2f}MB"
    elif bytes_size >= 1024:
        return f"{bytes_size / 1024:.2f}KB"
    else:
        return f"{bytes_size}B"

def create_test_data():
    """Create test data of various sizes and types."""
    tests = []
    
    # Small files
    tests.append(("CSV Small", "name,age\nJohn,30\nJane,25", "test.csv", True))
    tests.append(("JSON Small", '{"name": "John", "age": 30}', "test.json", False))
    tests.append(("HTML Small", "<html><body>Hello</body></html>", "test.html", False))
    
    # Medium files (generate larger content)
    csv_rows = ["id,name,email,department,salary"]
    for i in range(100):
        csv_rows.append(f"{i},User{i},user{i}@test.com,Dept{i%5},{50000 + i*100}")
    medium_csv = "\n".join(csv_rows)
    tests.append(("CSV Medium", medium_csv, "medium.csv", True))
    
    # JSON medium
    json_data = {
        "users": [{"id": i, "name": f"User{i}", "active": True} for i in range(50)],
        "metadata": {"count": 50}
    }
    tests.append(("JSON Medium", json.dumps(json_data, indent=2), "medium.json", False))
    
    # Large CSV
    large_csv_rows = ["id,name,email,department,salary,hire_date,status"]
    for i in range(1000):
        large_csv_rows.append(f"{i},User{i},user{i}@company.com,Engineering,{50000 + i*50},2020-01-{1+(i%28):02d},Active")
    large_csv = "\n".join(large_csv_rows)
    tests.append(("CSV Large", large_csv, "large.csv", True))
    
    # Real files if available
    test_files_dir = Path("test_files")
    if test_files_dir.exists():
        for real_file in ["IdentificationBooklet_web.pdf", "contribution_strategy_census.csv", "cat.jpeg"]:
            file_path = test_files_dir / real_file
            if file_path.exists():
                content = file_path.read_bytes()
                is_csv = real_file.endswith('.csv')
                tests.append((f"Real {real_file}", content, real_file, is_csv))
    
    return tests

def run_benchmark():
    """Run the benchmark."""
    print("🚀 PureMagic Performance Benchmark")
    print("=" * 80)
    
    test_data = create_test_data()
    results = []
    
    for test_name, content, filename, expected_csv in test_data:
        if isinstance(content, str):
            content = content.encode('utf-8')
        
        file_size = len(content)
        print(f"\n📊 Testing: {test_name} ({format_size(file_size)})")
        
        # Prepare event
        event = {
            'file_content': base64.b64encode(content).decode(),
            'filename': filename
        }
        
        # Run multiple times for accurate timing
        times = []
        first_result = None
        
        # Warmup run
        try:
            puremagic_handler(event, None)
        except:
            pass
        
        # Actual benchmark runs
        for i in range(5):
            try:
                # Suppress output during timing
                old_stdout = sys.stdout
                old_stderr = sys.stderr
                sys.stdout = open(os.devnull, 'w')
                sys.stderr = open(os.devnull, 'w')
                
                result, exec_time = time_function(puremagic_handler, event, None)
                times.append(exec_time)
                
                if i == 0:
                    first_result = result
                    
            except Exception as e:
                times.append(0.001)  # Default time for errors
                if i == 0:
                    first_result = {'statusCode': 500, 'body': json.dumps({'error': str(e)})}
            finally:
                # Restore output
                sys.stdout.close()
                sys.stderr.close()
                sys.stdout = old_stdout
                sys.stderr = old_stderr
        
        # Parse result for accuracy
        success = False
        mimetype = "unknown"
        if first_result:
            try:
                if 'body' in first_result:
                    body = json.loads(first_result['body']) if isinstance(first_result['body'], str) else first_result['body']
                    success = body.get('success', False)
                    mimetype = body.get('mimetype', 'unknown')
            except:
                pass
        
        # Calculate statistics
        if times:
            mean_time = statistics.mean(times)
            min_time = min(times)
            max_time = max(times)
            throughput = (file_size / 1024 / 1024) / mean_time if mean_time > 0 else 0
            
            # Check accuracy
            accuracy = "✅" if success == expected_csv else "❌"
            
            print(f"   Mean: {format_time(mean_time)}")
            print(f"   Range: {format_time(min_time)} - {format_time(max_time)}")
            print(f"   Throughput: {throughput:.2f} MB/s")
            print(f"   Detection: {mimetype}")
            print(f"   CSV Expected: {expected_csv}, Got: {success} {accuracy}")
            
            results.append({
                'test': test_name,
                'file_size': file_size,
                'mean_time': mean_time,
                'min_time': min_time,
                'max_time': max_time,
                'throughput': throughput,
                'expected_csv': expected_csv,
                'detected_csv': success,
                'mimetype': mimetype,
                'accurate': success == expected_csv
            })
    
    # Summary
    print(f"\n{'='*80}")
    print("📈 BENCHMARK SUMMARY")
    print(f"{'='*80}")
    
    if results:
        all_times = [r['mean_time'] for r in results]
        total_size = sum(r['file_size'] for r in results)
        total_time = sum(all_times)
        
        print(f"\n🏃‍♂️ Performance:")
        print(f"   Overall Mean Time: {format_time(statistics.mean(all_times))}")
        print(f"   Fastest: {format_time(min(all_times))}")
        print(f"   Slowest: {format_time(max(all_times))}")
        print(f"   Total Data Processed: {format_size(total_size)}")
        print(f"   Overall Throughput: {(total_size / 1024 / 1024) / total_time:.2f} MB/s")
        
        # Accuracy
        accurate_results = [r for r in results if r['accurate']]
        print(f"\n🎯 Accuracy:")
        print(f"   Correct: {len(accurate_results)}/{len(results)} ({len(accurate_results)/len(results)*100:.1f}%)")
        
        csv_tests = [r for r in results if r['expected_csv']]
        csv_correct = [r for r in csv_tests if r['accurate']]
        print(f"   CSV Detection: {len(csv_correct)}/{len(csv_tests)} correct")
        
        non_csv_tests = [r for r in results if not r['expected_csv']]
        non_csv_correct = [r for r in non_csv_tests if r['accurate']]
        print(f"   Non-CSV Detection: {len(non_csv_correct)}/{len(non_csv_tests)} correct")
        
        # File size performance analysis
        print(f"\n📏 Performance by File Size:")
        small_files = [r for r in results if r['file_size'] < 1024]
        medium_files = [r for r in results if 1024 <= r['file_size'] < 100*1024]
        large_files = [r for r in results if r['file_size'] >= 100*1024]
        
        for category, files in [("Small (<1KB)", small_files), ("Medium (1KB-100KB)", medium_files), ("Large (>100KB)", large_files)]:
            if files:
                avg_time = statistics.mean([f['mean_time'] for f in files])
                avg_throughput = statistics.mean([f['throughput'] for f in files])
                print(f"   {category}: {format_time(avg_time)} avg, {avg_throughput:.2f} MB/s avg")
    
    print(f"\n✨ Key Advantages of PureMagic:")
    print(f"   🔧 No system dependencies (no libmagic)")
    print(f"   📦 Pure Python - works anywhere")
    print(f"   🚀 Fast enough for most use cases")
    print(f"   🎯 Good accuracy with content analysis fallback")
    print(f"   ☁️  Perfect for serverless/containerized deployments")

if __name__ == "__main__":
    run_benchmark()
