

import os
import subprocess
import pytest
import h5py
import numpy as np
from glob import glob


from psana import DataSource
from test_shmem import Test as ShmemTest


# cpo found this on the web as a way to get mpirun to exit when
# one of the ranks has an exception
import sys
# Global error handler
def global_except_hook(exctype, value, traceback):
    sys.stderr.write("except_hook. Calling MPI_Abort().\n")
    # NOTE: mpi4py must be imported inside exception handler, not globally.
    # In chainermn, mpi4py import is carefully delayed, because
    # mpi4py automatically call MPI_Init() and cause a crash on Infiniband environment.
    import mpi4py.MPI
    mpi4py.MPI.COMM_WORLD.Abort(1)
    sys.__excepthook__(exctype, value, traceback)


sys.excepthook = global_except_hook

from mpi4py import MPI
comm = MPI.COMM_WORLD
rank = comm.Get_rank()
size = comm.Get_size()


global CALLBACK_OUTPUT
CALLBACK_OUTPUT = []


def gen_h5(source='xtc', pid=None):

    def test_callback(data_dict):
        CALLBACK_OUTPUT.append(data_dict['oneint'])


    if source == 'xtc':
        xtc_dir = os.path.join(os.environ.get('TEST_XTC_DIR', os.getcwd()),'.tmp')
        ds = DataSource(exp='xpptut13', run=1, dir=xtc_dir, filter=lambda x : True, batch_size=2)
    elif source == 'shmem':
        ds = DataSource(shmem='shmem_test_' + pid)

    smd = ds.smalldata(filename='smalldata_test.h5', batch_size=5,
                       callbacks=[test_callback])

    run = next(ds.runs())
    for i,evt in enumerate(run.events()):

        print('event:', i)

        smd.event(evt, 
                  timestamp=evt.timestamp, 
                  oneint=1, 
                  twofloat=2.0,
                  arrint=np.ones(2, dtype=np.int),
                  arrfloat=np.ones(2, dtype=np.float)
                  # ragged_
                  )


        if evt.timestamp % 2 == 0:
            smd.event(evt,
                      # unaligned_int=3,
                      every_other_missing=2)

        if (rank % 2 == 0) and (smd._type == 'client'):
            smd.event(evt, missing_vds=1)

    # smd.summary(...)

    smd.done() # can we get rid of this?

    return


class SmallDataTest:

    def __init__(self):
        self.fn = 'smalldata_test.h5'
        print('TESTING --> %s' % self.fn)
        f = h5py.File(self.fn, 'r')
        self.f = f
        return
        

    def test_int(self): 
        assert np.all(np.array(self.f['/oneint']) == 1)
        return

    def test_float(self): 
        assert np.all(np.array(self.f['/twofloat']) == 2.0)
        return

    def test_arrint(self): 
        a = np.array(self.f['/arrint'])
        assert np.all(a == 1), a
        assert a.shape[1] == 2, a
        assert a.dtype == np.int, a
        return

    def test_arrfloat(self):
        a = np.array(self.f['/arrfloat'])
        assert np.all(a == 1.0), a
        assert a.shape[1] == 2, a 
        assert a.dtype == np.float, a
        return

    # def test_unaligned(self): return

    def test_every_other_missing(self):
        d = np.array(self.f['/every_other_missing'])
        assert np.sum((d == 2)) == 5, d
        assert np.sum((d == -99999)) == 5, d
        return

    # def test_missing_vds(self): return



# -----------------------

def run_test(mode, tmp_path):

    if rank == 0:
        for fn in glob(".?_smalldata_test.h5"):
            os.remove(fn)
    comm.barrier()

    if mode == 'xtc':
        gen_h5('xtc')
    elif mode == 'shmem':
        pid = None
        if rank == 0:
            pid = str(os.getpid())
            tmp_file = tmp_path / '.tmp/shmem/data_shmem.xtc2'
            ShmemTest.setup_input_files(tmp_path  / '.tmp')
            ShmemTest.launch_server(tmp_file, pid)

        pid = comm.bcast(pid, root=0)
        gen_h5('shmem', pid=pid) 

    # make sure everyone is finished writing test file
    # then test with a single rank
    comm.barrier()
    if rank == 0:
        testobj = SmallDataTest()
        testobj.test_int()
        testobj.test_float()
        testobj.test_arrint()
        testobj.test_arrfloat()

        # currently this test counts the number of events that are missing
        # however, that number is not deterministic for shmem (depends on speed)
        # need to update for shmem case
        #testobj.test_every_other_missing()

    assert CALLBACK_OUTPUT == [1,] * len(CALLBACK_OUTPUT), CALLBACK_OUTPUT

    return


# pytest test_smalldata.py will call ONLY .main()
# NOTE : could merge test_smalldata.py into this file
def main(tmp_path):
    run_test('xtc', tmp_path)
    import platform
    # don't test shmem on macOS
    if platform.system()!='Darwin':
        run_test('shmem', tmp_path)
    return

# pytest byhand_mpi.py will call this section of the code (w/mpirun)
if __name__ == '__main__':

    import pathlib

    # COMMENT IN TO RUN python ...
    #from setup_input_files import setup_input_files
    #tmp_path = pathlib.Path('.')
    #setup_input_files(tmp_path) # tmp_path is from pytest :: makes .tmp
    #main(tmp_path)
    #os.system('rm -r .tmp')

    # COMMENT IN TO RUN pytest ...
    tmp_path = pathlib.Path(os.environ.get('TEST_XTC_DIR', os.getcwd()))
    main(tmp_path)


