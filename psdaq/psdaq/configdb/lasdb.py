#!/usr/bin/env python

import configparser
from psalg.configdb.typed_json import cdict
from psalg.configdb.configdb import configdb as cdb

class Assembly(object):
    """
    Class for handling 'assemblies' that are part of TILEs in the laser
    configuration database. Examples of 'assemblies' are Tuttifruttis, zoom
    telescopes. Assemblies are composed of devices such as  cameras, 
    spectrometers, etc.
    """
    def __init__(self, configdb, hutch, alias, device):
        self._cdb = configdb
        self._hutch = hutch
        self._alias = alias
        self._device = device
        self._base = self.get_current_config()['COMMON']['BASE']

    def get_base_pv(self):
        """
        Method for retrieving the current base PV of the assembly. 
        """
        self._base = self.get_current_config()['COMMON']['BASE']

        return self._base

    def get_current_config(self):
        """
        Method for retrieving the current configuration of the assembly. 
        Returns a typed JSON object containing the configuration.
        """
        cfg = self._cdb.get_configuration(self._alias, self._device, 
                                                            hutch=self._hutch) 

        return cfg

    def set_current_config(self, new_cfg):
        """
        Method for updating the current configuration of the assembly. Replaces
        the old configuration with the new one.
        """

        self._cdb.modify_device(self._alias, new_cfg, hutch=self._hutch)

    def get_iocs(self):
        """
        Get a list  of IOCs/devices contained within the assembly.
        """
        cfg = self.get_current_config()
        keys = list(cfg.keys())
        not_iocs = ['detType:RO', 'detName:RO', 'COMMON', ':types:']
        iocs = [key for key in keys if key not in not_iocs]

        return iocs

    def get_ioc_config(self, ioc):
        """
        Return a dictionary containing the data for the configuration of the
        requested IOC. Includes IOC configuration and parameter information.
        """
        iocs = self.get_iocs()

        if ioc not in iocs:
            raise ValueError("Unrecognized IOC {}.".format(ioc))

        cfg = self.get_current_config()
        ioc_data = cfg[ioc] 

        return ioc_data

    def set_ioc_config(self, ioc, new_ioc_cfg):
        """
        Update the configuration of the specified IOC with the given
        configuration.
        """
        iocs = self.get_iocs()

        if ioc not in iocs:
            raise ValueError("Unrecognized IOC {}.".format(ioc))

        # Test for ioc level config sections
        #TODO: Change this to only update config from relevant sections in
        #      provided config
        if all (key in new_ioc_cfg for key in ('IOC','CONFIG')):
            cfg = self.get_current_config() # Whole assmbly config
            cfg[ioc] = new_ioc_cfg # Modify just the requested ioc
            
            self.set_current_cfg(cfg)
        else:
            raise ValueError("Missing IOC configuration sections.")

    def get_ioc_parameters(self, ioc):
        """
        Return a dictionary containing the data for the operating parameters of 
        the requested IOC from the current configuration.
        """
        iocs = self.get_iocs()

        if ioc not in iocs:
            raise ValueError("Unrecognized IOC {}.".format(ioc))

        cfg = self.get_ioc_config(ioc)
        ioc_param_data = cfg['CONFIG'] # A dict of dicts

        return ioc_param_data 

    def _unpack_pv_dict(self, basepv, params, out_dict):
        # Recursively unpack parameter data, flatten into single dict with 
        # PV : Value pairs
        for k, v in params.items():
            if k != 'BASE':
                temp_base = basepv + ':' + k
            else:
                temp_base = basepv
            if isinstance(v, dict):
                self._unpack_pv_dict(temp_base, v, out_dict)
            else:
                out_dict[temp_base] = v

        return out_dict

    def _pack_pv_dict(self, basepv, params, out_dict):
        # Recursively pack parameter data, creating dict of dicts where PV
        # post-fixes create further nested dictionaries
        dicts = []
        for k, v in params.items():
            stripped_key = k.replace(basepv + ':', '') 
            levels = stripped_key.split(':')
            ## start "seed" dictionary with the final key:value pair
            out_dict = {levels[-1] : v}
            del levels[-1]
            for level in reversed(levels):
                out_dict = {level: out_dict}
            dicts.append(out_dict)
        def pack_dict(in_dict, out_dict): 
            for k, v in in_dict.items(): 
                if k not in out_dict: 
                    out_dict[k] = v 
                else: 
                    if isinstance(in_dict[k], dict): 
                        pack_dict(in_dict[k], out_dict[k])
        if 'BASE' not in out_dict:
            out_dict['BASE'] = {}
        for d in dicts:
            for k, v in d.items():
                if not isinstance(v, dict): # 'BASE' PV parameter
                    out_dict['BASE'][k] = v
                else:
                    pack_dict(d, out_dict)

        return out_dict

#    Commenting this out for now until we're ready to test. 
#    def apply_ioc_parameters(self, ioc):
#        """
#        Apply the configuration parameters in the current configuration to the
#        IOC.
#        """
#        params = self.get_ioc_parameters(ioc)
#        cfg = self.get_ioc_config(ioc)
#        ioc_base = self.get_base_pv() + cfg['IOC']['POSTFIX']
#
#        out_params = {}
#        out_params = self._unpack_pv_dict(ioc_base, params, out_params)
#
#        #TODO: need to work in ophyd signal for this to actually apply values
#        for key in out_params:
#            #sig = EpicsSignal(key)
#            #sig.put(p[key])
#            print("PV: {}, Val: {}".format(key, out_params[key]))
#
#    def retrieve_ioc_parameters(self, ioc):
#        """
#        Retrieve the current configuration parameters in a running instance of
#        the specified IOC.
#        """
#        # TODO: deal with :types:?
#        # TODO:need to work in ophyd signal for this
#        p = self.get_ioc_parameters(ioc)
#        params = {}
#        for key in p:
#            sig = EpicsSignal(key)
#            params[key] = signal.get()
#
#        # reshape dict
#        out_params = {}
#        out_params = self._pack_pv_dict(self.get_base_pv() + ':', params, out_params)
#
#        return out_params

#    def save_ioc_parameters(self, ioc, parameters=None):
#        """
#        Save a configuration parameters dictionary to the specified IOC. If no
#        parameters are provided, attempt to connect to the IOC parameter PVs
#        and save the current values.
#        """
#        # Get PVs from DB
#        current = self.get_ioc_parameters(ioc)
#        if parameters == None:
#            # Get PVs from IOC
#            parameters = self.retrieve_ioc_parameters(ioc) 
#        unpacked_current = {}
#        unpacked_current = self._unpack_pv_dict(self.get_base_pv(), current, unpacked_current)
#        unpacked_request = {}
#        unpacked_request = self._unpack_pv_dict(self.get_base_pv(), parameters, unpacked_request)
#
#        for k, v in unpacked_request.items():
#            if k in unpacked_current:
#                unpacked_current[k] = unpacked_request[k]
#            else:
#                continue # Leave missing values alone
#
#        # Pack the unpacked config back up, restoring nested dicts
#        new_config = {}
#        new_config = self._pack_pv_dict(self.get_base_pv(), unpacked_current, new_config)
#        cfg = self.get_ioc_config('IOC')
#        cfg['CONFIG'] = new_config
#        self.set_current_config(new_config)

    def get_assembly_config_file_data(self):
        """
        Return a dictionary containing the information to be written to the
        assembly config file.
        """
        cfg = self.get_current_config()
        file_data = {'COMMON': cfg['COMMON']}
        
        iocs = self.get_iocs()

        for ioc in iocs:
            file_data[ioc] = cfg[ioc]['IOC']
        
        return file_data
        
    def write_assembly_config_file(self, fpath):
        """
        Write a complete configuration file for the assembly to the specified
        filepath. Uses the current configuration.
        """
        with open(fpath, 'w') as f:
            cfg_data = self.get_assembly_config_file_data()
            for header, section in cfg_data.items():
                f.write('[' + header + ']\n') # Section header
                for param, value in section.items():
                    f.write(param + '=' + str(value) + '\n') # Add IOC parameters
                f.write('\n') # Section spacer

    def read_assembly_config_file(self, fpath):
        """
        Read an existing configuration file. Returns a typed JSON dictionary 
        containing the assembly configuration. 
        """
        #TODO: Is this more of a TILE level (or higher) thing? This will get
        # new configs into the database. Perhaps we should read them in. How
        # does this deal with :types:?
        conf = configparser.ConfigParser()
        conf.read(fpath)

        cd = cdict()

        for section in conf.sections(): 
            for key in conf[section].keys(): 
                name = 'IOC.' + section.upper() + '.' + key.upper() 
                cd.set(name, str(conf[section][key]), type='CHARSTR')

        return cd
        
class TILE(object):
    """
    Class for handling 'TILES' that are part of MODS tables in the laser
    configuration database. Examples of 'TILES' are injection, ejection, and
    compressor. TILES are comprised of 'assemblies' that contain the device
    information.
    """
    def __init__(self, configdb, hutch, alias):
        self._cdb = configdb
        self._hutch = hutch
        self._alias = alias

    def _make_device(self, device):
        """
        Helper method to check device legitimacy and return an Assembly object
        for valid devices.
        """
        devices = self.get_devices()
        if device not in devices:
            raise ValueError("Unrecognized devices {}".format(device))
        d = Assembly(self._cdb, self._hutch, self._alias, device)
        
        return d
        
    def get_devices(self):
        """
        Method for retrieving the current devices in the TILE configuration. 
        """
        devices = self._cdb.get_devices(self._alias, hutch=self._hutch) 

        return devices 

    def get_device_config(self, device):
        """
        Return the current configuration of the specified device. 
        """
        d = self._make_device(device)
        cfg = d.get_current_config()

        return cfg

    def set_device_config(self, device, new_cfg):
        d = self._make_device(device)
        d.set_current_config(new_cfg)

class MODS(object): 
    """
    Class for handling MODS tables in the laser configuration database. The 
    MODS object is a "hutch" in the MongoDB that is a  combination of 'TILES', 
    which are also "hutches" themselves, and other top-level MODS devices such
    as PDUs and digitizers. Each TILE is a combination of "Assembly" objects
    that contain information for one or more IOCs. The Assemblies are "devices"
    in the MongoDB that are dictionaries of configurations, which contain both
    IOC build information, and IOC configuration information.
    """
    #TODO: Finish this class to group Assembly classes into a complete MODS
    def __init__(self, configdb, hutch, alias):
        self._cdb = configdb
        self._hutch = hutch
        self._alias = alias

# Setup some devices for testing
ldb = cdb("mcbrowne:psana@psdb-dev:9306", root="lasDB")
ttf = Assembly(ldb, 'injection', 'STD', 'tuttifrutti1')
inj = TILE(ldb, 'injection', 'STD')

tst = cdict()
tst.setInfo(detType='injection', detName='injection_ip1')
tst.set('devices.1', 'tuttifrutti1', type="CHARSTR")
tst.set('devices.2', 'tuttifrutti2', type="CHARSTR")

