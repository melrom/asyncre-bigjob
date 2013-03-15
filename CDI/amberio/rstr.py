"""                                                                             
FILE: rstr.py - plugin for AMBER nmropt style restraint files

DESCRIPTION: This module provides a convenient implementation of restraints
in AMBER for use in Python. This is useful, for example, if one wants to
determine just the restraint energy of a set of coordinates without
running a full energy evaluation in AMBER.

AUTHOR: Brian K. Radak (BKR) - <radakb@biomaps.rutgers.edu>

REFERENCES: AMBER 12 Manual: ambermd.org/doc12/Amber12.pdf
"""
from math import pi
import sys
import coordinates

__all__ = ['ReadAmberRestraintFile','AmberRestraint','NmroptRestraint']

def ReadAmberRestraintFile(rstFilename):
    """
    Read an AMBER restraint file (usually file extension RST) and return an
    AmberRestraint object containing each restraint found therein.

    REQUIRED ARGUMENTS:
    rstFilename - file containing AMBER "&rst" namelists

    RETURN VALUES:
    amberRst - AmberRestraint object (list of NmroptRestraint)
    """
    from namelist import ReadNamelists
    amberRstr = AmberRestraint()
    # Read the namelists from the restraint file and look for &rst namelists
    namelists = ReadNamelists(rstFilename)
    for nl in namelists:
        if nl.name == 'rst':
            # only the iat keyword is required to define a restraint
            if not nl.has_key('iat'):
                msg = "'iat' must be specified to define an nmropt restraint."
                raise Exception(msg)
            iat = tuple([ int(i) for i in nl.pop('iat').split(',') ])
            if nl.has_key('rstwt'):
                rstwt = nl.pop('rstwt')
                amberRstr.append(GenDistCoordRestraint(iat,rstwt,**nl))
            else:
                if len(iat) == 2:
                    amberRstr.append(BondRestraint(iat,**nl))
                elif len(iat) == 3:
                    amberRstr.append(AngleRestraint(iat,**nl))
                elif len(iat) == 4:
                    amberRstr.append(TorsionRestraint(iat,**nl))
                else:
                    raise Exception('Bad iat specification')
    if len(amberRstr) < 1:
        print 'WARNING! No &rst namelists were found in %s.'%rstFilename
    return amberRstr


class AmberRestraint(list):
    """
    A collection (list) of NmroptRestraints defining an AMBER restraint energy.

    (See NmroptRestraint for further details.)
    """
    def __init__(self, *rstrs):
        list.__init__(self)
        for rstr in rstrs: self.extend(rstr)
        
    def append(self, item):
        if not isinstance(item, NmroptRestraint):
            raise TypeError('AmberRestraints must contain NmroptRestraints!')
        list.append(self, item)
    
    def extend(self, items):
        if hasattr(items, '__iter__'):
            for item in items:
                self.append(item)
            
    def __eq__(self, other):
        if len(self) != len(other):
            return False
        # Must test all possible permutations!
        from itertools import permutations
        areSame = False
        for perm_i in permutations(self):
            for perm_j in permutations(other):
                for rstr_i,rstr_j in zip(perm_i,perm_j):
                    if rstr_i != rstr_j:
                        areSame = False
                        break
                    else:
                        areSame = True
                if areSame:
                    return True
        return areSame

    def __ne__(self, other):
        return not AmberRestraint.__eq__(self,other)

    def SetRestraintParameters(self, **rstr_params):
        """
        Convenience function for setting any of r0, r1, r2, r3, r4, k0, rk2, and
        rk3 by list assignment. 

        Parameters will be assigned in order until either no parameters or 
        restraints are left. Thus, paramaters can be set for restraints 1 and 2,
        but not 1 and 3. For the latter case the individual restraints must
        be modified directly.
        """
        nrstrs = len(self)
        for params,values in rstr_params.iteritems():
            nvalues = len(values)
            # case 1: more restraints than parameter values
            if nrstrs >= nvalues:
                for i,value in enumerate(values):
                    self[i].SetRestraintParameters(**{params:float(value)})
            # case 1: more parameter values than restraints 
            #         (better to ask for forgiveness than permission)
            else:
                print ('Warning: %d restraint parameters were specified, but'
                       ' only %s restraints are defined.'%(nvalues,nrstrs))
                for i,rstr in enumerate(self):
                    value = float(rstr_params[params][i])
                    rstr.SetRestraintParameters(**{params:value})

    def Energy(self, crds):
        """
        Calculate the total energy from all restraints.

        REQUIRED ARGUMENTS:
        crds - 3N list of coordinates (in Angstroms) 
               OR 
               list of values for each of the restraint coordinates

        RETURN VALUES:
        energy - total restraint energy (in kcal/mol)
        """
        energy = 0.
        if len(crds) == len(self):
            for rst,r in zip(self,crds): energy += rst.Energy(r)
        else:
            for rst in self: energy += rst.Energy(crds)
        return energy

    def EnergyAndGradients(self, crds):
        """
        THIS IS CURRENTLY BROKEN AND RETURNS ALL GRADIENTS AS ZERO!

        Calculate the total energy and gradients from all restraints.

        REQUIRED ARGUMENTS:
        crds - 3N list of coordinates (in Angstroms)
               OR 
               list of values for each of the restraint coordinates

        RETURN VALUES:
        energy - restraint energy (in kcal/mol)
        gradients - 3N list of cartesian gradients (in kcal/mol-x)

        x - either Angstroms or radians
        """
        energy = 0.
        gradients = [ 0. for n in range(len(crds)) ]
        for rst in self:
            e,g = rst.EnergyAndGradients(crds)
            energy += e
            for i in range(len(g)): gradients[i] += g[i]
        return energy,gradients

    def DecomposeEnergy(self, crds):
        """Decompose (by restraint type) the total energy from all restraints.

        REQUIRED ARGUMENTS:
        crds - 3N list of coordinates (in Angstroms)
               OR 
               list of values for each of the restraint coordinates

        RETURN VALUES:
        energy - dict containing decomposed energies (in kcal/mol); 
                 
        NB. The 'Restraint' key corresponds to the total energy.
        """
        component_type = {BondRestraint : 'Bond', 
                          AngleRestraint : 'Angle',
                          TorsionRestraint : 'Torsion', 
                          GenDistCoordRestraint : 'Gen. Dist. Coord.'}
        energy = {'Bond':0., 'Angle':0., 'Torsion':0., 'Gen. Dist. Coord.':0.}
        if len(crds) == len(self):
            for rst,r in zip(self,crds):
                energy[component_type[type(rst)]] += rst.Energy(r)
        else:
            for rst,r in zip(self,crds):
                energy[component_type[type(rst)]] += rst.Energy(crds)
        eRestraint = 0.
        for key in energy.keys(): eRestraint += energy[key]
        energy['Restraint'] = eRestraint
        return energy

    def PrintRestraintReport(self, crds=None, anames=None):
        """
        Print a restraint report in the same format as AMBER output.
        Information not available from a restraint file (e.g. atom names) will
        be omitted unless additional information is provided.

        OPTIONAL ARGUMENTS:
        crds - 3N list of coordinates (in Angstroms)
        anames - N list of atom names
        """
        for rst in self:
            print '******' 
            rst.PrintRestraintReport(crds,anames)
        print '%23sNumber of restraints read = %5d'%('',len(self))

    def PrintRestraintEnergyReport(self, crds):
        """
        Print a restraint energy report in the same format as AMBER output.

        REQUIRED ARGUMENTS:
        crds - 3N list of coordinates (in Angstroms)
        """
        e = self.DecomposeEnergy(crds)
        print (' NMR restraints: Bond =%9.3f   Angle = %9.3f   Torsion = %9.3f'
               %(e['Bond'],e['Angle'],e['Torsion']))
        if e['Gen. Dist. Coord.'] > 0.:
            print ('               : Gen. Dist. Coord. = %9.3f'
                   %e['Gen. Dist. Coord.'])

    def WriteAmberRestraintFile(self, outfile, title=''):
        """
        Write an AMBER restraint file with all of the current restraints.

        REQUIRED ARGUMENTS:
        outfile - file object or name for writing
        
        OPTIONAL ARGUMENTS:
        title - 
        """
        if hasattr(outfile,'write'):
            pass
        elif isinstance(outfile,str):
            outfile = open(outfile,'w')
        else:
            raise TypeError("'outfile' must be either a string or file object.")
        outfile.write('%s\n'%title)
        for rst in self: rst.WriteRstNamelist(outfile,closeafter=False)
        if outfile is not sys.__stdout__: outfile.close()
      

class NmroptRestraint(object):
    """
    A restraint object like that in the AMBER nmropt module. The restraint form
    is a harmonic flat-bottom well with six parameters: four positions (r1-r4) 
    and two force constants (rk2 and rk3).

    From the AMBER 12 Manual (section 6.1.1 p. 204):
    ---
    the restraint is a well with a square bottom with parabolic sides out to a 
    defined distance, and then linear sides beyond that. If R is the value of 
    the restraint in question:

    -R<r1 Linear, with the slope of the "left-hand" parabola at the point R=r1
    -r1<=R<r2 Parabolic, with restraint energy k2(R-r2)^2
    -r2<=R<r3 E = 0
    -r3<=R<r4 Parabolic with restraint energy k3(R-r3)^2
    -r4<=R Linear, with the slope of the "right-hand" parabola at the point R=r4
    ----

    Frequently one only desires a purely harmonic well, in which case r1 << r2,
    r2=r3, r3 << r4, and rk2 = rk3. These defaults can be obtained by only
    specifying r0 and k0 (as in sander from AMBER 10 onward).

    REQUIRED ARGUMENTS:
    iat - list of atom indices defining the restraint

    OPTIONAL ARGUMENTS:
    rstr_params - any of r0, r1, r2, r3, r4, k0, rk2, and rk3 can be set by
    direct assignment. r0 and k0 will override all other specifications.

    NB: As in AMBER, angle positions are in degrees while angle force constants
    are in radians. Distances are always in Angstroms.
    """
    def __init__(self, iat, **rstr_params):
        self.iat = iat
        self._r  = [0., 0., 0., 0.]
        self._rk = [0., 0.]
        self.SetRestraintParameters(**rstr_params)

    def __eq__(self, other):
        if not isinstance(other,type(self)):
            return False
        # check atom defintions (could be reversed)
        if len(self.iat) != len(other.iat):
            return False
        same_perm = False
        for i,j in zip(self.iat,other.iat):
            if i != j:
                same_perm = False
                break
            else:
                same_perm = True
        if not same_perm:
            for i,j in zip(reversed(self.iat),other.iat):
                if i != j:
                    same_perm = False
                    break
                else:
                    same_perm = True
        if not same_perm:
            return False
        # check force constants
        for ki,kj in zip(self._rk,other._rk):
            if ki != kj:
                return False
        # check restraint positions
        for ri,rj in zip(self._r,other._r):
            if ri != rj:
                return False
        return True
 
    def __ne__(self, other):
        return not NmroptRestraint.__eq__(self,other)  

    def SetRestraintParameters(self, **rstr_params):
        """Set any of r0, r1, r2, r3, r4, k0, rk2, and rk3 by assignment.
        """
        # A pure harmonic restraint can be set with just r0, 
        if rstr_params.has_key('r0'):
            r0 = float(rstr_params['r0'])
            self._r[1:3] = [r0,r0]
            self._r[0] = self._harmonic_r1()
            self._r[3] = self._harmonic_r4()
            self._r = [ r/self._report_conversion for r in self._r ]
        # otherwise the four positions need to be set individually.
        else:
            rs = {'r1':0,'r2':1,'r3':2,'r4':3}
            for r,i in rs.iteritems():
                if rstr_params.has_key(r):
                    self._r[i] = float(rstr_params[r])/self._report_conversion

        # Check the relative restraint positions.
        if not self._r[0] <= self._r[1] <= self._r[2] <= self._r[3]:
            msg = ('Restraint positions must be monotonically increasing'
                   ' (r1 <= r2 <= r3 <= r4).')
            raise ValueError(msg)

        #  A pure harmonic restraint can be set with just k0,
        if rstr_params.has_key('k0'):
            k0 = float(rstr_params['k0'])
            self._rk = [k0,k0]
        # otherwise the two force constants need to be set individually.
        else:
            if rstr_params.has_key('rk2'):
                self._rk[0] = float(rstr_params['rk2'])
            if rstr_params.has_key('rk3'):
                self._rk[1] = float(rstr_params['rk3'])

    def Energy(self, crds):
        """Calculate the restraint energy.

        REQUIRED ARGUMENTS:
        crds - 3N list of coordinates (in Angstroms)

        RETURN VALUES:
        energy - restraint energy (in kcal/mol)
        """
        energy,gradients = self.EnergyAndGradients(crds)
        return energy

    def EnergyAndGradients(self, crds):
        """
        THIS IS CURRENTLY BROKEN AND RETURNS ALL GRADIENTS AS ZERO!
        
        Calculate the restraint energy and gradients.

        REQUIRED ARGUMENTS:
        crds - 3N list of coordinates (in Angstroms)

        RETURN VALUES:
        energy - restraint energy (in kcal/mol)
        gradients - 3N list of cartesian gradients (in kcal/mol-x)

        x - either Angstroms or radians
        """
        if isinstance(crds,float) or isinstance(crds,int):
            print 'shortcut!'
            r = float(crds)
            drdx = [ 0. ]
        else:
            r,drdx = self.CoordAndGradients(crds)
        dedr = 0.
        energy = 0.
        # The following is the harmonic, flat-bottomed well described in the
        # AMBER manual. See the class documentation for more details.
        if r < self._r[0]:
            dr = self._r[0] - self._r[1]
            dedr = 2.*self._rk[0]*dr 
            energy = dedr*(r-self._r[0]) + self._rk[0]*dr**2
        elif self._r[0] <= r < self._r[1]:
            dr = r - self._r[1]
            dedr = 2.*self._rk[0]*dr
            energy = self._rk[0]*dr**2
        elif self._r[1] <= r < self._r[2]:
            dedr = 0.
            energy = 0.
        elif self._r[2] <= r < self._r[3]:
            dr = r - self._r[2]
            dedr = 2.*self._rk[1]*dr
            energy = self._rk[1]*dr**2
        else:
            dr = self._r[3] - self._r[2]
            dedr = 2.*self._rk[1]*dr
            energy = dedr*(r-self._r[3]) + self._rk[1]*dr**2
        # Use the chain rule to get the gradient (dE/dx) along the atomic 
        # cartesian coordinates:
        #
        # dE/dx = (dE/dr)(dr/dx)
        #
        # where E is the energy, r is the restraint coordinate, and x is some 
        # atomic cartesian coordinate.
        gradients = [ dedr*drdxi for drdxi in drdx ]
        return energy,gradients

    def PrintRestraintReport(self, crds=None, anames=None):
        """
        Print a restraint report in the same format as AMBER output.
        Information not available from a restraint file (e.g. atom names) will
        be omitted unless additional information is provided.

        OPTIONAL ARGUMENTS:
        crds - 3N list of coordinates (in Angstroms)
        anames - N list of atom names
        """
        # Use blanks if atom names are not available
        if anames is None: 
            anames = [ '' for i in range(len(self.iat)) ]
        else:              
            anames = [ anames[i-1] for i in self.iat ]
        # The format for restraints on 4 or fewer atoms is rather simple:
        if len(self.iat) <= 4:
            line = ' '
            for i in range(len(self.iat)):
                line += '%-4s(%5d)-'%(anames[i],self.iat[i])
            print line[:-1]
        # The format for more complicated restraints is a little muckier:
        else:
            line1 = ' '
            for i in range(4): 
                line1 += '%-4s(%5d)-'%(anames[i],self.iat[i])
            line2 = ' '
            for i in range(4,len(self.iat)): 
                line2 += '%-4s(%5d)-'%(anames[i],self.iat[i])
            print line1
            print line2
        print ('R1 =%8.3f R2 =%8.3f R3 =%8.3f R4 =%8.3f RK2 =%8.3f RK3 = %8.3f'
               %(self._r[0]*self._report_conversion,
                 self._r[1]*self._report_conversion,
                 self._r[2]*self._report_conversion,
                 self._r[3]*self._report_conversion,
                 self._rk[0],self._rk[1]))
        if crds is not None: # Report on any coordinates provided as input.
            curr = self.Coord(crds)
            d_avg = abs(curr - (self._r[1]+self._r[2])/2.)
            min_d = min(abs(curr - self._r[1]),abs(curr - self._r[2]))
            print (' Rcurr: %8.3f  Rcurr-(R2+R3)/2: %8.3f  '
                   'MIN(Rcurr-R2,Rcurr-R3): %8.3f'
                   %(curr*self._report_conversion,d_avg*self._report_conversion,
                     min_d*self._report_conversion))

    def _extra_namelist_values(self):
        """Return extra namelist variables not defined by the base class.
        """
        return ''

    def WriteRstNamelist(self, outfile=sys.stdout, closeafter=True):
        """
        Write an &rst namelist with the current restraint information.

        OPTIONAL ARGUMENTS:
        outfile - file object or name to write data to, default=stdout
        closeafter (bool) - flag to close outfile after writing, default=True
        """
        # Accept a file object or file name for namelist printing
        if hasattr(outfile,'write'):
            pass
        elif isinstance(outfile,str):
            outfile = open(outfile,'w')
        else:
            raise TypeError("'outfile' must be either a string or file object.")
        # Build up a string representation of the namelist values.
        sprint = ' &rst iat=%s'%','.join([str(i) for i in self.iat])
        for i in range(4): 
            sprint += ' r%d=%s'%(i+1,str(self._r[i]*self._report_conversion))
        for i in range(2): 
            sprint += ' rk%d=%s'%(2+i,str(self._rk[i]))
        sprint += self._extra_namelist_values()
        sprint += ' / \n'
        outfile.write(sprint)
        if closeafter and outfile is not sys.__stdout__: outfile.close()


class BondRestraint(NmroptRestraint):
    def __init__(self, iat, **rstr_params):
        assert len(iat) == 2
        self._report_conversion = 1.
        NmroptRestraint.__init__(self,iat,**rstr_params)

    def _harmonic_r1(self):
        # Set r1 to be r0 minus a "really big number" (500 in AMBER).
        return self._r[1] - 500.
    
    def _harmonic_r4(self):
        # Set r4 to be r0 plus a "really big number"  (500 in AMBER).
        return self._r[1] + 500.

    def Coord(self, crds):
        """Return the restrained bond distance given a 3N coordinate list.
        """
        i = self.iat[0] - 1
        j = self.iat[1] - 1
        return coordinates.Bond(crds,i,j)

    def CoordAndGradients(self, crds):
        """
        Return the restrained bond distance and the gradients along the atom
        cartesian coordinates given a 3N coordinate list.

        THIS IS CURRENTLY BROKEN AND RETURNS ALL GRADIENTS AS ZERO!        
        """
        drdx = [ 0. for n in range(len(crds)) ]
        i = self.iat[0] - 1
        j = self.iat[1] - 1
        r,drdxi,drdxj = coordinates.BondAndGradients(crds,i,j)
        drdx[3*i:3*(i+1)] = drdxi
        drdx[3*j:3*(j+1)] = drdxj
        return r,drdx


class AngleRestraint(NmroptRestraint):
    def __init__(self, iat, **rstr_params):
        assert len(iat) == 3
        self._report_conversion = 180./pi
        NmroptRestraint.__init__(self,iat,**rstr_params)
               
    def _harmonic_r1(self):
        # Set r1 to be 0 degrees.
        return 0.

    def _harmonic_r4(self):
        # Set r4 to be 180 degrees.
        return 180.

    def Coord(self, crds):
        """Return the restrained angle given a 3N coordinate list.
        """
        i = self.iat[0] - 1
        j = self.iat[1] - 1
        k = self.iat[2] - 1
        return coordinates.Angle(crds,i,j,k)

    def CoordAndGradients(self, crds):
        """
        Return the restrained angle and the gradients along the atom cartesian 
        coordinates given a 3N coordinate list.

        THIS IS CURRENTLY BROKEN AND RETURNS ALL GRADIENTS AS ZERO!        
        """
        drdx = [ 0. for n in range(len(crds)) ]
        i = self.iat[0] - 1
        j = self.iat[1] - 1
        k = self.iat[2] - 1
        r,drdxi,drdxj,drdxk = coordinates.AngleAndGradients(crds,i,j,k)
        drdx[3*i:3*(i+1)] = drdxi
        drdx[3*j:3*(j+1)] = drdxj
        drdx[3*k:3*(k+1)] = drdxk
        return r,drdx

class TorsionRestraint(NmroptRestraint):
    def __init__(self, iat, **rstr_params):
        assert len(iat) == 4
        self._report_conversion = 180./pi
        NmroptRestraint.__init__(self,iat,**rstr_params)

    def _harmonic_r1(self):
        # Set r1 to be r0 minus 180 degrees.
        return self._r[1] - 180.

    def _harmonic_r4(self):
        # Set r4 to be r0 plus 180 degrees.
        return self._r[1] + 180.

    def Coord(self, crds):
        """Return the restrained torsion given a 3N coordinate list.
        """
        i = self.iat[0] - 1
        j = self.iat[1] - 1
        k = self.iat[2] - 1
        l = self.iat[3] - 1
        r = coordinates.Dihedral(crds,i,j,k,l)
        # Get the closest periodic image/phase.
        rmean = (self._r[1] + self._r[2])/2.
        isNearestImage = False
        while not isNearestImage:
            if r - rmean > pi:
                r -= 2*pi
            elif rmean - r > pi:
                r += 2*pi
            else:
                isNearestImage = True
        return r

    def CoordAndGradients(self, crds):
        """
        Return the restrained torsion and the gradients along the atom 
        cartesian coordinates given a 3N coordinate list.

        THIS IS CURRENTLY BROKEN AND RETURNS ALL GRADIENTS AS ZERO!        
        """
        drdx = [ 0. for n in range(len(crds)) ]
        i = self.iat[0] - 1
        j = self.iat[1] - 1
        k = self.iat[2] - 1
        l = self.iat[3] - 1
        r,drdxi,drdxj,drdxk,drdxl = (
            coordinates.DihedralAndGradients(crds,i,j,k,l) )
        drdx[3*i:3*(i+1)] = drdxi
        drdx[3*j:3*(j+1)] = drdxj
        drdx[3*k:3*(k+1)] = drdxk
        drdx[3*l:3*(l+1)] = drdxl
        # Get the closest periodic image/phase.
        rmean = (self._r[1] + self._r[2])/2.
        isNearestImage = False
        while not isNearestImage:
            if r - rmean > pi:
                r -= 2*pi
            elif rmean - r > pi:
                r += 2*pi
            else:
                isNearestImage = True
        return r,drdx

class GenDistCoordRestraint(NmroptRestraint):
    def __init__(self,iat, rstwt, **rstr_params):
        assert len(iat)%2 == 0
        self._report_conversion = 1.
        NmroptRestraint.__init__(self,iat,**rstr_params)
        self.rstwt = [ float(w) for w in rstwt.split(',') ]
        if len(self.rstwt) != len(self.iat)/2:
            msg = ('Wrong number of rstwt values provided for %d atom Gen.' 
                   ' Dist. Coord. Expected %d, but got %d.'
                   %(len(self.iat),len(self.iat)/2,len(self.rstwt)))
            raise Exception(msg)
        
    def _harmonic_r1(self):
        # Set r1 to be r0 minus a "really big number" (500 in AMBER).
        return self._r[1] - 500.
    
    def _harmonic_r4(self):
        # Set r4 to be r0 plus a "really big number" (500 in AMBER).
        return self._r[1] + 500.

    def _extra_namelist_values(self):
        # Add the additional rstwt namelist variable.
        return ' rstwt=%s'%','.join([str(w) for w in self.rstwt])

    def Coord(self, crds):
        """
        Return the restrained generalized distance coordinate given a 3N 
        coordinate list.
        """
        r = 0.
        for k in range(len(self.rstwt)):
            i = self.iat[2*k+0] - 1
            j = self.iat[2*k+1] - 1
            x,drdxi,drdxj = coordinates.BondAndGradients(crds,i,j)
            r += self.rstwt[k]*x
        return r

    def CoordAndGradients(self, crds):
        """
        Return the restrained generalized distance coordinate and the gradients
        along the atom cartesian coordinates given a 3N coordinate list.

        THIS IS CURRENTLY BROKEN AND RETURNS ALL GRADIENTS AS ZERO!        
        """
        r = 0.
        drdx = [ 0. for n in range(len(crds)) ]
        for k in range(len(self.rstwt)):
            i = self.iat[2*k+0] - 1
            j = self.iat[2*k+1] - 1
            x,drdxi,drdxj = coordinates.BondAndGradients(crds,i,j)
            r += self.rstwt[k]*x
            for m in range(3):
                drdx[3*i+m] += self.rstwt[k]*drdxi[m]
                drdx[3*j+m] += self.rstwt[k]*drdxj[m]
        return r,drdx

if __name__ == '__main__':
    import sys
    argc = len(sys.argv)
    print '=== AmberRestraint Test Suite ==='
    if 5 > argc < 2:
        print 'usage: AmberRestraint.py RST [[inpcrd] prmtop]\n'
        print 'RST - AMBER restraint file'
        print 'inpcrd - AMBER crd file (optional test on coordinates)'
        print 'prmtop - AMBER parm file (optional test for reporting)\n'
        sys.exit()

    # Read restraints from a file
    rstFile = sys.argv[1]
    print 'reading AMBER restraint file: %s'%rstFile
    print '>>> rstTest = ReadAmberRestraintFile(%s)'%rstFile
    rstTest = ReadAmberRestraintFile(rstFile)

    # Create an nmropt restraint in pure python
    print 'testing creation of restraints in pure python:'
    print '>>> rstTest.append(BondRestraint((1,2)))'
    print '(makes a dummy restraint between atoms 1 and 2)'
    rstTest.append(BondRestraint((1,2)))
    print '>>> rstTest[-1].SetRestraintParameters(r0=1.0,k0=10.)'
    print '(sets a pure harmonic potential with only 2 parameters)'
    rstTest[-1].SetRestraintParameters(r0=1.0,k0=10.)

    # Read crd and parm files if present
    crds = None
    anames = None
    if argc > 2:
        import amberio.ambertools
        from chemistry.amber.readparm import rst7
        crdFile = sys.argv[2]
        print 'Reading coordinates from file: %s'%crdFile
        crds = rst7(crdFile).coords
    if argc > 3:
        from chemistry.amber.readparm import AmberParm
        prmFile = sys.argv[3]
        print 'Reading parm info from file: %s'%prmFile
        anames = AmberParm(prmFile).parm_data['ATOM_NAME']

    # Print a report of the restraints so far
    print 'printing an AMBER-style report:'
    print '>>> rstTest.PrintRestraintReport(crds,anames)'
    rstTest.PrintRestraintReport(crds,anames)
    
    if crds is not None:
        # Print a report like those found after MD steps
        print '\nprinting an AMBER-style restraint energy decomposition:'
        print '>>> rstTest.PrintRestraintEnergyReport(crds)'
        rstTest.PrintRestraintEnergyReport(crds)

        # Test the total energy and forces against an AMBER forcedump.dat
        print '\ncalculating total restraint energy and forces:'
        print '>>> energy,gradients = rstTest.EnergyAndGradients(crds)'
        e,g = rstTest.EnergyAndGradients(crds)
        print 'RESTRAINT  = %12.4f'%e
        print 'Forces (same format as forcedump.dat)'
        for i in range(0,len(g),3):
            print ' % 18.16e % 18.16e % 18.16e'%(-g[i+0],-g[i+1],-g[i+2])
    print '\nwriting a new restraint file to stdout:'
    print '>>> rstTest.WriteAmberRestraintFile(sys.stdout)'
    rstTest.WriteAmberRestraintFile(sys.stdout)

    import copy
    print '\nmaking a test copy and modifying it for test comparison'
    print '>>> rstTest2 = copy(rstTest)'
    rstTest2 = copy.deepcopy(rstTest)
    r0 = rstTest[0]._r[1] + 1.
    k0 = rstTest[0]._rk[0] + 10.
    print '>>> rstTest2.SetRestraintParameters(r0=[%f],k0=[%f])'%(r0,k0)
    rstTest2.SetRestraintParameters(r0=[r0],k0=[k0])
    rstTest2.PrintRestraintReport()
    print '>>> rstTest == rstTest2'
    print rstTest == rstTest2
    print '>>> rstTest != rstTest2'
    print rstTest != rstTest2
