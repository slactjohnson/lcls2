import os, shutil
import subprocess
from setup_input_files import setup_input_files

# cpo and weninc split off this test because of an issue with openmpi where
# a python file that does "import mpi4py" cannot fork an "mpirun" command.
# see: https://bitbucket.org/mpi4py/mpi4py/issues/95/mpi4py-openmpi-300-breaks-subprocess

class Test:
    def test_mpi(self, tmp_path):
        setup_input_files(tmp_path)

        env = dict(list(os.environ.items()) + [
            ('TEST_XTC_DIR', str(tmp_path)),
            ('PS_SRV_NODES', '0'),
            ('PS_SMD_NODES', '1')
        ])

        loop_based = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'user_loops.py')
        subprocess.check_call(['mpirun','-n','3','python',loop_based], env=env)

        callback_based = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'user_callbacks.py')
        subprocess.check_call(['mpirun','-n','3','python',callback_based], env=env)
        
        loop_exhaustive_based = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'ds.py')
        subprocess.check_call(['mpirun','-n','3','python',loop_exhaustive_based], env=env)
        
        # Test more than 1 bigdata node
        loop_exhaustive_based = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'ds.py')
        subprocess.check_call(['mpirun','-n','5','python',loop_exhaustive_based], env=env)
        
        run_smalldata = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'run_mixed_rate.py')
        subprocess.check_call(['mpirun','-n','5','python',run_smalldata], env=env)
        
        env['PS_SMD_NODES'] = '1' # reset no. of eventbuilder cores
        env['PS_SRV_NODES'] = '2'
        run_smalldata = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'run_smalldata.py')
        subprocess.check_call(['mpirun','-n','6','python',run_smalldata], env=env)
