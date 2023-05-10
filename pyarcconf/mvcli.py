from . import runner


class MVCLI():
    """MVCLI wrapper class."""
    def __init__(self, cmdrunner=None):
        self.runner = cmdrunner or runner.CMDRunner()

    def _execute(self, cmd, args=None):
        """Execute a command using mvcli
        Args:
            args (list):
        Returns:
            str: arcconf output
        Raises:
            RuntimeError: if command fails
        """
        args = args or []
        if type(cmd) == str:
            cmd = [cmd]
        cmd = cmd + args
        cmd = f'(echo "{" ".join(cmd)}"; echo "exit") | {self.runner.path}'
        out, err, rc = self.runner.run(args=cmd, universal_newlines=True)
        if '>' in cmd:
            # out was redirected
            return out, rc
        out = out.split('\n')
        out = runner.cut_lines(out, 6)
        out = runner.sanitize_stdout(out, '> exit')
        if '(error ' in out[-1]:
            err = out[-1]
            rc = err.split('(error ')[1].split(runner.SEPARATOR_ATTRIBUTE)[0]
            out = ''
        else:
            rc = 0
            #out = runner.cut_lines(out, 6)
        return '\n'.join(out), rc

    def get_controllers(self):
        """Get all controller objects for further interaction.

        Returns:
            list: list of controller objects.
        """
        #from common.pyarcconf.controller import Controller
        result = self._execute('info -o hba')[0]
        #result = runner.cut_lines(result, 6)
        result = result.split('\n\n')
        controllers = []
        for info in result:
            controllers.append(Controller(info, self))
        return controllers




class Controller():
    """Object which represents an controller."""

    def __init__(self, info, cmdrunner=None):
        """Initialize a new controller object."""
        if type(info) == str and 'Adapter ID' in info:
            self.id = info.split('\n')[0].split(runner.SEPARATOR_ATTRIBUTE)[1]
        else:
            self.id = str(info)
            info = ''
        self.id = self.id.strip()
        self.runner = cmdrunner or MVCLI()
        self.mode = ''

        self._drives = []
        self.lds = []
        self.enclosures = []

        # pystorcli compliance
        self.facts = {}
        self.name = self.id

        self.update(info)

    def __repr__(self):
        """Define a basic representation of the class object."""
        return '<Controller{} | {} {}>'.format(
            self.id, self.mode, self.model
        )

    def _execute(self, cmd, args=[]):
        """Execute a command using arcconf.

        Args:
            args (list):
        Returns:
            str: arcconf output
        Raises:
            RuntimeError: if command fails
        """
        return self.runner._execute([cmd] + args)[0]

    @property
    def model(self):
        return getattr(self, 'product', '')

    @property
    def drives(self):
        if not self._drives:
            self._drives = self.get_pds()
        return self._drives

    @property
    def hba(self):
        """
        Return:
            bool: True if card is HBA
        """
        return not getattr(self, 'supported_raid_mode', '').upper()

    def update(self, info=''):
        """Parse controller info"""
        result = info or self._execute(f'info -o hba -i {self.id}')
        if not result:
            print('Command failed, aborting')
            return
        print(result)
        #result = runner.cut_lines(result, 4)
        section = list(filter(None, result.split('\n\n')))
        info = section[0]
        for line in info.split('\n'):
            if runner.SEPARATOR_ATTRIBUTE in line:
                key, value = runner.convert_property(line)
                self.__setattr__(key, value)
                
                # pystorcli compliance
                self.__setattr__(key.replace('controller_', ''), value)
                key = runner.convert_key_dict(line)
                # TODO: did not decide about naming, adding both. the second one is better for pystorcli
                self.facts[key] = value
                self.facts[key.replace('Controller ', '')] = value
                self.id = self.facts['Adapter ID']

        for idx in range(1, len(section), 2):
            if not section[idx].replace(' ', ''):
                print('NO SECTION') # TODO: remove it later
            attr = runner.convert_key_dict(section[idx])
            # pystorcli compliance
            attr = attr.replace('Information', '')
            attr = attr.replace('Controller', '').strip()
            if 'temperature sensors' in attr.lower():
                props = {}
                for sub_section in section[idx + 1].split('\n\n'):
                    sub_props = runner.get_properties(sub_section)
                    if sub_props:
                        props[sub_props['Sensor ID']] = sub_props
            else:
                props = runner.get_properties(section[idx + 1])
            if props:
                self.__setattr__(runner.convert_key_attribute(attr), props)
                # pystorcli compliance
                self.facts[attr] = props

        # TODO: remove it later
        print('print(self.facts):')
        print(self.facts)
