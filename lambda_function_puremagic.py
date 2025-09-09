import json
import base64
import tempfile
import os
from typing import Dict, Any

# Import puremagic
try:
    import puremagic
    print("Successfully imported puremagic")
except ImportError as e:
    print(f"Error importing puremagic: {e}")
    raise


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    AWS Lambda function to validate CSV files using puremagic.
    
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
            # Use puremagic to detect file type
            # puremagic.from_file() returns a string with the file type, or raises PureError
            try:
                detected_type = puremagic.from_file(temp_file_path)
                print(f"puremagic file detection -> filename={filename}, type={detected_type}")
            except Exception as e:
                print(f"puremagic file detection failed: {e}")
                detected_type = None
            
            # Also try with buffer detection
            try:
                buffer_type = puremagic.from_string(file_content)
                print(f"puremagic buffer detection -> type={buffer_type}")
            except Exception as e:
                print(f"puremagic buffer detection failed: {e}")
                buffer_type = None
            
            # Get a mime type - puremagic doesn't directly provide MIME types
            # We'll need to map the detected type to a MIME type or use content analysis
            detected_mimetype = 'application/octet-stream'  # Default
            
            # Map common puremagic types to MIME types
            if detected_type:
                type_lower = detected_type.lower()
                if 'pdf' in type_lower:
                    detected_mimetype = 'application/pdf'
                elif 'jpeg' in type_lower or 'jpg' in type_lower:
                    detected_mimetype = 'image/jpeg'
                elif 'png' in type_lower:
                    detected_mimetype = 'image/png'
                elif 'text' in type_lower:
                    detected_mimetype = 'text/plain'
                elif 'html' in type_lower:
                    detected_mimetype = 'text/html'
                elif 'xml' in type_lower:
                    detected_mimetype = 'application/xml'
                elif 'json' in type_lower:
                    detected_mimetype = 'application/json'
                print(f"Mapped to MIME type: {detected_mimetype}")
            
            # If no type detected, try to determine if it's text
            if not detected_type:
                try:
                    # Try to decode as text
                    file_content.decode('utf-8')
                    detected_mimetype = 'text/plain'
                    print("Defaulting to text/plain based on UTF-8 decode")
                except UnicodeDecodeError:
                    detected_mimetype = 'application/octet-stream'
                    print("Defaulting to application/octet-stream (binary)")
            
            puremagic_info = {
                'file_detection': detected_type,
                'buffer_detection': buffer_type
            }
            
            # Check if it's a CSV file
            # CSV files can have various MIME types depending on the system
            csv_mimetypes = [
                'text/csv',
                'application/csv',
                'text/comma-separated-values'
            ]
            
            is_csv = detected_mimetype in csv_mimetypes
            
            # Additional check: if detected as text/plain, check file extension and content
            if detected_mimetype == 'text/plain' or detected_mimetype.startswith('text/'):
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
                                 # Content patterns that suggest CSV
                                 any(keyword in content_str.lower()[:200] for keyword in ['name,', 'id,', 'date,', ',value', ',count', ',amount']))
                            )
                            
                            if csv_criteria_met:
                                is_csv = True
                                detected_mimetype = 'text/csv'  # Override
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
                    'filename': filename,
                    'puremagic_details': puremagic_info
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
