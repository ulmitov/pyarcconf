from . import runner
from .arcconf import Arcconf

SEPARATOR_SECTION = 64 * '-'


class PhysicalDrive():
    """Object which represents a physical drive."""

    def __init__(self, controller_obj, channel, device, cmdrunner=None):
        """Initialize a new Drive object."""
        self.runner = cmdrunner or Arcconf()
        self.controller = controller_obj
        self.controller_id = str(controller_obj.id)
        self.channel = str(channel).strip()
        self.device = str(device).strip()

        # pystorcli compliance
        self.facts = {}

    def __repr__(self):
        """Define a basic representation of the class object."""
        return '<PD Channel #{},Device #{}| {}>'.format(
            self.channel,
            self.device,
            ' '.join([
                getattr(self, 'vendor', ''),
                getattr(self, 'model', ''),
                getattr(self, 'serial', ''),
                getattr(self, 'name', '')
            ])
        )
    
    def _execute(self, cmd, args=[]):
        """Execute a command

        Args:
            args (list):
        Returns:
            str: output
        Raises:
            RuntimeError: if command fails
        """
        if cmd == 'GETCONFIG':
            base_cmd = [cmd, self.controller_id]
        else:
            base_cmd = [cmd, self.controller_id, 'DEVICE', self.channel, self.device]
        return self.runner._execute(base_cmd + args)

    def update(self, config=''):
        if config and type(config) == list:
            config = '\n'.join(config)
        section = config or self._get_config()
        section = section.split(SEPARATOR_SECTION)
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

    def _get_config(self):
        result = self._execute('GETCONFIG', ['PD', self.channel, self.device])[0]
        result = runner.cut_lines(result, 4)
        return result

    def set_state(self, state):
        """Set the state for the physical drive.
        • HSP—Create a hot spare from a ready drive. Dedicates the HSP to one or more .
        • RDY—Remove a hot spare designation. Attempts to change a drive from Failed to Ready.
        • DDD—Force a drive offline (to Failed).
        • EED—Enable the erased drive.

        Args:
            state (str): new state
        Returns:
            bool: command result
        """
        result, rc = self._execute('SETSTATE', [state])
        if not rc:
            result = self._get_config()
            lines = list(filter(None, result.split('\n')))
            for line in lines:
                if line.strip().startswith('State'):
                    self.state = runner.convert_property(line)[1]
                    return True
        return False

    def set_cache(self, mode):
        """Set the cache for the drive.
        ARCCONF SETCACHE <Controller#> LOGICALDRIVE <LogicalDrive#> <logical mode> [noprompt] [nologs]
        ARCCONF SETCACHE <Controller#> DRIVEWRITECACHEPOLICY <DriveType> <CachePolicy> [noprompt] [nologs]
        ARCCONF SETCACHE <Controller#> CACHERATIO <read#> <write#>
        ARCCONF SETCACHE <Controller#> WAITFORCACHEROOM <enable | disable>
        ARCCONF SETCACHE <Controller#> NOBATTERYWRITECACHE <enable | disable>
        ARCCONF SETCACHE <Controller#> WRITECACHEBYPASSTHRESHOLD <threshold size>
        ARCCONF SETCACHE <Controller#> RECOVERCACHEMODULE

        Args:
            mode (str): new mode
        Returns:
            bool: command result
        """
        result, rc = self._execute('SETCACHE', [mode, 'noprompt'])
        if not rc:
            result = self._get_config()
            lines = list(filter(None, result.split('\n')))
            for line in lines:
                if line.split(runner.SEPARATOR_ATTRIBUTE)[0].strip() in['Write Cache']:
                    key, value = runner.convert_property(line)
                    self.__setattr__(key, value)
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
