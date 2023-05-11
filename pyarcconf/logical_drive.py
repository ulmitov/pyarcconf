from . import runner
from .arcconf import Arcconf
from .physical_drive import PhysicalDrive


class LogicalDrive():
    """Object which represents a logical drive."""

    def __init__(self, controller_obj, id_, cmdrunner=None):
        """Initialize a new LogicalDrive object."""
        self.runner = cmdrunner or Arcconf()
        self.controller = controller_obj
        self.controller_id = str(controller_obj.id)
        self.id = str(id_)
        self.size = None

        # pystorcli compliance
        self.facts = {}

    def __repr__(self):
        """Define a basic representation of the class object."""
        return '<LD {} | Raid:{} {}>'.format(self.id, self.raid, self.size)

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
            base_cmd = [cmd, self.controller_id, 'LOGICALDRIVE', self.id]
        return self.runner._execute(base_cmd + args)

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

    def _get_config(self):
        result = self._execute('GETCONFIG', ['LD', self.id])[0]
        result = runner.cut_lines(result, 4)
        return result

    # pystorcli compliance
    @property
    def raid(self):
        return getattr(self, 'raid_level', '')
    # pystorcli compliance
    @property
    def os_name(self):
        return getattr(self, 'disk_name', '')

    @property
    def drives(self):
        config = self._get_config()
        config = config.split(runner.SEPARATOR_SECTION)[-1]
        drives = []
        for line in config.split('\n'):
            if not line:
                continue
            serial = line.split(')')[1].strip()
            # TODO: create new objects instead of getting them from the controller ?
            for d in self.controller.drives:
                if serial == d.serial:
                    d.update()
                    drives.append(d)
        return drives

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

    def set_state(self, state='OPTIMAL'):
        """Set the state for the logical drive:

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
                if line.strip().startswith('Status'):
                    self.status_of_logical_device = runner.convert_property(line)[1]
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
                if line.split(runner.SEPARATOR_ATTRIBUTE)[0].strip() in ['Read-cache', 'Write-cache']:
                    key, value = runner.convert_property(line)
                    self.__setattr__(key, value)
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
