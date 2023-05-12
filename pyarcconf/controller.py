import re

from . import runner
from .array import Array
from .enclosure import Enclosure
from .logical_drive import LogicalDrive
from .physical_drive import PhysicalDrive
from .task import Task


def get_controllers(arcconf_runner=None):
    """Get all controller objects for further interaction.
    Args:
        arcconf_runner: runner object
    Return:
        list: list of controller objects.
    """
    arcconf_runner = arcconf_runner or runner.CMDRunner()
    res = arcconf_runner.run([arcconf_runner.path, 'LIST'])[0]
    res = runner.sanitize_stdout(res, 'Command ')
    if not res:
        return []
    res = runner.cut_lines(res, 6)
    res = list(filter(None, res.split('\n')))
    ids = [line.split(':')[0].strip().split()[1] for line in res]
    return [Controller(i, arcconf_runner) for i in ids]


class Controller():
    """Object which represents a controller."""

    def __init__(self, controller_id, cmdrunner=None):
        """Initialize a new controller object."""
        self.id = str(controller_id)
        self.runner = cmdrunner or runner.CMDRunner()

        self._drives = []
        self.vds = []
        self.enclosures = []
        self.tasks = []

        # pystorcli compliance
        self.facts = {}
        self.name = self.id

        self.update()

    def __repr__(self):
        """Define a basic representation of the class object."""
        return '<Controller {} | {} {} {}>'.format(
            self.id,
            getattr(self, 'mode', ''),
            getattr(self, 'model', ''),
            getattr(self, 'channel_description', ''),
        )

    def _exec(self, cmd, args=None):
        """Generic Execute a command with runner
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
        out, err, rc = self.runner.run(args=[self.runner.path] + cmd + [self.id] + args, universal_newlines=True)
        if out:
            out = runner.sanitize_stdout(out, 'Command ')
        return out, rc

    def _execute(self, cmd, args=[]):
        """Execute a controller command

        Args:
            args (list):
        Return:
            str: output
        Raises:
            RuntimeError: if command fails
        """
        return self._exec(cmd, args)[0]

    def initialize(self):
        self.update()
        self.get_pds()
        self.get_vds()
        self.get_tasks()

    @property
    def drives(self):
        if not self._drives:
            self._drives = self.get_pds()
        return self._drives
    
    @property
    def expanders(self):
        """Get expander objects"""
        result = self._execute('EXPANDERLIST')
        if 'No expanders connected' in result:
            return []
        expanders = []
        _ = self.drives
        for e in self.enclosures:
            if 'Expander' in e.name:
                expanders.append(e)
        return expanders
    
    @property
    def hba(self):
        """
        Return:
            bool: True if card is HBA
        """
        return getattr(self, 'mode', '').upper() == 'HBA'

    @property
    def phyerrorcounters(self):
        result = self._execute('PHYERRORLOG')
        result = runner.cut_lines(result, 8)
        data = {}
        for phy in result.split('\n\n'):
            phy = phy.split('\n')
            _, phyid = runner.convert_property(phy[0])
            data[phyid] = {}
            for attr in phy[1:]:
                key, value = runner.convert_property(attr)
                data[phyid][key] = value
        return data

    @property
    def connectors(self):
        data = {}
        result = self._execute('GETCONFIG', ['CN'])
        result = runner.cut_lines(result, 4)
        for part in result.split('\n\n'):
            lines = part.split('\n')
            cnid = lines[0].split('#')[-1].strip()
            data[cnid] = {}
            for line in lines[1:]:
                key, value = runner.convert_property(line)
                data[cnid][key] = value
        return data

    def update(self):
        """Parse controller info"""
        result = self._execute('GETCONFIG', ['AD'])
        result = runner.cut_lines(result, 4)
        section = list(filter(None, result.split(runner.SEPARATOR_SECTION)))

        for line in section[0].split('\n'):
            if runner.SEPARATOR_ATTRIBUTE in line:
                key, value = runner.convert_property(line)
                self.__setattr__(key, value)
                
                # pystorcli compliance
                self.__setattr__(key.replace('controller_', ''), value)
                key = runner.convert_key_dict(line)
                # TODO: did not decide about naming, adding both. the second one is better for pystorcli
                self.facts[key] = value
                self.facts[key.replace('Controller ', '')] = value
        if len(section) == 1:
            return
        for idx in range(1, len(section), 2):
            if not section[idx].replace(' ', ''):
                print('NO SECTION') # TODO: this print is only for debug, did not see this case, remove it later
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

    @property
    def lds(self):
        return self.vds

    def get_lds(self):
        return self.get_vds()

    def get_vds(self):
        """Parse the info about logical drives."""
        result = self._execute('GETCONFIG', ['LD'])
        if 'not supported' in result:
            # HBA case
            return []
        if 'No logical devices configured' in result:
            return []
        self.vds = []
        result = runner.cut_lines(result, 4)
        for part in result.split('\n\n'):
            sections = part.split(runner.SEPARATOR_SECTION)
            options = sections[0]
            lines = list(filter(None, options.split('\n')))
            ldid = lines[0].split()[-1]
            ld = LogicalDrive(self, ldid)
            ld.update(lines)
            self.vds.append(ld)
        return self.vds
    
    def get_arrays(self):
        """Parse the info about drive arrays."""
        result = self._execute('GETCONFIG', ['AR'])
        if 'not supported' in result:
            # HBA case
            return []
        if 'No arrays configured' in result:
            return []
        self.arrays = []
        result = runner.cut_lines(result, 4)
        for part in result.split('\n\n'):
            sections = part.split(runner.SEPARATOR_SECTION)
            options = sections[0]
            lines = list(filter(None, options.split('\n')))
            ldid = lines[0].split()[-1]
            ld = Array(self, ldid)
            ld.update(lines)
            self.arrays.append(ld)
        return self.arrays

    def get_pds(self):
        """Parse the info about physical drives.
        """
        self._drives = []
        result = self._execute('GETCONFIG', ['PD'])
        result = runner.cut_lines(result, 4)
        result = re.split('.*Channel #\d+:', result)
        result = [re.split('.*Device #\d+\n', r) for r in result]
        result = [item for sublist in result for item in sublist]
        for part in result:
            lines = [l.strip() for l in part.split('\n')]
            lines = list(filter(None, lines))
            if not lines:
                continue
            for l in lines:
                if 'Channel,Device' in l:
                    channel, device = l.split(': ')[1].split('(')[0].split(',')

            if 'Device is a Hard drive' not in part:
                # this is an expander\enclosure case
                enc = Enclosure(self, channel, device)
                self.enclosures.append(enc)
                enc.update(lines)
                continue

            drive = PhysicalDrive(self, channel, device)
            drive.update(lines)
            self._drives.append(drive)
        return self._drives

    def get_tasks(self):
        """Parse the tasks."""
        result = self._execute('GETSTATUS')
        if 'Current operation              : None' in result:
            return []
        self.tasks = []
        result = runner.cut_lines(result, 1)
        for part in result.split('\n\n'):
            task = Task()
            for line in part.split('\n')[1:]:
                key, value = runner.convert_property(line)
                task.__setattr__(key, value)
            self.tasks.append(task)
        return self.tasks

    def get_logs(self, log_type='EVENT', args=None):
        """ GETLOGS command
        Args:
            log_type (str): One of: DEVICE,DEAD,EVENT,STATS,CACHE
            args (list): list of additional args
        Return:
            dict: dict of events
        """
        args = list(args) if args else []
        result = self._execute('GETLOGS', [log_type] + args)
        if 'not supported' in result:
            return {}
        result = ''.join(result.split('\n')[1:])
        import xml.etree.ElementTree as ET
        logs = ET.fromstring(result)
        ev = {}
        for child in logs:
            ev[child.tag] = child.attrib
        return ev

    def set_config(self):
        """Reset controller to default settings, removes all LDs"""
        result = self._execute('SETCONFIG', ['default'])
        return result

    def set_connector_mode(self, args):
        result = self._execute('SETCONNECTORMODE', args + ['noprompt'])
        return result

    def set_controller_mode(self, args):
        result = self._execute('SETCONTROLLERMODE', args + ['noprompt'])
        return result

    def set_stats_data_collection(self, enable=True):
        result = self._execute('SETSTATSDATACOLLECTION', ['Enable' if enable else 'Disable'])
        return result
    
    def set_cache(self, mode, args=None):
        """Set the cache for the drive.
        ARCCONF SETCACHE <Controller#> LOGICALDRIVE <LogicalDrive#> <logical mode> [noprompt] [nologs]
        ARCCONF SETCACHE <Controller#> DRIVEWRITECACHEPOLICY <DriveType> <CachePolicy> [noprompt] [nologs]
        ARCCONF SETCACHE <Controller#> CACHERATIO <read#> <write#>
        ARCCONF SETCACHE <Controller#> WAITFORCACHEROOM <enable | disable>
        ARCCONF SETCACHE <Controller#> NOBATTERYWRITECACHE <enable | disable>
        ARCCONF SETCACHE <Controller#> WRITECACHEBYPASSTHRESHOLD <threshold size>
        ARCCONF SETCACHE <Controller#> RECOVERCACHEMODULE

        Args:
            mode (str): setcache mode
            args (list): list of setcache args
        Returns:
            bool: True if success
        """
        args = [mode] + (args or [])
        result, rc = self._execute('SETCACHE', args)
        return not rc

    def create_ld(self, *args, **kwargs):
        return self.create_vd(*args, **kwargs)

    # pystorcli compliance
    def create_vd(self, name, raid, drives, strip: str = '64', size: str = 'MAX'):
        """
        Args:
            name (str): virtual drive name
            raid (str): virtual drive raid level (raid0, raid1, ...)
            drives (str): storcli drives expression (e:s|e:s-x|e:s-x,y;e:s-x,y,z)
            strip (str, optional): virtual drive raid strip size 16, 32, 64, 128, 256, 512 and 1024 are supported. The default is 128 KB
            size (str, optional): size of the logical drive in megabytes or MAX or MAXMBR (2TB)

        Returns:
            (None): no virtual drive created with name
            (:obj:virtualdrive.VirtualDrive)
        """
        args = ['logicaldrive']
        if name:
            args += ['Name', name]
        if strip:
            args += ['Stripesize', strip]
        args.append(size)
        args.append(str(raid).lower().replace('raid', ''))
        if type(drives) != str:
            if type(drives[0]) == str:
                # list of ['channel', 'device'] numbers
                drives = ' '.join(drives)
            else:
                # list of drive objects
                drv_list = []
                for d in drives:
                    drv_list += [d.channel, d.device]
                drives = ' '.join(drv_list)
        args.append(drives)
        result = self._execute('CREATE', args + ['noprompt'])
        if 'Command aborted' in result:
            #TODO: maybe return rc ?
            return None
        # TODO: if name is empty then we return None and user should find the vd by himself ?
        # but if name is a dup of other ld, then what? solution - find vd according to drives?
        for vd in self.get_vds():
            if vd.name == name:
                return vd
        print(self.vds)
        print([v.name for v in self.vds])

    def get_version(self):
        """Check the versions of all connected controllers.

        Returns:
            dict: controller with there version numbers for bios, firmware, etc.
        """
        versions = {}
        result = self._execute('GETVERSION')
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
        ids = self._execute('LIST')
        ids = runner.cut_lines(ids, 6)
        res = list(filter(None, res.split('\n')))
        ids = [line.split(':')[0].strip().split()[1] for line in res]
        return ids