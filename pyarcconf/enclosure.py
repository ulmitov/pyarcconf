"""Enclosure\Expander class"""

from .physical_drive import PhysicalDrive


class Enclosure(PhysicalDrive):
   """Object represents a physical enclosure\expander

      Example:
   HBA:
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

   RAID with expander:
      Device is an Enclosure Services Device
      Reported Channel,Device(T:L)         : 2,0(0:0)
      Reported Location                    : Connector 0:CN0, Enclosure 1
      Enclosure ID                         : 1
      Enclosure Logical Identifier         : 500E004A00E2003E
      Expander ID                          : 0
      Expander SAS Address                 : 500E004A00E2003F
      SEP device ID                        : 377
      Type                                 : SES2
      Vendor                               : VENDOR_XXXXXX
      Model                                : PRODUCT_XXXXX
      Firmware                             : 
      Status of Enclosure Services Device
         Temperature Sensor Status 1       : 35 C/ 95 F (Normal)
         Speaker status                    : Not Available

      Device is an Enclosure Services Device
      Reported Channel,Device(T:L)         : 2,1(1:0)
      Enclosure Logical Identifier         : 50000D1E012F1A88
      Type                                 : SES2
      Vendor                               : Adaptec 
      Model                                : Virtual SGPIO
      Firmware                             : 0102
      Status of Enclosure Services Device
         Speaker status                    : Not Available
   """
   #TODO: this method is not really needed for now
   def _execute(self, cmd, args=[]):
      """Execute a command

      Args:
         args (list):
      Returns:
         str: output
      Raises:
         RuntimeError: if command fails
      """
      result, rc = super()._execute(cmd, args)
      if 'Device is not a hard drive. Aborting' in result:
         return '', rc
      return result, rc

   # pysmart compliance
   @property
   def name(self):
      return 'Expander' if hasattr(self, 'expander_id') else 'Enclosure'
