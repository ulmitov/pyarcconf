from . import runner

SEPARATOR_SECTION = 64 * '-'


class PhysicalDrive():
    """Object which represents a physical drive."""

    def __init__(self, controller_obj, channel, device):
        """Initialize a new object."""
        self.controller = controller_obj
        self.channel = str(channel).strip()
        self.device = str(device).strip()

        # pystorcli compliance
        self.facts = {}

    def __repr__(self):
        """Define a basic representation of the class object."""
        return '<PD Channel #{}, Device #{} | {}>'.format(
            self.channel,
            self.device,
            ' '.join([
                getattr(self, 'vendor', ''),
                getattr(self, 'model', ''),
                self.serial,
                self.name,
                self.capacity
            ])
        )
    
    def _execute(self, cmd, args=[]):
        """Execute a command

        Args:
            args (list):
        Returns:
            str: output
        """
        if cmd.upper().strip() != 'GETCONFIG':
            args = ['DEVICE', self.channel, self.device] + (args or [])
        return self.controller._exec(cmd, args)

    def _get_config(self):
        result = self._execute('GETCONFIG', ['PD', self.channel, self.device])[0]
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
        for idx in range(1, len(section), 2):
            props = runner.get_properties(section[idx + 1])
            if props:
                attr = runner.convert_key_attribute(section[idx])
                # pystorcli compliance
                attr = attr.replace('device_', '')
                self.__setattr__(attr, props)
                key = runner.convert_key_dict(section[idx])
                self.facts[key] = props

    # pystorcli compliance
    @property
    def encl_id(self):
        return getattr(self, 'raid_level', '')

    # pysmart compliance
    @property
    def serial(self):
        return getattr(self, 'serial_number', '')

    # pysmart compliance
    @property
    def name(self):
        return getattr(self, 'disk_name', '').replace('/dev/', '').replace('nvd', 'nvme')

    # pysmart compliance
    @property
    def size(self):
        return getattr(self, 'total_size', '')

    # pysmart compliance
    @property
    def capacity(self):
        return runner.format_size(getattr(self, 'size', ''))

    def set_state(self, state, args=None):
        """Set the state for the physical drive.

        ARCCONF SETSTATE <Controller#> DEVICE <Channel#> <Device#> <State> [ARRAY <AR#> [AR#] ... ]
        [SPARETYPE <TYPE>][noprompt] [nologs]
        ARCCONF SETSTATE <Controller#> LOGICALDRIVE <LD#> OPTIMAL [ADVANCED <option>] [noprompt]
        [nologs]
        ARCCONF SETSTATE <Controller#> MAXCACHE <LD#> OPTIMAL [noprompt] [nologs]

        • HSP—Create a hot spare from a ready drive. Dedicates the HSP to one or more .
        • RDY—Remove a hot spare designation. Attempts to change a drive from Failed to Ready.
        • DDD—Force a drive offline (to Failed).
        • EED—Enable the erased drive.

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
                if line.strip().startswith('State'):
                    self.state = runner.convert_property(line)[1]
                    return True
        return False

    @property
    def phyerrorcounters(self):
        result, rc = self._execute('PHYERRORLOG')
        if rc == 2:
            return {}
        sata = 'SATA' in result
        result = runner.cut_lines(result, 16 if sata else 15)
        data = {}
        #TODO: add sata logic
        if not sata:
            for phy in result.split('\n\n'):
                if 'No device attached' in phy:
                    continue
                phy = phy.split('\n')
                _, phyid = runner.convert_property(phy[0])
                data[phyid] = {}
                for attr in phy[7:]:
                    key, value = runner.convert_property(attr)
                    data[phyid][key] = value
        return data
