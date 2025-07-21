#!/usr/bin/env python3
"""
Script to clean up encoding issues in streamlit_app.py
"""

def clean_file():
    """Clean the file of encoding issues"""
    try:
        # Try reading with different encodings
        content = None
        for encoding in ['utf-8', 'latin1', 'cp1252', 'utf-8-sig']:
            try:
                with open('streamlit_app.py', 'r', encoding=encoding) as f:
                    content = f.read()
                print(f"✅ Successfully read file with {encoding} encoding")
                break
            except UnicodeDecodeError:
                continue
        
        if content is None:
            print("❌ Could not read file with any encoding")
            return False
        
        # Clean up any problematic characters
        # Remove non-printable characters except common whitespace
        import re
        content = re.sub(r'[^\x20-\x7E\t\r\n]', '', content)
        
        # Write back as UTF-8
        with open('streamlit_app.py', 'w', encoding='utf-8') as f:
            f.write(content)
        
        print("✅ Cleaned up encoding issues")
        return True
        
    except Exception as e:
        print(f"❌ Error cleaning file: {e}")
        return False

def test_syntax():
    """Test if the file has valid Python syntax"""
    try:
        with open('streamlit_app.py', 'r', encoding='utf-8') as f:
            content = f.read()
        
        import ast
        ast.parse(content)
        print("✅ File has valid Python syntax!")
        return True
    except SyntaxError as e:
        print(f"❌ Syntax error: {e}")
        return False
    except Exception as e:
        print(f"❌ Error testing syntax: {e}")
        return False

if __name__ == "__main__":
    if clean_file():
        test_syntax() 