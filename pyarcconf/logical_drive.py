from . import runner


class LogicalDrive():
    """Object which represents a logical drive."""

    def __init__(self, controller_obj, id_):
        """Initialize a new object."""
        self.controller = controller_obj
        self.id = str(id_)
        self.segments = []

        # pystorcli compliance
        self.facts = {}

    def __repr__(self):
        """Define a basic representation of the class object."""
        return '<LD {} | {} {} Segments: {}>'.format(self.id, self.raid, self.capacity, self.segments)

    def _execute(self, cmd, args=[]):
        """Execute a command

        Args:
            args (list):
        Returns:
            str: output
        """
        if cmd.upper().strip() != 'GETCONFIG':
            args = ['LOGICALDRIVE', self.id] + (args or [])
        return self.controller._exec(cmd, args)

    def _get_config(self):
        result = self._execute('GETCONFIG', ['LD', self.id])[0]
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
        if len(section) == 1:
            return
        self.segments = []
        for idx in range(1, len(section), 1):
            header = section[idx]
            if 'Logical Device segment information' not in header:
                continue
            # skipping other sections since they are parsed in self.drives
            segments = section[idx + 1]
            for line in list(filter(None, segments.split('\n'))):
                line = ':'.join(line.split(':')[1:])
                state = line.split()[0].strip()
                serial = line.split(')')[-1].strip()
                props = line.split('(')[1].split(')')[0].split(',')
                if len(props) == 5:
                    enclosure = None
                    size, protocol, type_, channel, slot = props
                else:
                    size, protocol, type_, channel, enclosure, slot = props
                channel = channel.split(':')[1]
                slot = slot.split(':')[1]
                self.segments.append(LogicalDriveSegment(channel, slot, state, serial, protocol, type_, size, enclosure))

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

    # pystorcli compliance
    @property
    def name(self):
        return getattr(self, 'logical_device_name', '')
    
    # pystorcli compliance
    @property
    def raid(self):
        level = getattr(self, 'raid_level', '')
        if level:
            level = f'raid{level}'
        return level
    
    # pystorcli compliance
    @property
    def os_name(self):
        return getattr(self, 'disk_name', '')

    # pysmart compliance
    @property
    def capacity(self):
        return runner.format_size(getattr(self, 'size', ''))

    def set_name(self, name):
        """Set the name for the logical drive.

        Args:
            name (str): new name
        Returns:
            bool: command result
        """
        result, rc = self._execute('SETNAME', [name])
        if not rc:
            result = self._execute('GETCONFIG', ['LD', self.id])
            result = runner.cut_lines(result, 4)
            for line in result.split('\n'):
                if line.strip().startswith('Logical Device Name'):
                    self.logical_device_name = runner.convert_property(line)[1]
            return True
        return False

    def set_state(self, state='OPTIMAL', args=None):
        """Set the state for the logical drive:

        ARCCONF SETSTATE <Controller#> LOGICALDRIVE <LD#> OPTIMAL [ADVANCED <option>] [noprompt]
        [nologs]

        Args:
            state (str): new state
        Returns:
            bool: command result
        """
        result, rc = self._execute('SETSTATE', [state] + (args or []))
        if not rc:
            result = self._get_config()
            lines = list(filter(None, result.split('\n')))
            for line in lines:
                if line.strip().startswith('Status'):
                    self.status_of_logical_device = runner.convert_property(line)[1]
            return True
        return False


class LogicalDriveSegment():
    """Object which represents a logical drive segment."""

    def __init__(self, channel, port, state, serial, protocol, type_, size, enclosure=None):
        """Initialize a new PhysicalDrive object."""
        self.channel = channel
        self.port = port
        self.state = state
        self.serial = serial
        self.protocol = protocol
        self.type = type_
        self.size = size
        self.enclosure = enclosure

    def __repr__(self):
        """Build a string formatted object representation."""
        return '<LD segment {},{} {} {}>'.format(self.channel, self.port, self.state, self.serial)
