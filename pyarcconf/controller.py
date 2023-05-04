"""Pyarcconf submodule, which provides a raidcontroller representing Adapter class."""
import re

from . import parser
from .arcconf import Arcconf
from .enclosure import Enclosure
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

        self.raid_properties = {}
        self.versions = {}
        self.battery = {}

        # pystorcli compliance
        self.facts = {}
        self.name = self.id

        self.update()

    def __repr__(self):
        """Define a basic representation of the class object."""
        return '<{} | {} {} {}>'.format(
            self.id, self.mode, self.model, self.channel_description
        )

    def initialize(self):
        self.update()
        self.get_pds()
        self.get_lds()
        self.get_tasks()

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

    @property
    def drives(self):
        if not self._drives:
            self._drives = self.get_pds()
        return self._drives
    
    @property
    def expanders(self):
        """TODO: return expanders objects"""
        result = self._execute('EXPANDERLIST')
        if 'No expanders connected' in result:
            return []

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


        if self.mode.upper() == 'HBA':
            for idx in range(1, len(section), 2):
                if not section[idx].replace(' ', ''):
                    print('NO SECTION') # TODO: remove it later
                attr = parser.convert_key_dict(section[idx])
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
        else:
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
            options, _, segments = part.split(parser.SEPARATOR_SECTION)
            lines = list(filter(None, options.split('\n')))
            logid = lines[0].split()[-1]
            log_drive = LogicalDrive(self.id, logid, arcconf=self.arcconf)
            log_drive.update(lines)

            for line in list(filter(None, segments.split('\n'))):
                line = ':'.join(line.split(':')[1:])
                state = line.split()[0].strip()
                serial = line.split(')')[-1].strip()
                size, proto, type_, channel, port = line.split('(')[1].split(')')[0].split(',')
                channel = channel.split(':')[1]
                port = port.split(':')[1]
                log_drive.segments.append(LogicalDriveSegment(channel, port, state, serial, proto, type_))
            self.lds.append(log_drive)
        return self.lds

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
                print(part) # TODO: remove it later
                enc = Enclosure(self.id, channel, device, arcconf=self.arcconf)
                self.enclosures.append(enc)
                enc.update(lines)
                continue

            drive = PhysicalDrive(self.id, channel, device, arcconf=self.arcconf)
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
        result = self._execute('GETCONFIG', ['CN'])[0]
        result = parser.cut_lines(result, 4)
        for part in result.split('\n\n'):
            lines = part.split('\n')
            cnid = lines[0].split('#')[-1].strip()
            data[cnid] = {}
            for line in lines[1:]:
                key, value = parser.convert_property(line)
                data[cnid][key] = value
        return data
