"""Python3 library for the arcconf tool.

https://download.adaptec.com/pdfs/user_guides/adaptec_cli_smarthba_smartraid_7_21_ug.pdf
https://download.adaptec.com/pdfs/user_guides/microsemi_cli_smarthba_smartraid_v3_00_23484_ug.pdf
http://download.adaptec.com/pdfs/user_guides/cli_arc_v2_02_22404_users_guide.pdf

old versions outputs:
https://www.lcg.triumf.ca/files/recipes/65/procedure.txt


troubleshoot:
https://www.ibm.com/support/pages/diagnosing-bad-stripes-mt-7979-host-puredata-system-analytics-n1001
https://wiki.miko.ru/kb:sysadm:arcconf

"""
from . import runner


class Arcconf():
    """Arcconf wrapper class."""
    def __init__(self, cmdrunner=None):
        self.runner = cmdrunner or runner.CMDRunner()

    def _execute(self, cmd, args=None):
        """Execute a command
        Return codes:
        0x00: SUCCESS
        0x01: FAILURE - The requested command failed
        0x02: ABORT - The command was aborted because parameters failed validation
        0x03: INVALID_ARGUMENTS - The arguments are incorrect. (Displays COMMAND help)
        0x06: INVALID_CARD_NUM - Unable to find the specified controller ID
        Args:
            args (list):
        Returns:
            str: output
        Raises:
            RuntimeError: if command fails
        """
        args = args or []
        if type(cmd) == str:
            cmd = [cmd]
        out, err, rc = self.runner.run(args=[self.runner.path] + cmd + args, universal_newlines=True)
        for arg in cmd + args:
            if '>' in arg:
                # out was redirected
                return out, rc
        out = runner.sanitize_stdout(out, 'Command ')
        return out, rc

    def get_version(self):
        """Check the versions of all connected controllers.

        Returns:
            dict: controller with there version numbers for bios, firmware, etc.
        """
        versions = {}
        result = self._execute('GETVERSION')[0]
        result = runner.cut_lines(result, 1)
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
        """List all controllers by their ids.

        Returns:
            list: list of controller ids
        """
        controllers = []
        result = self._execute('LIST')[0]
        result = runner.cut_lines(result, 6)
        for line in list(filter(None, result.split('\n'))):
            controllers.append(line.split(':')[0].strip().split()[1])
        return controllers

    def get_controllers(self):
        """Get all controller objects for further interaction.

        Returns:
            list: list of controller objects.
        """
        from common.pyarcconf.controller import Controller
        controllers = []
        for idx in self.list():
            controllers.append(Controller(idx, self))
        return controllers
