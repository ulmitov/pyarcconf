from . import runner


class Array():
    """Object which represents an Array of logical\physical drives"""

    def __init__(self, controller_obj, id_):
        """Initialize a new object."""
        self.controller = controller_obj
        self.id = str(id_)

        # pystorcli compliance
        self.facts = {}

    def __repr__(self):
        """Define a basic representation of the class object."""
        return '<AR {} | {} {}>'.format(
            self.id,
            getattr(self, 'interface', ''),
            self.capacity
        )

    def _execute(self, cmd, args=[]):
        """Execute a command

        Args:
            args (list):
        Returns:
            str: output
        """
        if cmd.upper().strip() != 'GETCONFIG':
            args = ['ARRAY', self.id] + (args or [])
        return self.controller._exec(cmd, args)

    def _get_config(self):
        result = self._execute('GETCONFIG', ['AR', self.id])[0]
        result = runner.cut_lines(result, 4)
        return result

    def update(self, config=''):
        if config and type(config) == list:
            config = '\n'.join(config)
        section = config or self._get_config()
        section = section.split(runner.SEPARATOR_SECTION)
        for line in section[0].split('\n'):
            if runner.SEPARATOR_ATTRIBUTE in line:
                key, value = runner.convert_property(line)
                self.__setattr__(key, value)
                # pystorcli compliance
                key = runner.convert_key_dict(line)
                self.facts[key] = value
        # skipping other sections since they are parsed in self.drives and self.vds

    @property
    def drives(self):
        config = self._get_config()
        config = config.split(runner.SEPARATOR_SECTION)[-1]
        drives = []
        for line in config.split('\n'):
            if line:
                serial = line.split(')')[1].strip()
                # TODO: create new objects instead of getting them from the controller ?
                for d in self.controller.drives:
                    if serial == d.serial:
                        d.update()
                        drives.append(d)
        return drives
    
    # pysmart compliance
    @property
    def size(self):
        return getattr(self, 'total_size', '')
    
    # pysmart compliance
    @property
    def capacity(self):
        return runner.format_size(getattr(self, 'size', ''))

    @property
    def lds(self):
        return self.vds

    @property
    def vds(self):
        config = self._get_config()
        config = config.split(runner.SEPARATOR_SECTION)[-4]
        drives = []
        print(config)
        for line in config.split('\n'):
            if line:
                name = line.split(')')[1].strip()
                # TODO: create new objects instead of getting them from the controller ?
                for d in self.controller.get_vds():
                    if name == d.name:
                        d.update()
                        drives.append(d)
        return drives
