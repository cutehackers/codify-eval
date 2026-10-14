"""Closed, unescaped, no-substitution cmd literals. Never evaluate actor code."""
import json
import re

from transport import OPTIONS


EXPRESSION = (r'text\s*\(\s*await\s+tools\.exec_command\s*\(\s*\{\s*"?cmd"?\s*:\s*'
              r'`([^`\\]*)`(' + OPTIONS + r')\s*\}\s*\)\s*\)\s*;?\s*')


def project(code):
    if not isinstance(code, str):
        return None
    match = re.fullmatch(EXPRESSION, code.strip(), re.S)
    if not match or '${' in match.group(1):
        return None
    # ECMAScript normalizes raw line terminators within a template literal.
    command = match.group(1).replace('\r\n', '\n').replace('\r', '\n')
    return 'text(await tools.exec_command({"cmd":' + json.dumps(command) + match.group(2) + '}));'
