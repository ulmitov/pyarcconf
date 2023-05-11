"""This code was tested with CLI Version: 4.1.13.31   RaidAPI Version: 5.0.13.1071
"""
from . import runner

SEPARATOR_SECTION = 25 * '-'


class MVCLI():
    """MVCLI wrapper class."""
    def __init__(self, cmdrunner=None):
        self.runner = cmdrunner or runner.CMDRunner()

    def _execute(self, cmd, args=None):
        """Execute a command
        Args:
            cmd: list or string of command to run
            args (list): list of args for the command
        Returns:
            str: command output
        """
        args = args or []
        if type(cmd) == str:
            cmd = [cmd]
        cmd = f'{self.runner.path} {" ".join(cmd + args)}'
        out, err, rc = self.runner.run(args=cmd, universal_newlines=True)
        if '>' in cmd:
            # out was redirected
            return out, rc
        out = out.split('\n')
        out = runner.cut_lines(out, 2)
        out = runner.sanitize_stdout(out)
        return '\n'.join(out), rc

    def get_controllers(self):
        """Get all controller objects for further interaction.

        Returns:
            list: list of controller objects.
        """
        #from common.pyarcconf.controller import Controller
        result = self._execute('info -o hba')[0]
        #result = runner.cut_lines(result, 6)
        result = result.split('\n\n')
        controllers = []
        for info in result:
            controllers.append(Controller(info, self))
        return controllers



class Drive():
    """Object which represents a physcial \ virtual drive."""

    def __init__(self, controller_obj, id_, cmdrunner=None):
        """Initialize a new Drive object."""
        self.runner = cmdrunner or MVCLI()
        self.controller = controller_obj
        self.controller_id = str(controller_obj.id)
        self.id = str(id_)
        self.size = None

        # pystorcli compliance
        self.facts = {}

    def __repr__(self):
        """Define a basic representation of the class object."""
        return f'<{"VD" if self.raid else "PD"} {self.id} | {self.raid} {self.size}>'

    def update(self, config):
        if config and type(config) == list:
            config = '\n'.join(config)
        section = config
        section = section.split(runner.SEPARATOR_SECTION)
        for line in section[0].split('\n'):
            if runner.SEPARATOR_ATTRIBUTE in line:
                key, value = runner.convert_property(line)
                self.__setattr__(key, value)
                # pystorcli compliance
                key = runner.convert_key_dict(line)
                self.facts[key] = value

    # pystorcli compliance
    @property
    def raid(self):
        return getattr(self, 'raid_mode', '')
    # pystorcli compliance
    @property
    def os_name(self):
        return 'TODO'


class Controller():
    """Object which represents a controller."""

    def __init__(self, info, cmdrunner=None):
        """Initialize a new controller object."""
        self.runner = cmdrunner or MVCLI()
        self.mode = ''
        self._drives = []

        # pystorcli compliance
        self.facts = {}

        if type(info) == str and 'Adapter ID' in info:
            self.id = info.split('Adapter ID')[1].split('\n')[0].split(runner.SEPARATOR_ATTRIBUTE)[1]
        elif type(info) != list:
            self.id = str(info)
            info = None
        self.id = self.id.strip()
        self.update(info)

        # Setting default adapter for the following CLI commands
        # (not mandatory, just in case host has several marvels)
        self._execute(f'adapter -i {self.id}')

    def __repr__(self):
        """Define a basic representation of the class object."""
        return '<Controller{} | {} {}>'.format(
            self.id, self.mode, self.model
        )

    def _execute(self, cmd, args=[], rc=False):
        """Execute a command using arcconf.

        Args:
            args (list):
        Returns:
            str: arcconf output
        Raises:
            RuntimeError: if command fails
        """
        result = self.runner._execute([cmd] + args)
        return (result[0], result[1]) if rc else result[0]

    @property
    def model(self):
        """
        Return:
            str: controller model
        """
        return getattr(self, 'product', '')

    @property
    def drives(self):
        """
        Return:
            list: list of physical drives
        """
        if not self._drives:
            self._drives = self.get_pds()
        return self._drives

    @property
    def vds(self):
        """
        Return:
            list: list of virtual drives
        """
        return self.get_vds()

    @property
    def hba(self):
        """
        Return:
            bool: True if card is HBA
        """
        return not getattr(self, 'supported_raid_mode', '').upper()

    def update(self, info=None):
        """Parse controller info
        Description:Display adapter(hba), virtual disk(vd), disk array,
        physical disk(pd), Port multiplexer(pm), expander(exp),
        block disk(blk) or spare drive information.

        info -o <hba|vd|pd|array|pm|exp|blk|spare|bbu> [-i <id>] [-h]

        Options:
            -o, --object <hba|vd|array|pd|pm|exp|blk|spare|bbu>
                Object name of the object to retrieve information from.
                hba - HBA (Adapter)
                vd  - Virtual Disk
                array  - disk array
                pd  - Physical Disk
                pm  - Port Multiplexer
                exp - Expander
                blk - Block Disk
                spare - Spare drives
                bbu - Battery Backup Unit
            -i, --id <id>
                Id of the object to retrieve info from. If not specified,
                info of all instances of the object will be retrieved.
            -h, --help

        Examples:
            info -o hba

            Information of all HBAs are retrieved.

            """
        result = info or self._execute(f'info -o hba -i {self.id}')
        if not result:
            print('Command failed, aborting')
            return

        section = list(filter(None, result.split('\n\n')))
        get_info = self._execute(f'get -o hba')
        info = section[0] + '\n' + get_info
        for line in info.split('\n'):
            if runner.SEPARATOR_ATTRIBUTE in line:
                key, value = runner.convert_property(line)
                self.__setattr__(key, value)
                
                # pystorcli compliance
                key = runner.convert_key_dict(line)
                self.facts[key] = value

        self.id = self.facts['Adapter ID']
        # pystorcli compliance
        self.name = self.id

    def get_pds(self):
        """Parse the info about physical drives.
        """
        self._drives = []
        result = self._execute('info -o pd')
        result = runner.cut_lines(result, 0, 3).split(SEPARATOR_SECTION)[1]
        result = result.split('\n\n')
        idx = 0
        for part in result:
            get_info = self._execute(f'get -o pd -i {idx}')
            drive = Drive(self, idx, cmdrunner=self.runner)
            drive.update(part + '\n' + get_info)
            self._drives.append(drive)
            idx += 1
        return self._drives
    
    def get_vds(self):
        """Parse the info about physical drives.
        """
        self._drives = []
        result = self._execute('info -o vd')
        result = runner.cut_lines(result, 0, 3).split(SEPARATOR_SECTION)[1]
        result = result.split('\n\n')
        idx = 0
        for part in result:
            get_info = self._execute(f'get -o vd -i {idx}')
            drive = Drive(self, idx, cmdrunner=self.runner)
            drive.update(part + '\n' + get_info)
            self._drives.append(drive)
            idx += 1
        return self._drives
    
    def get_events(self, sequence=0, once=False):
        """Description:Get the current events.
        event [-s <seqno>] --once


        Description: Get the current events.

        Options:
            -s, --seqno<seqno>
                to get events that sequence number larger than the seqno. 
            --once
                display event once by event sequence. after plug adapter please remove seq.txt
            -h, --help

        Examples:
            event -s 100

            Get events that sequence number larger than 100.
        """
        args = f' -s {sequence}' if sequence else ''
        args += ' --once' if once else ''
        result = self._execute('event' + args)
        result = runner.cut_lines(result, 1)
        result = result.split('\n\n')
        events = {}
        for part in result:
            part = runner.get_properties(part)
            events[part['Sequence']] = part
        return events

    def create_vd(self, name, raid, drives, strip: str = '64', size: str = 'MAX'):
        """
        create -o<vd> -d<PD id list> -r<0|1|10|5|1e>[-n <name>][-b <16|32|64|128>]
        [-c<on|off>][-i<quick|none>][-g<0|1|10>][--waiveconfirmation] [-h]
        Options:
            -o,  --object <vd>create virtual disk.
            -d, --pdid <PD id list> PD IDs used to create the VD, separated by commas.
            -r,  --raidmode <0|1|10|5|1e|hc|hs|hybrid>RAID level,
                Raid1E only for vanir, RAID hyper Duo only for Magni.
            -n, --name <VD name>(DEFAULT: Logical raid) - VD name. (max length is 11 chars)
            -b, --blocksize <16|32|64|128>(DEFAULT:64)stripe block size in KB unit.
                Can be one of 16, 32, 64 or 128.Only RAID0/1/10 can be 128.
            -c, --cache mode <on|off>(DEFAULT:on),Can be Cache On orCache Off.
            -i, --init <quick|none|intelligent> Initialization mode.(DEFAULT:quick)
                    intelligent only support on hyperduo/safe mode on win
            -g, --gbrounding <0|1|10> 0:0MB,1:1GB,10:10GB.(DEFAULT:0)
            Giga byte rounding scheme.Show size precision on MB/GB/10GB boundary.
            -h, --help
        Examples:
            create -o vd -r0 -d 0,2,4 -n "My VD" -b 32 -g 0
            Create a RAID 0 VD named 'My VD'  using disk 0, 2, 4. Stripe block size
            is 32 KB. 0GB rounding scheme is used.

        Args:
            name (str): virtual drive name
            raid (str): virtual drive raid level (raid0, raid1, ...)
            drives (str): storcli drives expression (e:s|e:s-x|e:s-x,y;e:s-x,y,z)
            strip (str, optional): <16|32|64|128>(DEFAULT:64)stripe block size in KB unit.
            Can be one of 16, 32, 64 or 128.Only RAID0/1/10 can be 128.
            size (str, optional): size of the logical drive in megabytes or MAX or MAXMBR (2TB)

        Returns:
            (None): no virtual drive created with name
            (:obj:virtualdrive.VirtualDrive)
        """
        args = ['create', '-o', 'vd']
        if name:
            args += ['-n', f'"{name}"']
        if strip:
            args += ['-b', strip]
        args += ['-r', str(raid).lower().replace('raid', '')]
        if type(drives) != str:
            if type(drives[0]) in [str, int]:
                # list of ids
                drives = ' '.join(drives)
            else:
                # list of drive objects
                drv_list = []
                for d in drives:
                    drv_list += [d.id]
                drives = ','.join(drv_list)
        args += ['-d', drives]
        args.append('--waiveconfirmation')
        _, rc = self._execute(args, rc=True)
        if rc:
            print(f'create {args} command failed')
            return
        # TODO: if name is empty then we return None and user should find the vd by himself ?
        # but if name is a dup of other ld, then what? solution - find ld according to drives
        for vd in self.get_vds():
            if vd.name == name[:11]:
                return vd

    def set(self, args):
        """Description:Set configuration parameters of VD, PD or HBA.
        set -o vd -i <VD id> [-n <new name>]
            [<--cacheon|--cacheoff>] [<--clear>] [-h]

        set -o <pd> -i <PD id> [<--cacheon|--cacheoff>] [-h]

        set -o hba
            [<--clear>] [-r <BGA rate>]
        set -o link -i <VD id> -d <PD id>  [-h]

        Options:
            -o, --object <vd|pd|hba>
                Configure VD, PD or HBA.
            -i, --id <VD id|PD id>
                Virtual Disk id, Physical Disk id.
            -n, --name <new name>
                If blank character is in the name, <new name> has to be quoted.
                To delete the name, set <new name> to .
            -r, --bgarate <rate>
                BGA rate - a number between 0 and 100
            -h, --help

        Examples:
            set -o vd -i 2 --cacheon

            Enable cache on VD 2.
        """
        result = self._execute('set' + args)
        return result
