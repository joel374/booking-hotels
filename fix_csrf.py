import os
import re

def fix_csrf():
    templates_dir = 'templates'

    for root, dirs, files in os.walk(templates_dir):
        for file in files:
            if not file.endswith('.html'):
                continue
                
            filepath = os.path.join(root, file)
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
                
            original_content = content
            
            # Inject CSRF token into missing forms
            def form_replacer(match):
                form_tag = match.group(0)
                # If there's already a csrf_token inside the form (but maybe it failed the check? The check was on form content)
                # We'll just append it directly after the form opening tag.
                return form_tag + '\n    <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">'
            
            # Find forms missing CSRF token
            # We must be careful to only replace forms that are missing it.
            # So we iterate over them.
            form_pattern = re.compile(r'(<form\b[^>]*method=[\'"]?POST[\'"]?[^>]*>)(.*?)</form>', re.IGNORECASE | re.DOTALL)
            
            new_content = ""
            last_end = 0
            for match in form_pattern.finditer(content):
                new_content += content[last_end:match.start()]
                
                form_tag = match.group(1)
                form_inner = match.group(2)
                
                if 'csrf_token' not in form_inner:
                    new_content += form_tag + '\n    <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">' + form_inner + '</form>'
                else:
                    new_content += match.group(0)
                
                last_end = match.end()
            
            new_content += content[last_end:]
            content = new_content
            
            # Now fix missing fetch CSRF tokens
            # For fetch requests we can inject headers: { 'X-CSRFToken': '{{ csrf_token() }}' }
            # Wait, edit_hotel.html:316 uses fetch(form.action, { method: 'POST', body: new FormData(form) })
            # If it uses FormData(form), it doesn't need X-CSRFToken IF the form has the hidden input.
            # We already added the hidden input to the form, but wait, the script found edit_hotel.html:316 because 'csrf_token' wasn't literally in the fetch call.
            # But wait, earlier I fixed `delete-group-form` to have csrf_token!
            # The other fetches in base.html:106 and 119 are:
            # fetch('/notifications/read/...', { method: 'POST' })
            
            # Let's fix base.html manually via regex or just replace specifically:
            fetch_pattern = re.compile(r'(fetch\([^;]+method:\s*[\'"]POST[\'"])(?![\s\S]*?X-CSRFToken)', re.IGNORECASE)
            # This is hard to regex safely for all fetches. I will do string replacement for the known base.html ones.
            if 'base.html' in filepath:
                content = content.replace("{ method: 'POST' }", "{ method: 'POST', headers: { 'X-CSRFToken': '{{ csrf_token() }}' } }")
                
            if content != original_content:
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(content)
                print(f"Fixed CSRF in {filepath}")

if __name__ == '__main__':
    fix_csrf()
