#!/usr/bin/env python3
"""
Head-to-head benchmark comparison between python-magic and puremagic.
Now that both are working, we can get real performance comparisons.
"""

import json
import base64
import time
import statistics
from pathlib import Path
from typing import Dict, Any, List, Tuple
import sys
import os
import tempfile

# Import both implementations
from lambda_function_puremagic import lambda_handler as puremagic_handler
from lambda_function import lambda_handler as python_magic_handler

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

def create_comprehensive_test_data():
    """Create comprehensive test data for head-to-head comparison."""
    tests = []
    
    # 1. Real files first
    test_files_dir = Path("test_files")
    if test_files_dir.exists():
        real_files = [
            ("Real PDF", "IdentificationBooklet_web.pdf", False),
            ("Real CSV", "contribution_strategy_census.csv", True),
            ("Real JPEG", "cat.jpeg", False),
        ]
        
        for name, filename, is_csv in real_files:
            file_path = test_files_dir / filename
            if file_path.exists():
                content = file_path.read_bytes()
                tests.append((name, content, filename, is_csv))
    
    # 2. Synthetic test cases of various sizes
    test_cases = [
        # Small files
        ("CSV Tiny", "name,age\nJohn,30\nJane,25", "tiny.csv", True),
        ("JSON Tiny", '{"name": "John", "age": 30}', "tiny.json", False),
        ("HTML Tiny", "<html><body>Hello</body></html>", "tiny.html", False),
        ("XML Tiny", '<?xml version="1.0"?><root><item>test</item></root>', "tiny.xml", False),
        
        # Medium files
        ("CSV Medium", generate_csv_data(100), "medium.csv", True),
        ("JSON Medium", generate_json_data(50), "medium.json", False),
        ("HTML Medium", generate_html_data(100), "medium.html", False),
        ("Text Medium", generate_text_data(500), "medium.txt", False),
        
        # Large files
        ("CSV Large", generate_csv_data(1000), "large.csv", True),
        ("JSON Large", generate_json_data(500), "large.json", False),
        
        # Edge cases
        ("Empty", "", "empty.csv", False),
        ("CSV Header Only", "name,age,city", "header.csv", False),
        ("CSV with Quotes", 'name,description\n"John","Software Engineer"\n"Jane","Data Scientist"', "quoted.csv", True),
        ("Malformed CSV", "name,age\nJohn,30\nJane\nBob,25,extra", "bad.csv", False),
        
        # Binary-like content
        ("PDF Header", "%PDF-1.4\n1 0 obj\n<<\n/Type /Catalog\n>>\nendobj", "fake.pdf", False),
        ("JPEG Header", b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01", "fake.jpg", False),
    ]
    
    for name, content, filename, is_csv in test_cases:
        if isinstance(content, str):
            content = content.encode('utf-8')
        tests.append((name, content, filename, is_csv))
    
    return tests

def generate_csv_data(rows: int) -> str:
    """Generate CSV data with specified number of rows."""
    lines = ["id,name,email,department,salary,hire_date"]
    for i in range(rows):
        lines.append(f"{i+1},User{i+1},user{i+1}@test.com,Engineering,{50000 + i*100},2020-{1+(i%12):02d}-{1+(i%28):02d}")
    return "\n".join(lines)

def generate_json_data(objects: int) -> str:
    """Generate JSON data with specified number of objects."""
    data = {
        "users": [
            {"id": i+1, "name": f"User{i+1}", "email": f"user{i+1}@test.com", "active": True}
            for i in range(objects)
        ],
        "total": objects,
        "generated": "2024-01-01T00:00:00Z"
    }
    return json.dumps(data, indent=2)

def generate_html_data(elements: int) -> str:
    """Generate HTML data with specified number of elements."""
    html = ["<!DOCTYPE html>", "<html>", "<head><title>Test</title></head>", "<body>"]
    for i in range(elements):
        html.append(f"<p>This is paragraph {i+1} with some content.</p>")
    html.extend(["</body>", "</html>"])
    return "\n".join(html)

def generate_text_data(words: int) -> str:
    """Generate plain text data."""
    sample_words = ["the", "quick", "brown", "fox", "jumps", "over", "lazy", "dog"] * 10
    return " ".join(sample_words[:words])

class BenchmarkResult:
    def __init__(self, name: str, implementation: str, file_size: int):
        self.name = name
        self.implementation = implementation
        self.file_size = file_size
        self.times = []
        self.success = None
        self.mimetype = None
        self.accuracy = None
        self.error = None
    
    def add_timing(self, exec_time: float):
        self.times.append(exec_time)
    
    def get_stats(self):
        if not self.times:
            return None
        
        return {
            'mean_time': statistics.mean(self.times),
            'median_time': statistics.median(self.times),
            'min_time': min(self.times),
            'max_time': max(self.times),
            'std_dev': statistics.stdev(self.times) if len(self.times) > 1 else 0,
            'throughput': (self.file_size / 1024 / 1024) / statistics.mean(self.times) if self.times else 0
        }

def run_single_benchmark(test_name: str, content: bytes, filename: str, expected_csv: bool, runs: int = 5) -> Tuple[BenchmarkResult, BenchmarkResult]:
    """Run benchmark for both implementations on a single test case."""
    
    file_size = len(content)
    event = {
        'file_content': base64.b64encode(content).decode(),
        'filename': filename
    }
    
    # Benchmark PureMagic
    puremagic_result = BenchmarkResult(test_name, "PureMagic", file_size)
    
    # Warmup
    try:
        puremagic_handler(event, None)
    except:
        pass
    
    first_pm_result = None
    for i in range(runs):
        try:
            # Suppress output during timing
            old_stdout = sys.stdout
            sys.stdout = open(os.devnull, 'w')
            
            result, exec_time = time_function(puremagic_handler, event, None)
            puremagic_result.add_timing(exec_time)
            
            if i == 0:
                first_pm_result = result
                
        except Exception as e:
            puremagic_result.error = str(e)
            break
        finally:
            sys.stdout.close()
            sys.stdout = sys.__stdout__
    
    # Parse PureMagic result
    if first_pm_result and not puremagic_result.error:
        try:
            body = json.loads(first_pm_result['body']) if isinstance(first_pm_result['body'], str) else first_pm_result['body']
            puremagic_result.success = body.get('success', False)
            puremagic_result.mimetype = body.get('mimetype', 'unknown')
            puremagic_result.accuracy = puremagic_result.success == expected_csv
        except:
            puremagic_result.error = "Result parsing failed"
    
    # Benchmark Python-Magic
    python_magic_result = BenchmarkResult(test_name, "Python-Magic", file_size)
    
    # Warmup
    try:
        python_magic_handler(event, None)
    except:
        pass
    
    first_pm_result = None
    for i in range(runs):
        try:
            # Suppress output during timing
            old_stdout = sys.stdout
            sys.stdout = open(os.devnull, 'w')
            
            result, exec_time = time_function(python_magic_handler, event, None)
            python_magic_result.add_timing(exec_time)
            
            if i == 0:
                first_pm_result = result
                
        except Exception as e:
            python_magic_result.error = str(e)
            break
        finally:
            sys.stdout.close()
            sys.stdout = sys.__stdout__
    
    # Parse Python-Magic result  
    if first_pm_result and not python_magic_result.error:
        try:
            body = json.loads(first_pm_result['body']) if isinstance(first_pm_result['body'], str) else first_pm_result['body']
            python_magic_result.success = body.get('success', False)
            python_magic_result.mimetype = body.get('mimetype', 'unknown')
            python_magic_result.accuracy = python_magic_result.success == expected_csv
        except:
            python_magic_result.error = "Result parsing failed"
    
    return puremagic_result, python_magic_result

def print_detailed_results(results: List[Tuple[BenchmarkResult, BenchmarkResult]]):
    """Print detailed comparison results."""
    
    print(f"\n{'='*100}")
    print("📊 DETAILED HEAD-TO-HEAD BENCHMARK RESULTS")
    print(f"{'='*100}")
    
    # Header
    print(f"{'Test Case':<20} {'Implementation':<12} {'Mean Time':<12} {'Throughput':<12} {'MIME Type':<20} {'Accuracy':<8}")
    print("-" * 100)
    
    for puremagic_result, python_magic_result in results:
        for result in [puremagic_result, python_magic_result]:
            if result.error:
                print(f"{result.name:<20} {result.implementation:<12} {'ERROR':<12} {'ERROR':<12} {'ERROR':<20} {'ERROR':<8}")
            else:
                stats = result.get_stats()
                if stats:
                    accuracy_symbol = "✅" if result.accuracy else "❌"
                    throughput_str = f"{stats['throughput']:.1f} MB/s"
                    print(f"{result.name:<20} {result.implementation:<12} "
                          f"{format_time(stats['mean_time']):<12} "
                          f"{throughput_str:<12} "
                          f"{result.mimetype[:19]:<20} "
                          f"{accuracy_symbol:<8}")
        print("-" * 100)

def print_summary_analysis(results: List[Tuple[BenchmarkResult, BenchmarkResult]]):
    """Print comprehensive summary analysis."""
    
    print(f"\n{'='*80}")
    print("📈 COMPREHENSIVE ANALYSIS")
    print(f"{'='*80}")
    
    # Collect data
    puremagic_times = []
    python_magic_times = []
    puremagic_accurate = 0
    python_magic_accurate = 0
    total_tests = 0
    
    puremagic_csv_correct = 0
    python_magic_csv_correct = 0
    csv_tests = 0
    
    for pm_result, py_result in results:
        total_tests += 1
        
        if not pm_result.error and pm_result.times:
            puremagic_times.extend(pm_result.times)
            if pm_result.accuracy:
                puremagic_accurate += 1
        
        if not py_result.error and py_result.times:
            python_magic_times.extend(py_result.times)
            if py_result.accuracy:
                python_magic_accurate += 1
        
        # Check CSV-specific accuracy
        if hasattr(pm_result, 'accuracy') and pm_result.accuracy is not None:
            csv_tests += 1
            if pm_result.accuracy:
                puremagic_csv_correct += 1
            if py_result.accuracy:
                python_magic_csv_correct += 1
    
    # Performance comparison
    print(f"\n🏃‍♂️ Performance Comparison:")
    if puremagic_times and python_magic_times:
        pm_mean = statistics.mean(puremagic_times)
        py_mean = statistics.mean(python_magic_times)
        
        print(f"   PureMagic Average: {format_time(pm_mean)}")
        print(f"   Python-Magic Average: {format_time(py_mean)}")
        
        if pm_mean < py_mean:
            speedup = py_mean / pm_mean
            print(f"   🚀 PureMagic is {speedup:.2f}x FASTER")
        else:
            speedup = pm_mean / py_mean
            print(f"   🐌 PureMagic is {speedup:.2f}x slower")
        
        print(f"   PureMagic Range: {format_time(min(puremagic_times))} - {format_time(max(puremagic_times))}")
        print(f"   Python-Magic Range: {format_time(min(python_magic_times))} - {format_time(max(python_magic_times))}")
    
    # Accuracy comparison
    print(f"\n🎯 Accuracy Comparison:")
    print(f"   PureMagic: {puremagic_accurate}/{total_tests} correct ({puremagic_accurate/total_tests*100:.1f}%)")
    print(f"   Python-Magic: {python_magic_accurate}/{total_tests} correct ({python_magic_accurate/total_tests*100:.1f}%)")
    
    # File size analysis
    print(f"\n📏 Performance by File Size:")
    size_categories = [
        ("Tiny (<100B)", lambda r: r.file_size < 100),
        ("Small (100B-1KB)", lambda r: 100 <= r.file_size < 1024),
        ("Medium (1KB-100KB)", lambda r: 1024 <= r.file_size < 100*1024),
        ("Large (>100KB)", lambda r: r.file_size >= 100*1024)
    ]
    
    for cat_name, size_filter in size_categories:
        pm_times_cat = []
        py_times_cat = []
        
        for pm_result, py_result in results:
            if size_filter(pm_result):
                if not pm_result.error and pm_result.times:
                    pm_times_cat.extend(pm_result.times)
                if not py_result.error and py_result.times:
                    py_times_cat.extend(py_result.times)
        
        if pm_times_cat and py_times_cat:
            pm_avg = statistics.mean(pm_times_cat)
            py_avg = statistics.mean(py_times_cat)
            print(f"   {cat_name}: PureMagic {format_time(pm_avg)}, Python-Magic {format_time(py_avg)}")

def main():
    """Run comprehensive head-to-head benchmark."""
    print("⚔️  HEAD-TO-HEAD BENCHMARK: PureMagic vs Python-Magic")
    print("="*80)
    print("Both implementations are loaded and ready for comparison!")
    
    test_data = create_comprehensive_test_data()
    print(f"\n📋 Running {len(test_data)} test cases with 5 runs each...")
    
    results = []
    
    for i, (test_name, content, filename, expected_csv) in enumerate(test_data, 1):
        print(f"\n🧪 [{i:2d}/{len(test_data)}] {test_name} ({format_size(len(content))})")
        
        puremagic_result, python_magic_result = run_single_benchmark(
            test_name, content, filename, expected_csv, runs=5
        )
        
        results.append((puremagic_result, python_magic_result))
        
        # Quick status update
        pm_status = "✅" if not puremagic_result.error and puremagic_result.accuracy else "❌"
        py_status = "✅" if not python_magic_result.error and python_magic_result.accuracy else "❌"
        
        pm_time = format_time(statistics.mean(puremagic_result.times)) if puremagic_result.times else "ERROR"
        py_time = format_time(statistics.mean(python_magic_result.times)) if python_magic_result.times else "ERROR"
        
        print(f"     PureMagic: {pm_time} {pm_status}")
        print(f"     Python-Magic: {py_time} {py_status}")
    
    # Print detailed results
    print_detailed_results(results)
    print_summary_analysis(results)
    
    print(f"\n{'='*80}")
    print("🏆 FINAL VERDICT")
    print(f"{'='*80}")
    print("Both implementations tested head-to-head with real performance data!")
    print("Check the detailed results above for timing, accuracy, and deployment trade-offs.")

if __name__ == "__main__":
    main()
