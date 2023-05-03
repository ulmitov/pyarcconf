"""Pyarcconf submodule, which provides a logical drive representing class."""

from .physical_drive import PhysicalDrive


class Enclosure(PhysicalDrive):
    """Object which represents a physical drive.
    Example:

       Channel #2:
      Device #3
         Device is an Enclosure Services Device
         Reported Channel,Device(T:L)       : 2,3(3:0)
         Enclosure ID                       : 0
         Enclosure Logical Identifier       : 50000D1704B53280
         Type                               : SES2
         Vendor                             : MSCC    
         Model                              : Virtual SGPIO
         Firmware                           : 1.32
         Status of Enclosure Services Device
            Speaker status                  : Not Available
    """
    pass

