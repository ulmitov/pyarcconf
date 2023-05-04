"""Python3 library for the arcconf tool."""
import logging
import subprocess

from . import parser

logger = logging.getLogger('pyArcconf')


class Arcconf():
    """Arcconf wrapper class."""

    def __init__(self, path=''):
        """Initialize a new Arcconf object.
        
        Args:
            path (str): path to arcconf binary
        """
        self.path = path or self._exec(['which', 'arcconf'])[0].split('\n')[0]
    
    def _exec(self, cmd):
        """Execute a command using arcconf.

        Args:
            cmd (list):
        Returns:
            str: arcconf output
        Raises:
            RuntimeError: if command fails
        """
        proc = subprocess.Popen(cmd,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        _stdout, _stderr = proc.communicate()
        if isinstance(_stdout, bytes):
            _stdout = _stdout.decode('utf8').strip()
            _stderr = _stderr.decode('utf8').strip()
        return _stdout, proc.returncode

    def _execute(self, cmd, args=[]):
        """Execute a command using arcconf.

        Args:
            args (list):
        Returns:
            str: arcconf output
        Raises:
            RuntimeError: if command fails
        """
        if type(cmd) == str:
            cmd = [cmd]
        out, rc = self._exec([self.path] + cmd + args)
        for arg in cmd + args:
            if '>' in arg:
                # out was redirected
                return out, rc
        out = out.split('\n')
        while out and not out[-1]:
            # remove empty lines in the end of out
            del out[-1]
        if 'Command completed successfully' not in out[-1]:
            logger.error(f'{cmd} {out[-1]}')
        del out[-1]
        while out and not out[-1]:
            # remove empty lines in the end of out
            del out[-1]
        return '\n'.join(out), rc

    def get_version(self):
        """Check the versions of all connected controllers.

        Returns:
            dict: controller with there version numbers for bios, firmware, etc.
        """
        versions = {}
        result = self._execute('GETVERSION')[0]
        result = parser.cut_lines(result, 1)
        for part in result.split('\n\n'):
            lines = part.split('\n')
            id_ = lines[0].split('#')[1]
            versions[id_] = {}
            for line in lines[2:]:
                key = line.split(':')[0].strip()
                value = line.split(':')[1].strip()
                versions[id_][key] = value
        return versions

    def list(self):
        """List all adapter by their ids.

        Returns:
            list: list of adapter ids
        """
        adapters = []
        result = self._execute('LIST')[0]
        result = parser.cut_lines(result, 6)
        for line in list(filter(None, result.split('\n'))):
            adapters.append(line.split(':')[0].strip().split()[1])
        return adapters

    def get_adapters(self):
        """Get all adapter objects for further interaction.

        Returns:
            list: list of adapter objects.
        """
        from common.pyarcconf.controller import Controller
        adapters = []
        for idx in self.list():
            adapters.append(Controller(idx, self))
        return adapters
