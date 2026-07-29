import os
import re

def fix_ide_syntax():
    templates_dir = 'templates'

    for root, dirs, files in os.walk(templates_dir):
        for file in files:
            if not file.endswith('.html'):
                continue
                
            filepath = os.path.join(root, file)
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
                
            original_content = content
            
            # Replace '{{ _('something') }}' with "{{ _('something') }}"
            # We match single quote, then {{ _(, then anything up to ) }}, then single quote
            # Be careful with nested quotes.
            content = re.sub(r"'({{\s*_\('[^']+'\)\s*}})'", r'"\1"', content)
            
            # For innerHTML = '... {{ _('...') }} ...' which is harder to regex generically,
            # Let's fix specific lines like tbody.innerHTML = '<tr>...';
            content = re.sub(
                r"tbody\.innerHTML\s*=\s*'([^']*{{\s*_\('[^']+'\)\s*}}[^']*)';",
                lambda m: f'tbody.innerHTML = `{m.group(1)}`;',
                content
            )
            
            # Replace \'{{\s*_\(\' with "{{\s*_\(\'"
            if content != original_content:
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(content)
                print(f"Fixed quotes in {filepath}")

if __name__ == '__main__':
    fix_ide_syntax()
