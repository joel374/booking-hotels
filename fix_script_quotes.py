import os
import re

def fix_script_quotes():
    templates_dir = 'templates'

    for root, dirs, files in os.walk(templates_dir):
        for file in files:
            if not file.endswith('.html'):
                continue
                
            filepath = os.path.join(root, file)
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
                
            original_content = content
            
            # Find all <script> blocks and replace _('...') with _("...")
            def script_replacer(match):
                script_content = match.group(0)
                # Replace _('...') with _("...") inside the script block
                # Be careful not to replace _('"') or something weird, but assuming standard strings.
                fixed_script = re.sub(r"_\('([^']+)'\)", r'_("\1")', script_content)
                return fixed_script

            content = re.sub(r'<script.*?>.*?</script>', script_replacer, content, flags=re.IGNORECASE | re.DOTALL)
            
            # Also fix inline handlers like onclick="..."
            def onclick_replacer(match):
                onclick_content = match.group(0)
                # If there are Jinja variables like {{ group.quantity }}, we can't easily fix them all, 
                # but we can try quoting them if they are numbers: {{ group.max_number }} -> '{{ group.max_number }}'
                # Let's fix the specific one in edit_hotel.html
                if 'openAddMoreRoomsModal' in onclick_content or 'openDeleteGroupModal' in onclick_content:
                    onclick_content = re.sub(r',\s*({{[^}]+}})', r", '\1'", onclick_content)
                return onclick_content
                
            content = re.sub(r'onclick="[^"]+"', onclick_replacer, content, flags=re.IGNORECASE)

            if content != original_content:
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(content)
                print(f"Fixed script quotes in {filepath}")

if __name__ == '__main__':
    fix_script_quotes()
