import os, re, random, math
from pj_async_re import async_re_job

class pj_amber_job(async_re_job):

    def _launchReplica(self,replica,cycle):
        """Launches Amber sub-job using pilot-job
        """

        if self.keywords.get('SPMD') is None:
            spmd = 'single'
        else:
            spmd = self.keywords.get('SPMD')
            if spmd == 'single':
                exe = os.popen('which sander','r').readlines()[0].strip()
            elif spmd == 'mpi':
                exe = os.popen('which sander.MPI','r').readlines()[0].strip()

        if self.keywords.get('PPN') is None: ppn = 1
        else:                                ppn = int(self.keywords.get('PPN'))

        input_file = "%s_%d.inp" % (self.basename, cycle)
        out_file = "%s_%d.out" % (self.basename, cycle)
        prm_file = "%s.parm7" % self.basename
        crd_file = "%s_%d.rst7" % (self.basename, cycle-1)
        rst_file = "%s_%d.rst7" % (self.basename, cycle)
        xyz_file = "%s_%d.nc" % (self.basename, cycle)
        info_file = "%s_%d.info" % (self.basename, cycle)
        log_file = "%s_%d.log" % (self.basename, cycle)
        err_file = "%s_%d.err" % (self.basename, cycle)

        arguments = ["-O",
                     "-i", input_file,
                     "-o", out_file, 
                     "-p", prm_file, 
                     "-c", crd_file, 
                     "-r", rst_file, 
                     "-x", xyz_file, 
                     "-inf", info_file]

        #pilotjob: Compute Unit (i.e. Job) description
        compute_unit_description = {
            "executable": exe,
            "environment": [],
            "arguments": arguments,
            "total_cpu_count": int(self.keywords.get('SUBJOB_CORES')),
            "output": log_file,
            "error": err_file,   
            "working_directory":os.getcwd()+"/r"+str(replica),
            "number_of_processes": ppn, 
            "spmd_variation": spmd,
            }

        if self.keywords.get('VERBOSE') == "yes":
            print ( "Launching %s in directory %s (cycle %d)" % 
                    (exe.split('/')[-1], os.getcwd()+"/r"+str(replica), cycle) )

#        compute_unit=self.cds.submit_compute_unit(compute_unit_description)
        compute_unit=self.pilotcompute.submit_compute_unit(compute_unit_description)
        return compute_unit

    def _getAmberUSData(self, file):
        """Reads the bias coordinate values from NMRopt output file
        """
        if not os.path.exists(file):
            msg = 'File does not exist: %s' % file
            self._exit(msg)
        data = []
        f = self._openfile(file ,"r")
        line = f.readline()
        while line:
            words = line.split()
            data.append(words)
            line = f.readline()
        f.close()
        return data
        
    def _hasCompleted(self,replica,cycle):
        """
        Returns true if an Amber replica has completed a cycle. Basically 
        checks if the restart file exists.
        """
        rstfile = "r%d/%s_%d.rst7" % (replica, self.basename,cycle)
        if os.path.exists(rstfile):
            return True
        else:
            return False
