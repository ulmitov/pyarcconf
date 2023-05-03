"""Pyarcconf submodule, which provides a logical drive representing class."""

from . import parser
from .arcconf import Arcconf

SEPARATOR_SECTION = 64 * '-'


class PhysicalDrive():
    """Object which represents a physical drive."""

    def __init__(self, adapter_id, channel, device, arcconf=None):
        """Initialize a new LogicalDriveSegment object."""
        self.arcconf = arcconf or Arcconf()
        self.adapter_id = str(adapter_id)
        self.channel = str(channel).strip()
        self.device = str(device).strip()
        self.model = None
        self.disk_name = None
        #compliance with pystorcli
        self.serial = None

    def _execute(self, cmd, args=[]):
        """Execute a command using arcconf.

        Args:
            args (list):
        Returns:
            str: arcconf output
        Raises:
            RuntimeError: if command fails
        """
        if cmd == 'GETCONFIG':
            base_cmd = [cmd, self.adapter_id]
        else:
            base_cmd = [cmd, self.adapter_id, 'DEVICE', self.channel, self.device]
        return self.arcconf._execute(base_cmd + args)

    def __repr__(self):
        """Define a basic representation of the class object."""
        return 'Channel#{},Device#{}| {} {} {}'.format(
            self.channel, self.device, self.model, self.serial, self.disk_name
        )
    
    def init(self, config=''):
        if config and type(config) == list:
            config = '\n'.join(config)
        section = config or self._get_config()
        
        section = section.split(SEPARATOR_SECTION)
        for line in section[0].split('\n'):
            if parser.SEPARATOR_ATTRIBUTE in line:
                key, value = parser.convert_attribute(line)
                self.__setattr__(key, value)
        if len(section) == 1:
            return
        
        for idx in range(1, len(section), 2):
            props = parser.get_properties(section[idx + 1])
            if props:
                attr = parser.convert_key_attribute(section[idx])
                attr = attr.replace('device_', '')
                self.__setattr__(attr, props)

        self.serial = self.serial_number

    def _get_config(self):
        result = self._execute('GETCONFIG', ['PD', self.channel, self.device])[0]
        result = parser.cut_lines(result, 4)
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
            conf = self._get_config()
            lines = list(filter(None, conf.split('\n')))
            for line in lines:
                if line.strip().startswith('State'):
                    self.state = line.split(':')[1].strip().lower()
                    return True
        return False

    def set_cache(self, mode):
        """Set the cache for the physical drive.
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
            conf = self._get_config()
            lines = list(filter(None, conf.split('\n')))
            for line in lines:
                if line.strip().startswith('Write Cache'):
                    self.write_cache = line.split(':')[1].strip().lower()
                    return True
        return False

    @property
    def phyerrorcounters(self):
        result = self._execute('PHYERRORLOG')
        sata = 'SATA' in result
        result = parser.cut_lines(result, 16 if sata else 15)
        data = {}
        if not sata:
            for phy in result.split('\n\n'):
                if 'No device attached' in phy:
                    continue
                phy = phy.split('\n')
                _, phyid = parser.convert_attribute(phy[0])
                data[phyid] = {}
                for attr in phy[7:]:
                    key, value = parser.convert_attribute(attr)
                    data[phyid][key] = value
        return data
