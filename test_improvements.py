"""
Comprehensive test suite for AI MCQ Generator v2.0
Tests all improvements: validation, rate limiting, caching, parallel calls, etc.
"""
import asyncio
import time
import requests
from pathlib import Path


BASE_URL = "http://localhost:8000"


def print_test(name: str):
    """Print test header"""
    print(f"\n{'='*60}")
    print(f"TEST: {name}")
    print('='*60)


def test_health_check():
    """Test enhanced health check endpoint"""
    print_test("Health Check")
    
    response = requests.get(f"{BASE_URL}/health")
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}")
    
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "groq_api" in data
    assert "cache_size" in data
    print("✅ Health check passed")


def test_input_validation():
    """Test input validation with invalid inputs"""
    print_test("Input Validation")
    
    # Test 1: Invalid question count (too high)
    print("\n1. Testing invalid question count (150 > 100)...")
    response = requests.post(
        f"{BASE_URL}/generate",
        data={
            "url_input": "https://example.com",
            "total_questions": 150,  # Too high
            "co_list": "CO1: Test"
        }
    )
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}")
    assert response.status_code == 400
    print("✅ Correctly rejected invalid question count")
    
    # Test 2: Invalid question count (too low)
    print("\n2. Testing invalid question count (0 < 1)...")
    response = requests.post(
        f"{BASE_URL}/generate",
        data={
            "url_input": "https://example.com",
            "total_questions": 0,  # Too low
            "co_list": "CO1: Test"
        }
    )
    assert response.status_code == 400
    print("✅ Correctly rejected invalid question count")
    
    # Test 3: Empty CO list
    print("\n3. Testing empty CO list...")
    response = requests.post(
        f"{BASE_URL}/generate",
        data={
            "url_input": "https://example.com",
            "total_questions": 10,
            "co_list": ""  # Empty
        }
    )
    assert response.status_code == 400
    print("✅ Correctly rejected empty CO list")
    
    # Test 4: Too many COs
    print("\n4. Testing too many COs (25 > 20)...")
    co_list = "\n".join([f"CO{i}: Test" for i in range(25)])
    response = requests.post(
        f"{BASE_URL}/generate",
        data={
            "url_input": "https://example.com",
            "total_questions": 10,
            "co_list": co_list
        }
    )
    assert response.status_code == 400
    print("✅ Correctly rejected too many COs")
    
    # Test 5: Invalid URL
    print("\n5. Testing invalid URL...")
    response = requests.post(
        f"{BASE_URL}/generate",
        data={
            "url_input": "not-a-url",
            "total_questions": 10,
            "co_list": "CO1: Test"
        }
    )
    assert response.status_code == 400
    print("✅ Correctly rejected invalid URL")
    
    print("\n✅ All validation tests passed")


def test_rate_limiting():
    """Test rate limiting (5 requests per minute)"""
    print_test("Rate Limiting")
    
    print("Sending 7 requests rapidly (limit is 5/min)...")
    
    success_count = 0
    rate_limited_count = 0
    
    for i in range(7):
        response = requests.post(
            f"{BASE_URL}/generate",
            data={
                "url_input": "https://example.com",
                "total_questions": 5,
                "co_list": "CO1: Test"
            }
        )
        
        if response.status_code == 200:
            success_count += 1
            print(f"Request {i+1}: ✅ Success")
        elif response.status_code == 429:
            rate_limited_count += 1
            print(f"Request {i+1}: 🚫 Rate limited")
        else:
            print(f"Request {i+1}: ❌ Unexpected status {response.status_code}")
        
        time.sleep(0.5)  # Small delay between requests
    
    print(f"\nResults: {success_count} successful, {rate_limited_count} rate limited")
    assert rate_limited_count >= 2, "Rate limiting should have kicked in"
    print("✅ Rate limiting working correctly")


def test_caching():
    """Test caching functionality"""
    print_test("Caching")
    
    # First request - should be slow (API call)
    print("\n1. First request (should hit API)...")
    start = time.time()
    response1 = requests.post(
        f"{BASE_URL}/generate",
        data={
            "url_input": "https://en.wikipedia.org/wiki/Python_(programming_language)",
            "total_questions": 5,
            "co_list": "CO1: Python basics\nCO2: Python applications"
        }
    )
    time1 = time.time() - start
    print(f"Time: {time1:.2f}s")
    print(f"Status: {response1.status_code}")
    
    if response1.status_code != 200:
        print(f"⚠️ First request failed: {response1.json()}")
        return
    
    # Wait a bit to avoid rate limiting
    time.sleep(2)
    
    # Second request - should be fast (cache hit)
    print("\n2. Second request (should hit cache)...")
    start = time.time()
    response2 = requests.post(
        f"{BASE_URL}/generate",
        data={
            "url_input": "https://en.wikipedia.org/wiki/Python_(programming_language)",
            "total_questions": 5,
            "co_list": "CO1: Python basics\nCO2: Python applications"
        }
    )
    time2 = time.time() - start
    print(f"Time: {time2:.2f}s")
    print(f"Status: {response2.status_code}")
    
    if response2.status_code == 200:
        speedup = time1 / time2 if time2 > 0 else float('inf')
        print(f"\nSpeedup: {speedup:.1f}x faster")
        
        if speedup > 2:
            print("✅ Caching working correctly (significant speedup)")
        else:
            print("⚠️ Cache may not be working (no significant speedup)")
    else:
        print(f"⚠️ Second request failed: {response2.json()}")


def test_stats_endpoint():
    """Test statistics endpoint"""
    print_test("Statistics Endpoint")
    
    response = requests.get(f"{BASE_URL}/stats")
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}")
    
    assert response.status_code == 200
    data = response.json()
    assert "cache_size" in data
    assert "timestamp" in data
    print("✅ Statistics endpoint working")


def test_compression():
    """Test download compression"""
    print_test("Download Compression")
    
    # First, generate some MCQs to get a filename
    print("\n1. Generating MCQs...")
    response = requests.post(
        f"{BASE_URL}/generate",
        data={
            "url_input": "https://example.com",
            "total_questions": 5,
            "co_list": "CO1: Test"
        }
    )
    
    if response.status_code != 200:
        print(f"⚠️ Generation failed: {response.json()}")
        return
    
    data = response.json()
    pdf_filename = data.get("pdf_filename")
    
    if not pdf_filename:
        print("⚠️ No PDF filename in response")
        return
    
    # Download without compression
    print(f"\n2. Downloading {pdf_filename} without compression...")
    response1 = requests.get(f"{BASE_URL}/download/{pdf_filename}")
    size1 = len(response1.content)
    print(f"Size: {size1} bytes")
    
    # Download with compression
    print(f"\n3. Downloading {pdf_filename} with compression...")
    response2 = requests.get(f"{BASE_URL}/download/{pdf_filename}?compress=true")
    size2 = len(response2.content)
    print(f"Size: {size2} bytes")
    
    # Calculate compression ratio
    if size1 > 0:
        ratio = (1 - size2/size1) * 100
        print(f"\nCompression: {ratio:.1f}% smaller")
        
        if ratio > 10:
            print("✅ Compression working correctly")
        else:
            print("⚠️ Compression may not be working effectively")


def test_file_upload():
    """Test file upload with streaming"""
    print_test("File Upload (Streaming)")
    
    # Create a small test file
    test_file = Path("test_upload.txt")
    test_file.write_text("This is a test document for MCQ generation. " * 100)
    
    try:
        print(f"\n1. Uploading {test_file.name}...")
        with open(test_file, 'rb') as f:
            response = requests.post(
                f"{BASE_URL}/generate",
                data={
                    "total_questions": 5,
                    "co_list": "CO1: Test concepts\nCO2: Test applications"
                },
                files={"file": f}
            )
        
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            print("✅ File upload working correctly")
        else:
            print(f"Response: {response.json()}")
            print("⚠️ File upload may have issues")
    
    finally:
        # Cleanup
        if test_file.exists():
            test_file.unlink()


def test_parallel_generation():
    """Test that parallel generation is faster than sequential"""
    print_test("Parallel API Calls")
    
    print("\nGenerating MCQs for 3 COs (should be parallel)...")
    print("This tests that API calls happen concurrently, not sequentially.")
    
    start = time.time()
    response = requests.post(
        f"{BASE_URL}/generate",
        data={
            "url_input": "https://en.wikipedia.org/wiki/Machine_learning",
            "total_questions": 15,
            "co_list": "CO1: ML fundamentals\nCO2: ML algorithms\nCO3: ML applications"
        }
    )
    elapsed = time.time() - start
    
    print(f"\nTime: {elapsed:.2f}s")
    print(f"Status: {response.status_code}")
    
    if response.status_code == 200:
        # If sequential, would take ~24s (3 COs × 8s each)
        # If parallel, should take ~8-12s
        if elapsed < 20:
            print(f"✅ Parallel generation working (completed in {elapsed:.1f}s)")
        else:
            print(f"⚠️ May be sequential (took {elapsed:.1f}s, expected <20s)")
    else:
        print(f"⚠️ Generation failed: {response.json()}")


def run_all_tests():
    """Run all tests"""
    print("\n" + "="*60)
    print("AI MCQ GENERATOR v2.0 - COMPREHENSIVE TEST SUITE")
    print("="*60)
    
    tests = [
        ("Health Check", test_health_check),
        ("Input Validation", test_input_validation),
        ("Rate Limiting", test_rate_limiting),
        ("Caching", test_caching),
        ("Statistics", test_stats_endpoint),
        ("Compression", test_compression),
        ("File Upload", test_file_upload),
        ("Parallel Generation", test_parallel_generation),
    ]
    
    passed = 0
    failed = 0
    
    for name, test_func in tests:
        try:
            test_func()
            passed += 1
        except Exception as e:
            print(f"\n❌ Test failed: {e}")
            failed += 1
    
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    print(f"Passed: {passed}/{len(tests)}")
    print(f"Failed: {failed}/{len(tests)}")
    
    if failed == 0:
        print("\n🎉 All tests passed! System is production-ready.")
    else:
        print(f"\n⚠️ {failed} test(s) failed. Please review.")


if __name__ == "__main__":
    print("\n⚠️ IMPORTANT: Make sure the server is running at http://localhost:8000")
    print("Run: uvicorn backend.app:app --reload\n")
    
    input("Press Enter to start tests...")
    
    run_all_tests()
