"""Pyarcconf submodule, which provides a logical drive representing class."""

from . import parser
from .arcconf import Arcconf


class LogicalDrive():
    """Object which represents a logical drive."""

    def __init__(self, adapter_id, id_, arcconf=None):
        """Initialize a new LogicalDrive object."""
        self.arcconf = arcconf or Arcconf()
        self.adapter_id = str(adapter_id)
        self.id_ = str(id_)
        self.logical_drive_name = None
        self.raid_level = None
        self.status_of_logical_drive = None
        self.size = None
        self.read_cache_mode = None
        self.write_cache_mode = None
        self.write_cache_setting = None
        self.partitioned = None
        self.protected_by_hot_spare = None
        self.bootable = None
        self.failed_stripes = None
        self.power_settings = None
        self.segments = []

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
            base_cmd = [cmd, self.adapter_id, 'LOGICALDRIVE', self.id_]
        return self.arcconf._execute(base_cmd + args)

    def __repr__(self):
        """Define a basic representation of the class object."""
        return 'LD {} | {} {} {} {}'.format(
            self.id_,
            self.logical_drive_name,
            self.raid_level,
            self.status_of_logical_drive,
            self.size
        )

    def update(self, config=''):
        config = config or self._get_config().split('\n')
        for line in config:
            if parser.SEPARATOR_ATTRIBUTE in line:
                key, value = parser.convert_property(line)
                self.__setattr__(key, value)

    def _get_config(self):
        result = self._execute('GETCONFIG', ['LD', self.channel, self.device])[0]
        result = parser.cut_lines(result, 4)
        return result

    def set_name(self, name):
        """Set the name for the logical drive.

        Args:
            name (str): new name
        Returns:
            bool: command result
        """
        result, rc = self._execute('SETNAME', [name])
        if not rc:
            result = self._execute('GETCONFIG', ['LD', self.id_])
            result = parser.cut_lines(result, 4)
            for line in result.split('\n'):
                if line.strip().startswith('Logical Device Name'):
                    self.logical_device_name = line.split(':')[1].strip().lower()
            return True
        return False

    def set_state(self, state):
        """Set the state for the logical drive.

        Args:
            state (str): new state
        Returns:
            bool: command result
        """
        result, rc = self._execute('SETSTATE', [state])
        if not rc:
            result = self._execute('GETCONFIG', ['LD', self.id_])
            result = parser.cut_lines(result, 4)
            for line in result.split('\n'):
                if line.strip().startswith('Status'):
                    self.status_of_logical_device = line.split(':')[1].strip().lower()
            return True
        return False

    def set_cache(self, mode):
        """Set the cache for the logical drive.
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
        result, rc = self._execute('SETCACHE', [mode])
        if not rc:
            result = self._execute('GETCONFIG', ['LD', self.id_])
            result = parser.cut_lines(result, 4)
            for line in result.split('\n'):
                if line.split(':')[0].strip() in ['Read-cache', 'Write-cache']:
                    key, value = parser.convert_property(line)
                    self.__setattr__(key, value)
            return True
        return False


class LogicalDriveSegment():
    """Object which represents a logical drive segment."""

    def __init__(self, channel, port, state, serial, proto, type_):
        """Initialize a new PhysicalDrive object."""
        self.channel = channel
        self.port = port
        self.state = state
        self.serial = serial
        self.proto = proto
        self.type_ = type_

    def __str__(self):
        """Build a string formatted object representation."""
        return '{},{} {} {}'.format(self.channel, self.port, self.state, self.serial)
