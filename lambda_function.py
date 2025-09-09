import json
import base64
import tempfile
import os
from typing import Dict, Any

# Set up library path for embedded libmagic
import os
import sys

# Add lib directory to library path for libmagic.so.1
lib_path = os.path.join(os.path.dirname(__file__), 'lib')
if os.path.exists(lib_path):
    current_ld_path = os.environ.get('LD_LIBRARY_PATH', '')
    os.environ['LD_LIBRARY_PATH'] = f"{lib_path}:{current_ld_path}"

# Set magic database path if available
magic_data_path = os.path.join(os.path.dirname(__file__), 'magic_data')
if os.path.exists(magic_data_path):
    magic_file = os.path.join(magic_data_path, 'magic.mgc')
    if os.path.exists(magic_file):
        os.environ['MAGIC'] = magic_file

# Import magic with error handling
try:
    import magic
    print("Successfully imported python-magic")
    # Debug: Verify libmagic is available and log version
    try:
        import ctypes
        from ctypes.util import find_library
        libmagic_hint = find_library('magic')
        print(f"ctypes.find_library('magic') -> {libmagic_hint}")

        loaded_lib = None
        candidates = [
            libmagic_hint,
            os.path.join(lib_path, 'libmagic.so.1'),
            os.path.join(lib_path, 'libmagic.so'),
            '/opt/lib/libmagic.so.1',
            '/opt/lib64/libmagic.so.1',
            '/lib64/libmagic.so.1',
            '/usr/lib64/libmagic.so.1'
        ]
        for candidate in [c for c in candidates if c]:
            try:
                loaded_lib = ctypes.CDLL(candidate)
                print(f"Loaded libmagic from: {candidate}")
                break
            except Exception as e:
                print(f"Failed to load libmagic from {candidate}: {e}")

        if loaded_lib is not None:
            try:
                version_val = loaded_lib.magic_version()
                print(f"libmagic version: {version_val}")
            except Exception as e:
                print(f"Could not query libmagic version: {e}")
        else:
            print("libmagic not loaded via ctypes")
    except Exception as e:
        print(f"libmagic load check failed: {e}")
except ImportError as e:
    print(f"Error importing magic: {e}")
    print(f"Current directory: {os.path.dirname(__file__)}")
    print(f"LD_LIBRARY_PATH: {os.environ.get('LD_LIBRARY_PATH', 'NOT SET')}")
    print(f"MAGIC: {os.environ.get('MAGIC', 'NOT SET')}")
    
    # Debug: List files in current directory
    print("Files in function directory:")
    for root, dirs, files in os.walk(os.path.dirname(__file__)):
        for file in files[:20]:  # Limit output
            print(f"  {os.path.join(root, file)}")
        if len(files) > 20:
            print(f"  ... and {len(files) - 20} more files")
        break
    raise


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    AWS Lambda function to validate CSV files using python-magic.
    
    Expects event with:
    - 'file_content': base64 encoded file content
    - 'filename': name of the uploaded file
    
    Returns:
    - success: boolean indicating if file is a valid CSV
    - message: descriptive message
    - mimetype: detected MIME type
    """
    
    try:
        # Handle API Gateway event format
        if 'body' in event:
            # Parse JSON body for API Gateway
            if isinstance(event['body'], str):
                body = json.loads(event['body'])
            else:
                body = event['body']
        else:
            # Direct invocation
            body = event
        
        # Extract file content from event
        if 'file_content' not in body:
            return {
                'statusCode': 400,
                'body': json.dumps({
                    'success': False,
                    'message': 'Missing file_content in request',
                    'mimetype': None
                })
            }
        
        # Decode base64 file content
        file_content = base64.b64decode(body['file_content'])
        filename = body.get('filename', 'unknown')
        
        # Create temporary file to analyze
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            temp_file.write(file_content)
            temp_file_path = temp_file.name
        
        try:
            # Use python-magic to detect MIME type
            mime = magic.Magic(mime=True)
            detected_mimetype = mime.from_file(temp_file_path)
            # Also log the human-readable type description
            try:
                kind_descr = magic.Magic(mime=False).from_file(temp_file_path)
            except Exception:
                kind_descr = None
            print(f"magic detection -> filename={filename}, mime={detected_mimetype}, kind={kind_descr}")
            
            # Check if it's a CSV file
            # CSV files can have various MIME types depending on the system
            csv_mimetypes = [
                'text/csv',
                'application/csv',
                'text/comma-separated-values'
            ]
            
            is_csv = detected_mimetype in csv_mimetypes
            
            # Additional check: if detected as text/plain, check file extension and content
            # Also try alternative magic detection methods for CSV
            if detected_mimetype == 'text/plain' or detected_mimetype.startswith('text/'):
                # Try to detect CSV with different magic approaches
                csv_detected_by_magic = False
                try:
                    # Try with mime_encoding to see if we get more specific info
                    mime_encoding = magic.Magic(mime_encoding=True)
                    encoding = mime_encoding.from_file(temp_file_path)
                    print(f"Detected encoding: {encoding}")
                    
                    # Try reading first few lines to help magic detection
                    with open(temp_file_path, 'rb') as f:
                        sample = f.read(1024)  # First 1KB
                    
                    # Try buffer detection which might be more specific
                    buffer_mime = magic.Magic(mime=True).from_buffer(sample)
                    buffer_desc = magic.Magic(mime=False).from_buffer(sample)
                    print(f"Buffer detection -> mime={buffer_mime}, desc={buffer_desc}")
                    
                    # Check if buffer detection gives us CSV
                    if 'csv' in buffer_mime.lower() or 'csv' in buffer_desc.lower():
                        csv_detected_by_magic = True
                        detected_mimetype = 'text/csv'  # Override
                        
                except Exception as e:
                    print(f"Alternative magic detection failed: {e}")
                
                # Content-based CSV validation (enhanced)
                try:
                    content_str = file_content.decode('utf-8')
                    lines = content_str.strip().split('\n')
                    
                    if len(lines) >= 2:  # Need at least header + 1 data row
                        non_empty_lines = [line.strip() for line in lines if line.strip()]
                        
                        if len(non_empty_lines) >= 2:
                            # Check comma consistency
                            comma_counts = [line.count(',') for line in non_empty_lines]
                            comma_lines = sum(1 for count in comma_counts if count > 0)
                            total_lines = len(non_empty_lines)
                            
                            # More sophisticated CSV detection
                            header_commas = comma_counts[0]
                            consistent_comma_lines = sum(1 for count in comma_counts if count == header_commas)
                            
                            print(f"CSV analysis -> total_lines={total_lines}, comma_lines={comma_lines}, header_commas={header_commas}, consistent={consistent_comma_lines}")
                            
                            # Enhanced criteria for CSV detection
                            csv_criteria_met = (
                                # At least 80% of lines have commas
                                comma_lines >= total_lines * 0.8 and
                                # Header has at least 1 comma (2+ fields)
                                header_commas >= 1 and
                                # At least 70% of lines have same comma count as header
                                consistent_comma_lines >= total_lines * 0.7 and
                                # Filename hint (if available)
                                (filename.lower().endswith('.csv') or 
                                 csv_detected_by_magic or
                                 # Content patterns that suggest CSV
                                 any(keyword in content_str.lower()[:200] for keyword in ['name,', 'id,', 'date,', ',value', ',count', ',amount']))
                            )
                            
                            if csv_criteria_met:
                                is_csv = True
                                print(f"CSV detected by content analysis")
                                
                except UnicodeDecodeError:
                    print("Failed to decode as UTF-8 for CSV analysis")
                    is_csv = False
            
            return {
                'statusCode': 200,
                'body': json.dumps({
                    'success': is_csv,
                    'message': f'File is {"a valid CSV" if is_csv else "not a valid CSV"}',
                    'mimetype': detected_mimetype,
                    'filename': filename
                })
            }
            
        finally:
            # Clean up temporary file
            if os.path.exists(temp_file_path):
                os.unlink(temp_file_path)
                
    except Exception as e:
        return {
            'statusCode': 500,
            'body': json.dumps({
                'success': False,
                'message': f'Error processing file: {str(e)}',
                'mimetype': None
            })
        }


# For local testing
if __name__ == "__main__":
    # Example test with a simple CSV content
    import base64
    
    csv_content = "name,age,city\nJohn,30,New York\nJane,25,Los Angeles"
    encoded_content = base64.b64encode(csv_content.encode()).decode()
    
    test_event = {
        'file_content': encoded_content,
        'filename': 'test.csv'
    }
    
    result = lambda_handler(test_event, None)
    print(json.dumps(result, indent=2))
