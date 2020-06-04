from psana.psexp.envstore import EnvStore
from psana.dgram import Dgram

class EnvStoreManager(object):
    """ Manages envStore.
    Stores list of envStores (created according to given keywords e.g 'epics')
    and update the stores with list of views.
    """
    stores = {}
    
    def __init__(self, configs, *args):
        self.configs = configs
        for arg in args:
            self.stores[arg] = EnvStore(configs, arg)
    
    def update_by_event(self, evt):
        if not evt:
            return
        for i, d in enumerate(evt._dgrams):
            if not d: continue

            # This releases the original dgram object (friendly
            # with shared memory which has limited capacity).
            new_d = Dgram(view=d, config=self.configs[i], offset=0)
            for key, val in d.__dict__.items():
                if key in self.stores:
                    self.stores[key].add_to(new_d, i)

    def update_by_views(self, views):
        if not views:
            return
        for i in range(len(views)):
            view = bytearray(views[i])
            offset = 0
            while offset < memoryview(view).shape[0]:
                d = Dgram(view=view, config=self.configs[i], offset=offset)
                for key, val in d.__dict__.items():
                    if key in self.stores:
                        self.stores[key].add_to(d, i)
                    
                offset += d._size
                    
    def env_from_variable(self, variable_name):
        for env_name, store in self.stores.items():
            found = store.locate_variable(variable_name)
            if found is not None:
                alg, _ = found
                return env_name, alg
        return None

    


        
        
