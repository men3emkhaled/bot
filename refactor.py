import re
import ast
import textwrap

with open('bot.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Fix the invalid escape sequence
content = content.replace(r'\_', r'\\_')

def replacer(match):
    var_name = match.group(1)
    inner_block = match.group(2)
    # The inner block is something like:
    # "line1\n"
    # "line2\n"
    # Let's ast.literal_eval the whole thing as a tuple of strings or a concatenated string
    try:
        # Wrap in parentheses so ast evaluates it as a single string (implied concatenation)
        eval_str = "(" + inner_block + ")"
        val = ast.literal_eval(eval_str)
        if isinstance(val, str):
            # Dedent formatting:
            # We want to format it so that textwrap.dedent("""\ ... """) works.
            # We can simply do:
            # textwrap.dedent('''\
            # {val}''')
            # But we must ensure it's properly indented.
            lines = val.split('\n')
            indented_lines = ['    ' + line if line else '' for line in lines]
            new_inner = '\n'.join(indented_lines)
            
            # Since we replaced \_ with \\_, the evaluated string will have \_
            # So we should dump it back safely, escaping backslashes
            new_inner = new_inner.replace('\\', '\\\\')
            
            return f'{var_name} = textwrap.dedent("""\\\n{new_inner}""")'
    except Exception as e:
        print(f"Failed to process {var_name}: {e}")
        return match.group(0)

# XRAY_LABS_TEXT is already dedented, so we can exclude it or just process all of them
pattern = r'^([A-Z_]+_TEXT|EMERGENCY_PHARMACY_INFO)\s*=\s*\(([\s\S]*?)\n\)'
new_content = re.sub(pattern, replacer, content, flags=re.MULTILINE)

with open('bot.py', 'w', encoding='utf-8') as f:
    f.write(new_content)
print("Done")
