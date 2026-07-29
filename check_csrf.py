import os
import re

def check_csrf():
    templates_dir = 'templates'
    missing_forms = []
    missing_fetches = []

    for root, dirs, files in os.walk(templates_dir):
        for file in files:
            if file.endswith('.html'):
                filepath = os.path.join(root, file)
                with open(filepath, 'r', encoding='utf-8') as f:
                    content = f.read()

                # Find all POST forms. 
                # A basic regex to extract everything between <form ...> and </form>
                # and check if method is POST
                form_pattern = re.compile(r'<form\b[^>]*method=[\'"]?POST[\'"]?[^>]*>(.*?)</form>', re.IGNORECASE | re.DOTALL)
                for match in form_pattern.finditer(content):
                    form_content = match.group(1)
                    if 'csrf_token' not in form_content:
                        # get line number
                        line_num = content[:match.start()].count('\n') + 1
                        missing_forms.append(f"{filepath}:{line_num}")

                # Find all fetch calls with POST
                fetch_pattern = re.compile(r'fetch\([^;]+method:\s*[\'"]POST[\'"][^;]*\)', re.IGNORECASE | re.DOTALL)
                for match in fetch_pattern.finditer(content):
                    fetch_content = match.group(0)
                    if 'X-CSRFToken' not in fetch_content and 'csrf_token' not in fetch_content:
                        line_num = content[:match.start()].count('\n') + 1
                        missing_fetches.append(f"{filepath}:{line_num}")

    print("--- Missing CSRF in Forms ---")
    for mf in missing_forms:
        print(mf)

    print("\n--- Missing CSRF in Fetches ---")
    for mf in missing_fetches:
        print(mf)

if __name__ == '__main__':
    check_csrf()
