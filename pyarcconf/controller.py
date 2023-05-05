"""Pyarcconf submodule, which provides a raidcontroller representing Adapter class."""
import re

from . import parser
from .arcconf import Arcconf
from .enclosure import Enclosure
from .array import Array
from .logical_drive import LogicalDrive, LogicalDriveSegment
from .physical_drive import PhysicalDrive
from .task import Task


class Controller():
    """Object which represents an adapter."""

    def __init__(self, adapter_id, arcconf=None):
        """Initialize a new Adapter object."""
        self.id = str(adapter_id)
        self.arcconf = arcconf or Arcconf()
        self.model = ''
        self.mode = ''
        self.channel_description = ''

        self._drives = []
        self.lds = []
        self.enclosures = []
        self.tasks = []

        #TODO: those really needed?
        self.raid_properties = {}
        self.versions = {}
        self.battery = {}

        # pystorcli compliance
        self.facts = {}
        self.name = self.id

        self.update()

    def __repr__(self):
        """Define a basic representation of the class object."""
        return '<Controller{} | {} {} {}>'.format(
            self.id, self.mode, self.model, self.channel_description
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
        return self.arcconf._execute([cmd, self.id] + args)[0]

    def initialize(self):
        self.update()
        self.get_pds()
        self.get_lds()
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
        result = parser.cut_lines(result, 8)
        data = {}
        for phy in result.split('\n\n'):
            phy = phy.split('\n')
            _, phyid = parser.convert_property(phy[0])
            data[phyid] = {}
            for attr in phy[1:]:
                key, value = parser.convert_property(attr)
                data[phyid][key] = value
        return data

    @property
    def connectors(self):
        data = {}
        result = self._execute('GETCONFIG', ['CN'])
        result = parser.cut_lines(result, 4)
        for part in result.split('\n\n'):
            lines = part.split('\n')
            cnid = lines[0].split('#')[-1].strip()
            data[cnid] = {}
            for line in lines[1:]:
                key, value = parser.convert_property(line)
                data[cnid][key] = value
        return data

    def update(self):
        """Parse adapter info"""
        result = self._execute('GETCONFIG', ['AD'])
        result = parser.cut_lines(result, 4)
        section = list(filter(None, result.split(parser.SEPARATOR_SECTION)))

        info = section[0]
        for line in info.split('\n'):
            if parser.SEPARATOR_ATTRIBUTE in line:
                key, value = parser.convert_property(line)

                if key == 'pci_address':
                    #changing from 0:d9:0:0 to lspci format 0:d9:00.0
                    value = value.replace(':0:', ':00:')
                    value = value.split(':')
                    value = ':'.join(value[:-1]) + '.' + value[-1]

                self.__setattr__(key, value)
                
                # pystorcli compliance
                self.__setattr__(key.replace('controller_', ''), value)
                key = parser.convert_key_dict(line)
                # TODO: did not decide about naming, adding both. the second one is better for pystorcli
                self.facts[key] = value
                self.facts[key.replace('Controller ', '')] = value

        for idx in range(1, len(section), 2):
            if not section[idx].replace(' ', ''):
                print('NO SECTION') # TODO: remove it later
            attr = parser.convert_key_dict(section[idx])
            # pystorcli compliance
            attr = attr.replace('Information', '')
            attr = attr.replace('Controller', '').strip()
            if 'temperature sensors' in attr.lower():
                props = {}
                for sub_section in section[idx + 1].split('\n\n'):
                    sub_props = parser.get_properties(sub_section)
                    if sub_props:
                        props[sub_props['Sensor ID']] = sub_props
            else:
                props = parser.get_properties(section[idx + 1])
            if props:
                self.__setattr__(parser.convert_key_attribute(attr), props)
                # pystorcli compliance
                self.facts[attr] = props

        if not self.hba:
            #TODO: original pyarcconf code, is it needed?
            raid_props = section[2]
            versions = section[4]
            battery = section[6]
            for line in raid_props.split('\n'):
                if parser.SEPARATOR_ATTRIBUTE in line:
                    key, value = parser.convert_property(line)
                    self.raid_properties[key] = value
            for line in versions.split('\n'):
                if parser.SEPARATOR_ATTRIBUTE in line:
                    key, value = parser.convert_property(line)
                    self.versions[key] = value
            for line in battery.split('\n'):
                if parser.SEPARATOR_ATTRIBUTE in line:
                    key, value = parser.convert_property(line)
                    self.battery[key] = value
        # TODO: remove it later
        print('print(self.facts):')
        print(self.facts)

    def get_lds(self):
        """Parse the info about logical drives."""
        result = self._execute('GETCONFIG', ['LD'])
        if 'not supported' in result:
            # HBA case
            return []
        if 'No logical devices configured' in result:
            return []
        self.lds = []
        result = parser.cut_lines(result, 4)
        for part in result.split('\n\n'):
            sections = part.split(parser.SEPARATOR_SECTION)
            options = sections[0]
            lines = list(filter(None, options.split('\n')))
            ldid = lines[0].split()[-1]
            ld = LogicalDrive(self, ldid, arcconf=self.arcconf)
            ld.update(lines)

            if 'Logical Device segment information' in part:
                segments = sections[-1]
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
                    ld.segments.append(LogicalDriveSegment(channel, slot, state, serial, protocol, type_, size, enclosure))
            self.lds.append(ld)
        return self.lds
    
    def get_arrays(self):
        """Parse the info about drive arrays."""
        result = self._execute('GETCONFIG', ['AR'])
        if 'not supported' in result:
            # HBA case
            return []
        if 'No arrays configured' in result:
            return []
        self.arrays = []
        result = parser.cut_lines(result, 4)
        for part in result.split('\n\n'):
            sections = part.split(parser.SEPARATOR_SECTION)
            options = sections[0]
            lines = list(filter(None, options.split('\n')))
            ldid = lines[0].split()[-1]
            ld = Array(self, ldid, arcconf=self.arcconf)
            ld.update(lines)
            self.arrays.append(ld)
        return self.arrays

    def get_pds(self):
        """Parse the info about physical drives.
        """
        self._drives = []
        result = self._execute('GETCONFIG', ['PD'])
        result = parser.cut_lines(result, 4)
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
                enc = Enclosure(self, channel, device, arcconf=self.arcconf)
                self.enclosures.append(enc)
                enc.update(lines)
                continue

            drive = PhysicalDrive(self, channel, device, arcconf=self.arcconf)
            drive.update(lines)
            self._drives.append(drive)
        return self._drives

    def get_tasks(self):
        """Parse the tasks."""
        result = self._execute('GETSTATUS')
        if 'Current operation              : None' in result:
            return []
        self.tasks = []
        result = parser.cut_lines(result, 1)
        for part in result.split('\n\n'):
            task = Task()
            for line in part.split('\n')[1:]:
                key, value = parser.convert_property(line)
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

    # pystorcli compliance
    def create_vd(self, *args, **kwargs):
        return self.create_ld(*args, **kwargs)

    def create_ld(self, name, raid, drives, strip: str = '64', size: str = 'MAX'):
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
        self._execute('CREATE', args + ['noprompt'])
        # TODO: if name is empty then we return None and user should find the vd by himself ?
        # but if name is a dup of other ld, then what? solution - find ld according to drives
        for ld in self.get_lds():
            if ld.logical_device_name == name:
                return ld
