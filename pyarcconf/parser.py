"""Pyarcconf submodule, which provides methods for easier output parsing."""

SEPARATOR_ATTRIBUTE = ' : '
SEPARATOR_SECTION = 56 * '-'


def cut_lines(output, start, end=0):
    """Cut a number of lines from the start and the end.

    Args:
        output (str): command output from arcconf
        start (int): offset from start
        end (int): offset from end
    Returns:
        str: cutted output
    """
    output = output.split('\n')
    return '\n'.join(output[start:len(output) - end])


def convert_attribute(key, value=None):
    """Convert an attribute into the most pratical datatype.
   
    If the value is 'enabled', 'yes', 'true', 'disabled', 'no' or 'false'
    it will be converted into boolean, otherwise it stays a string.
    Args:
        key (str): attribute key
        value (str): attribute value
    Returns:
        str, bool: key, value pair
        str, str: formated key, value pair
    """
    if not value:
        if SEPARATOR_ATTRIBUTE not in key:
            print(f'ERROR: {key} is not an attribute')
            return
        key, value = key.split(SEPARATOR_ATTRIBUTE)
    key = convert_key_attribute(key)
    if not key:
        print(f'WARNING: EMPTY KEY RETURNED')

    if len(value.split()) == 2:
        size, unit = value.split()
        if size.isdigit() and unit in ['B', 'KB', 'MB', 'GB']:
            return key, bytes_fmt(float(size))
    value = value.strip().lower()
    if value in ['enabled', 'yes', 'true']:
        value = True
    if value in ['disabled', 'no', 'false']:
        value = False
    return key, value


def convert_key_attribute(key):
    key = key.strip().lower()
    if not key:
        print('EMPTY KEY')
        return key
    for char in [' ', '-', ',', '/']:
        key = key.replace(char, '_')
    for char in ['.']:
        key = key.replace(char, '')
    if '(' in key:
        key = key.split('(')[0]
    if key[0].isnumeric():
        print(f"DEBUG 4: {key}")
        # some properties might have a number on first char
        key = '_' + key
    return key.strip()


def bytes_fmt(value):
    """Format a byte value human readable.

    Args:
        value (float): value of bytes
    Returns:
        str: formated value with unit
    """
    for unit in ['', 'K', 'M', 'G']:
        if abs(value) < 1024.0:
            return '{:3.2}f{}B'.format(value, unit)
        value /= 1024.0
    return '{:3.2}fTB'.format(value, 'G')


def get_properties(section):
    if type(section) == str:
        section = section.split('\n')
    props = {}
    sub_section = ''

    for line in section:
        if not line or line == '\n' or not line.replace('-', '') or not line.replace(' ', ''):
            continue
        if SEPARATOR_ATTRIBUTE not in line:
            sub_section = convert_key_attribute(line)

        if SEPARATOR_ATTRIBUTE in line:
            key, value = convert_attribute(line)
            if sub_section:
                if not props.get(sub_section, None):
                    props[sub_section] = {}
                props[sub_section][key] = value
            else:
                props[key] = value
    return props
