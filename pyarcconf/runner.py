"""Command execute and output parse methods"""
import os
import re
import shutil
from subprocess import Popen, PIPE

SEPARATOR_ATTRIBUTE = ': '
SEPARATOR_SECTION = 56 * '-'


class CMDRunner():
    """This is a simple wrapper for subprocess.Popen()/subprocess.run(). The main idea is to inherit this class and create easy mockable tests.
    """
    def __init__(self, path=''):
        """Initialize a new MVCLI object.
        
        Args:
            path (str): path to mvcli binary
        """
        self.path = self.binaryCheck(path)
    
    def run(self, args, **kwargs):
        """Runs a command and returns the output.
        """
        proc = Popen(args, stdout=PIPE, stderr=PIPE, **kwargs)

        _stdout, _stderr = [i.decode('utf8') for i in proc.communicate()]

        return _stdout, _stderr, proc.returncode

    def binaryCheck(self, binary) -> str:
        """Verify and return full binary path
        """
        _bin = shutil.which(binary)
        if not _bin:
            raise Exception(
                "Cannot find storcli binary '%s'" % (binary))
        return _bin


def cut_lines(output, start, end=0):
    """Cut a number of lines from the start and the end.

    Args:
        output (str|list): command output from arcconf
        start (int): offset from start
        end (int): offset from end
    Returns:
        str|list: cutted output
    """
    islist = type(output) == list
    if not islist:
        output = output.split('\n')
    output = output[start:len(output) - end]
    return output if islist else '\n'.join(output)


def sanitize_stdout(output, last_line=''):
    """Remove blank lines from end of output,
    including a specific last_line if given

    Args:
        output (str): comand output
        last_line (str): a line that supposed to be in the end of output
    Return:
        str: command output up to last line, without blank lines in the end
    """
    islist = type(output) == list
    output = output if islist else output.split('\n')
    while output and not output[-1]:
        del output[-1]
    if not output:
        return [] if islist else ''
    if last_line and last_line in output[-1]:
        del output[-1]
    while output and not output[-1]:
        del output[-1]
    return output if islist else '\n'.join(output)


def convert_property(key, value=None):
    """Convert an attribute into the most pratical datatype.

    Args:
        key (str): attribute key
        value (str): attribute value
    Returns:
        str, bool: key, value pair
        str, str: formated key, value pair
    """
    if not value:
        if SEPARATOR_ATTRIBUTE not in key:
            print(f'ERROR: {key} is not a property')
            return
        key, value = key.split(SEPARATOR_ATTRIBUTE)
    key = convert_key_attribute(key)
    value = convert_value_attribute(value)
    return key, value


def convert_value_attribute(value):
    """Convert a string to class attribute value"""
    if len(value.split()) == 2:
        size, unit = value.split()
        if size.isdigit() and unit in ['B', 'KB', 'MB', 'GB']:
            return bytes_fmt(size)
    value = value.strip()
    if value.lower() in ['enabled', 'yes', 'true']:
        value = True
    elif value.lower() in ['disabled', 'no', 'false']:
        value = False
    return value


def convert_key_attribute(key):
    """Convert a string to class attribute"""
    if '(' in key:
        key = key.split('(')[0]
    key = key.strip().lower()
    if not key:
        print('EMPTY KEY')
        return key
    for char in [' ', '-', ',', '/']:
        key = key.replace(char, '_')
    if key[0].isnumeric():
        # first char might be a number
        key = '_' + key
    # clear special chars
    key = re.sub('[^a-zA-Z0-9\_]', '', key)
    return key.strip()


def convert_key_dict(line):
    """Convert a string to dict key"""
    # clear from garbage
    for key in line.split('\n'):
        if key.replace('-', ''):
            line = key
            break
    key = line.split(SEPARATOR_ATTRIBUTE)[0]
    if '(' in key:
        key = key.split('(')[0]
    key = key.strip()
    if not key:
        print(f'EMPTY KEY: {line}')
    return key


def bytes_fmt(value):
    """Format a byte value human readable.

    Args:
        value (float): value of bytes
    Returns:
        str: formated value with unit
    """
    value = float(value)
    for unit in ['', 'K', 'M', 'G']:
        if abs(value) < 1024.0:
            return '{:3.2}f{}B'.format(value, unit)
        value /= 1024.0
    return '{:3.2}fTB'.format(value, 'G')


def get_properties(section):
    """Build a dict of properties"""
    if type(section) == str:
        section = section.split('\n')
    props = {}
    sub_section = ''

    for line in section:
        if not line or line == '\n' or not line.replace('-', '') or not line.replace(' ', ''):
            continue
        if SEPARATOR_ATTRIBUTE not in line:
            sub_section = convert_key_dict(line)

        if SEPARATOR_ATTRIBUTE in line:
            key, value = line.split(SEPARATOR_ATTRIBUTE)
            key = convert_key_dict(key)
            value = convert_value_attribute(value)
            if sub_section:
                if not props.get(sub_section, None):
                    props[sub_section] = {}
                props[sub_section][key] = value
            else:
                props[key] = value
    return props
