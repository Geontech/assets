# This file is protected by Copyright. Please refer to the COPYRIGHT file
# distributed with this source distribution.
#
# This file is part of REDHAWK.
#
# REDHAWK is free software: you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by the
# Free Software Foundation, either version 3 of the License, or (at your
# option) any later version.
#
# REDHAWK is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or
# FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License
# for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see http://www.gnu.org/licenses/.

import unittest
import nose
from ossie.utils import sb#, testing
import ossie.utils.testing
from ossie.utils.testing import PRFParser, SPDParser, SCDParser

import os, sys, time, inspect, random, copy, signal
from pprint import pprint as pp
from pprint import pformat as pf

from omniORB import any
from omniORB import CORBA

from ossie import properties
from ossie.cf import CF, CF__POA
from ossie.utils import uuid
#from ossie.cf import ExtendedCF
#from ossie.resource import usesport, providesport

from redhawk.frontendInterfaces import FRONTEND, FRONTEND__POA, TunerControl_idl
from bulkio.bulkioInterfaces import BULKIO, BULKIO__POA
from ossie.utils.bulkio import bulkio_data_helpers

DEBUG_LEVEL = 0
def set_debug_level(lvl=0):
    global DEBUG_LEVEL
    DEBUG_LEVEL = lvl
def get_debug_level():
    return DEBUG_LEVEL

# Define device under test below
IMPL_ID = None
def set_impl_id(id):
    global IMPL_ID
    IMPL_ID = id
def get_impl_id():
    return IMPL_ID

DEVICE_INFO = {'spd':None}
def set_device_info(dev_info):
    global DEVICE_INFO
    DEVICE_INFO = dev_info
    set_impl_id(DEVICE_INFO['impl_id'])
def get_device_info():
    return DEVICE_INFO

class FrontendTunerTests(unittest.TestCase):
    ''' FrontEnd device compatibility tests
        Define DUT using the global DEVICE_INFO dict
        Customize deviceStartup function if your device has special start up requirements
        Customize deviceShutdown function if your device has special shut down requirements
    '''
    
    dut = None
    dut_ref = None
    device_discovery = {'TX':0, 'RX':0, 'CHANNELIZER':0, 'DDC':0, 'RX_DIGITIZER':0,
                        'RX_DIGITIZER_CHANNELIZER':0, 'UNKNOWN':0}
    testReport = []
    testReportStats = {}
    
    # mapping of required/optional frontend tuner status elements and the allowable data types
    FE_tuner_status_fields_req = {'FRONTEND::tuner_status::tuner_type':[str],
                                  'FRONTEND::tuner_status::allocation_id_csv':[str],
                                  'FRONTEND::tuner_status::center_frequency':[float],
                                  'FRONTEND::tuner_status::bandwidth':[float],
                                  'FRONTEND::tuner_status::sample_rate':[float],
                                  'FRONTEND::tuner_status::group_id':[str],
                                  'FRONTEND::tuner_status::rf_flow_id':[str],
                                  'FRONTEND::tuner_status::enabled':[bool]}
    FE_tuner_status_fields_opt = {'FRONTEND::tuner_status::bandwidth_tolerance':[float],
                                  'FRONTEND::tuner_status::sample_rate_tolerance':[float],
                                  'FRONTEND::tuner_status::complex':[bool],
                                  'FRONTEND::tuner_status::gain':[float],
                                  'FRONTEND::tuner_status::agc':[bool],
                                  'FRONTEND::tuner_status::valid':[bool],
                                  'FRONTEND::tuner_status::available_frequency':[str],
                                  'FRONTEND::tuner_status::available_bandwidth':[str],
                                  'FRONTEND::tuner_status::available_gain':[str],
                                  'FRONTEND::tuner_status::available_sample_rate':[str],
                                  'FRONTEND::tuner_status::reference_source':[int,long],
                                  'FRONTEND::tuner_status::output_format':[str],
                                  'FRONTEND::tuner_status::output_multicast':[str],
                                  'FRONTEND::tuner_status::output_vlan':[int,long],
                                  'FRONTEND::tuner_status::output_port':[int,long],
                                  'FRONTEND::tuner_status::decimation':[int,long],
                                  'FRONTEND::tuner_status::tuner_number':[int,long]}
    
    # get lists of all methods/functions defined in digital tuner idl
    digital_tuner_idl = filter(lambda x: x[0]!='_', dir(TunerControl_idl._0_FRONTEND._objref_DigitalTuner))
    # In future, could also do this:
    #import frontend
    #digital_tuner_idl = filter(lambda x: x[0]!='_', dir(frontend.InDigitalTunerPort))
    
    # map data types to DataSink port names
    port_map = {'dataShort':'shortIn',
                'dataFloat':'floatIn',
                'dataUlong':'uLongIn',
                'dataDouble':'doubleIn',
                'dataUshort':'ushortIn',
                'dataLong':'longIn',
                'dataUlongLong':'ulonglongIn',
                'dataLongLong':'longlongIn',
                'dataOctet':'octetIn',
                'dataXML':'xmlIn',
                'dataChar':'charIn',
                'dataFile':'fileIn'}

    from ossie.cf import CF
    from omniORB import any

    @classmethod
    def _query(cls, props=tuple() ):
        pl = [CF.DataType( id=p, value=any.to_any(None)) for p in props ]
        qr = cls.dut.query( pl )
        return ossie.properties.props_to_dict(qr)
    
    @classmethod
    def devicePreLaunch(self):
        pass
    @classmethod
    def devicePostLaunch(self):
        pass
    
    @classmethod
    def devicePreRelease(self):
        pass
    @classmethod
    def devicePostRelease(self):
        pass

    @classmethod
    def getToBasicState(self, execparams={}, configure={}, initialize=True):
        ''' Function used to launch device before each test case
            With no arguments, uses execparams defined in global DEVICE_INFO['execparams'] dict,
            configures props with values from prf, and initializes device.
            If specified, execparams overrides those specified in DEVICE_INFO dict, and configure
            overrides those specified in the prf.
            Add special start-up commands for your device to deviceStartup() function
        '''
        if not execparams:
            #execparams = self.getPropertySet(kinds=('execparam',), modes=('readwrite', 'writeonly'), includeNil=False)
            execparams = getPropertySet(DEVICE_INFO['spd'],kinds=('execparam',), modes=('readwrite', 'writeonly'), includeNil=False)
            execparams = dict([(x.id, any.from_any(x.value)) for x in execparams])
            execparams['DEBUG_LEVEL'] = DEBUG_LEVEL
            #Add custom execparams here
            for param,val in DEVICE_INFO['execparams'].items():
                execparams[param] = val
        
        #Add custom configure here
        for param,val in DEVICE_INFO['configure'].items():
            configure[param] = val
                
        ### device-specific pre-launch commands
        self.devicePreLaunch()
        
        print 'Launching device --',DEVICE_INFO['spd']
        print '\texecparams:',str(execparams)
        print '\tconfigure:',str(configure)
        print '\tinitialize:',str(initialize)

        try:
            # new method, use in versions >= 1.9
            self.dut = sb.launch(DEVICE_INFO['spd'],execparams=execparams,configure=configure,initialize=initialize,impl=IMPL_ID)
        except:
            # deprecated, use in 1.8.x versions
            self.dut = sb.Component(DEVICE_INFO['spd'],execparams=execparams,configure=configure,initialize=initialize,impl=IMPL_ID)
        
        self.dut_ref = self.dut.ref._narrow(CF.Device)

        ### device-specific post-launch commands
        self.devicePostLaunch()

    @classmethod
    def getToShutdownState(self):
        ''' Function used to release device after each test case
            Add special shut-down commands for your device to deviceShutdown() function
        '''
        
        ### device-specific pre-release commands
        self.devicePreRelease()
        
        if self.dut_ref:
            self.dut_ref = None
        if self.dut:
            self.dut.releaseObject()
            self.dut = None
            
        ### device-specific post-release commands
        self.devicePostRelease()
    
    @classmethod
    def setUpClass(self):
        
        self.spd_file = DEVICE_INFO['spd']
        self.spd = SPDParser.parse(self.spd_file)
        
        try:
            self.prf_file = self.spd.get_propertyfile().get_localfile().get_name()
            if (self.prf_file[0] != '/'):
                self.prf_file = os.path.join(os.path.dirname(self.spd_file), self.prf_file)
            self.prf = PRFParser.parse(self.prf_file)
        except:
            self.prf_file = None
            self.prf = None
        
        self.scd_file = self.spd.get_descriptor().get_localfile().get_name()
        if (self.scd_file[0] != '/'):
            self.scd_file = os.path.join(os.path.dirname(self.spd_file), self.scd_file)
        self.scd = SCDParser.parse(self.scd_file)

        # create a map between prop ids and names
        #if self.prf:
        #    self._props = prop_helpers.getPropNameDict(self.prf)
            
        self.testReport = ['\nDiscovering Tuner Types']
        self.getToBasicState()
        
        #Count # of each tuner type
        props = self.dut.query([])
        props = properties.props_to_dict(props)
        for tuner in props['FRONTEND::tuner_status']:
            if tuner['FRONTEND::tuner_status::tuner_type'] in self.device_discovery.keys():
                self.device_discovery[tuner['FRONTEND::tuner_status::tuner_type']] += 1
            else:
                self.device_discovery['UNKNOWN'] += 1
                
        for k,v in self.device_discovery.items():
            if v > 0:
                self.testReport.append('  Found %s %s'%(v,k))
                
        self.getToShutdownState()
        self.testReport.append('Completed discovery')

        # Override functions if necessary
        if 'tuner_gen' in DEVICE_INFO:
            generateTunerRequest=DEVICE_INFO['tuner_gen']
    
    def setUp(self):
        
        signal.signal(signal.SIGINT, self.tearDown)
        signal.signal(signal.SIGTERM, self.tearDown)
        signal.signal(signal.SIGQUIT, self.tearDown)

        self.getToBasicState()       
            
    def tearDown(self):
        self.getToShutdownState()
        #self.testReport.append('\n%s - STOP'%test_name)
        #ossie.utils.testing.ScaComponentTestCase.tearDown(self)
    
    @classmethod
    def tearDownClass(self):
        self.testReport.append('\nFRONTEND Test - Completed')
        for line in self.testReport:
            print >> sys.stderr, line
            
        print >> sys.stderr, '\nReport Statistics:'
        MAX_LHS_WIDTH=40
        MIN_SEPARATION=5
        total_nonsilent_checks=0
        for key in sorted(self.testReportStats.keys()):
            if key == 'Total checks made':
                continue
            total_nonsilent_checks+=self.testReportStats[key]
            print >> sys.stderr, '  ',key[:MAX_LHS_WIDTH], '.'*(MIN_SEPARATION+MAX_LHS_WIDTH-len(key[:MAX_LHS_WIDTH])), self.testReportStats[key]
        if 'Total checks made' not in self.testReportStats:
            self.testReportStats['Total checks made'] = 0
        key='Checks with silent results'
        total_silent_checks=self.testReportStats['Total checks made']-total_nonsilent_checks
        print >> sys.stderr, '  ',key[:MAX_LHS_WIDTH], '.'*(MIN_SEPARATION+MAX_LHS_WIDTH-len(key[:MAX_LHS_WIDTH])), total_silent_checks
        key='Total checks made'
        print >> sys.stderr, '  ',key[:MAX_LHS_WIDTH], '.'*(MIN_SEPARATION+MAX_LHS_WIDTH-len(key[:MAX_LHS_WIDTH])), self.testReportStats[key]
        
        #self.printTestReport() 
        
    def skipTest(self, msg=None, silent=False):
        if msg == None:
            msg = 'Skipping test %s'%(self.id().split('.')[-1])
        if not silent:
            self.testReport.append(msg)
        raise nose.SkipTest
    
    def attachChanInput(self):
        pass
    
    def detachChanInput(self):
        pass
    
    def testFRONTEND_6(self):
        ''' TX 0 - Not Implemented
        '''
        self.testReport.append('\nFRONTEND Test 6 - TX - Not implemented!')
        #self.testReport.append('\nFRONTEND Test 6 - TX')
        #self.testReport.append('\nFRONTEND Test 6 - Completed')
        
    def testFRONTEND_1_1(self):
        ''' ALL 1.1 Verify device_kind property
        '''
        props = self.dut.query([])
        props = properties.props_to_dict(props)
        #pp(props)
        self.check(props.has_key('DCE:cdc5ee18-7ceb-4ae6-bf4c-31f983179b4d'), True, 'Has device_kind property')
        self.check(props['DCE:cdc5ee18-7ceb-4ae6-bf4c-31f983179b4d'], 'FRONTEND::TUNER', 'device_kind = FRONTEND::TUNER')
        
    def testFRONTEND_1_2(self):
        ''' ALL 1.2 Verify that there is a device_model property
        '''
        props = self.dut.query([])
        props = properties.props_to_dict(props)
        self.check(props.has_key('DCE:0f99b2e4-9903-4631-9846-ff349d18ecfb'), True, 'Has device_model property')
        
    def testFRONTEND_1_3(self):
        ''' ALL 1.3 Verify that there is a FRONTEND Status property
        '''
        props = self.dut.query([])
        props = properties.props_to_dict(props)
        self.check(props.has_key('FRONTEND::tuner_status'), True, 'Has tuner_status property')
        # check for required fields
        #pp(props['FRONTEND::tuner_status'])
        if (len(props['FRONTEND::tuner_status']) == 0):
                print '\nERROR - tuner_status is empty. Check that the unit test is configured to reach the target device hardware.\n'
                self.check(False,True,'\nERROR - tuner_status is empty. Check that the unit test is configured to reach the target device hardware.')
                
        success = True
        for field in self.FE_tuner_status_fields_req:
            if not self.check(props['FRONTEND::tuner_status'][-1].has_key(field), True, 'tuner_status has %s required field'%field):
                success = False
        if not success:
            self.check(False,True,'\nERROR - tuner_status does not have all required fields.')
            
        
    def testFRONTEND_1_4(self):
        ''' ALL 1.4 Verify there is a tuner port
        '''
        #Attempt to get both ports and compare if None, then xor (^) the boolean result
        reason = 'both'
        try:
            DigitalTuner = self.dut.getPort('DigitalTuner_in')
        except:
            DigitalTuner= None
            reason = 'analog'
        try:
            AnalogTuner = self.dut.getPort('AnalogTuner_in')
        except:
            AnalogTuner = None
            reason = 'digital'
        if (DigitalTuner==None) and (AnalogTuner==None):
            reason = 'none'
        self.check( (DigitalTuner== None)^(AnalogTuner== None), True, 'Has an analog or digital tuner input port (%s)'%reason)   
        
    
        
    def testFRONTEND_3_1_1a(self):
        ''' RX_DIG 1.1a Allocate a single tuner (first)
        '''
        t1 = generateTunerRequest(idx=0)
        t1Alloc = generateTunerAlloc(t1)
        if not self.check(self.dut_ref.allocateCapacity(t1Alloc), True, 'Can allocate single RX_DIGITIZER') and DEBUG_LEVEL >= 4:
            # Do some DEBUG
            print 'RX_DIG 1.1a FAILURE - Can allocate single RX_DIGITIZER'
            pp(t1)
            pp(t1Alloc)
        
        # Deallocate the tuner
        error = False
        try:
            self.dut_ref.deallocateCapacity(t1Alloc)
        except:
            error = True
        self.check(error, False, 'Deallocated RX_DIGITIZER without error')
        
    def testFRONTEND_3_1_1b(self):
        ''' RX_DIG 1.1b Allocate a single tuner (last)
        '''
        t1 = generateTunerRequest(idx=self.device_discovery['RX_DIGITIZER']-1)
        t1Alloc = generateTunerAlloc(t1)
        if not self.check(self.dut_ref.allocateCapacity(t1Alloc), True, 'Can allocate single RX_DIGITIZER') and DEBUG_LEVEL >= 4:
            # Do some DEBUG
            print 'RX_DIG 1.1b FAILURE - Can allocate single RX_DIGITIZER'
            pp(t1)
            pp(t1Alloc)
        
        # Deallocate the tuner
        error = False
        try:
            self.dut_ref.deallocateCapacity(t1Alloc)
        except:
            error = True
        self.check(error, False, 'Deallocated RX_DIGITIZER without error')
        
    def testFRONTEND_3_1_2(self): 
        ''' RX_DIG 1.2 Allocate to max tuners
        '''
        ts = []
        for t in range(0,self.device_discovery['RX_DIGITIZER']):
            ts.append(generateTunerRequest(idx=t))
            tAlloc = generateTunerAlloc(ts[-1])
            if not self.check(self.dut_ref.allocateCapacity(tAlloc), True, 'Allocating RX_DIGITIZER number: %s'%(t), silentSuccess=True) and DEBUG_LEVEL >= 4:
                # Do some DEBUG
                print 'RX_DIG 1.2 FAILURE - Allocating RX_DIGITIZER number: %s'%(t)
                pp(ts)
                pp(tAlloc)
        self.check(True, True, 'Allocated to max RX_DIGITIZERs')
        
        # deallocate everything     
        error = False   
        for t in ts:
            try:
                tAlloc = generateTunerAlloc(t)
                self.dut_ref.deallocateCapacity(tAlloc)
            except:
                error = True
        self.check(error, False, 'Deallocated all RX_DIGITIZER tuners')
        
    def testFRONTEND_3_1_3(self): 
        ''' RX_DIG 1.3 Verify over-allocation failure
        '''
        
        # Allocate to max tuners
        ts = []
        for t in range(0,self.device_discovery['RX_DIGITIZER']):
            ts.append(generateTunerRequest(idx=t))
            tAlloc = generateTunerAlloc(ts[-1])
            if not self.check(self.dut_ref.allocateCapacity(tAlloc), True, 'Allocating RX_DIGITIZER number: %s'%(t), silentSuccess=True) and DEBUG_LEVEL >= 4:
                # Do some DEBUG
                print 'RX_DIG 1.3 FAILURE - Allocating RX_DIGITIZER number: %s'%(t)
                pp(ts)
                pp(tAlloc)
        self.check(True, True, 'Allocated to max RX_DIGITIZERs')
        
        # Verify over-allocation failure
        over_t = generateTunerRequest()
        over_tAlloc = generateTunerAlloc(over_t)
        if not self.check(self.dut_ref.allocateCapacity(over_tAlloc), False, 'Over-allocate RX_DIGITIZER check') and DEBUG_LEVEL >= 4:
            # Do some DEBUG
            print 'RX_DIG 1.3 FAILURE - Over-allocate RX_DIGITIZER check'
            pp(ts)
            pp(over_t)
            pp(over_tAlloc)
        
        try:
            self.dut_ref.deallocateCapacity(over_tAlloc)
        except:
            # It's fine if this fails b/c the alloc should have failed, but just in case
            pass
        
        # deallocate everything        
        error = False   
        for t in ts:
            try:
                tAlloc = generateTunerAlloc(t)
                self.dut_ref.deallocateCapacity(tAlloc)
            except:
                error = True
        self.check(error, False, 'Deallocated all RX_DIGITIZER tuners')
        
    def testFRONTEND_3_2_01(self):
        ''' RX_DIG 2.1 Verify InvalidCapacityException on repeat Alloc ID
        '''
        ttype = 'RX_DIGITIZER'
        tuner = generateTunerRequest()
        alloc_id = tuner['ALLOC_ID']
        tAlloc = generateTunerAlloc(tuner)
        if not self.check(self.dut_ref.allocateCapacity(tAlloc), True, 'Allocate single %s with alloc id: %s'%(ttype,alloc_id)) and DEBUG_LEVEL >= 4:
            # Do some DEBUG
            print 'RX_DIG 2.1 FAILURE - Allocate single %s with alloc id: %s'%(ttype,alloc_id)
            pp(tuner)
            pp(tAlloc)
        try:
            retval = self.dut_ref.allocateCapacity(tAlloc)
        except CF.Device.InvalidCapacity:
            self.check(True, True, 'Allocate second %s with same alloc id check (produces InvalidCapacity exception)'%(ttype))
        except Exception, e:
            self.check(False, True, 'Allocate second %s with same alloc id check (produces %s exception, should produce InvalidCapacity exception)'%(ttype,e.__class__.__name__))
        else:
            self.check(False, True, 'Allocate second %s with same alloc id check (returns %s, should produce InvalidCapacity exception)'%(ttype,retval))
        
        error = False
        try:
            self.dut_ref.deallocateCapacity(tAlloc) # this will deallocate the original successful allocation
        except:
            error = True
        self.check(error, False, 'Deallocated RX_DIGITIZER without error')
        
    def testFRONTEND_3_2_02(self):
        ''' RX_DIG 2.2 Verify InvalidCapacityException on malformed request (missing alloc ID)
        '''
        ttype = 'RX_DIGITIZER'
        tuner = generateTunerRequest()
        # First, check empty string
        tuner['ALLOC_ID'] = ''
        tAlloc = generateTunerAlloc(tuner)
        try:
            retval = self.dut_ref.allocateCapacity(tAlloc)
        except CF.Device.InvalidCapacity:
            self.check(True, True, 'Allocate %s with malformed request (alloc_id="") check (produces InvalidCapcity exception)'%(ttype))
        except Exception, e:
            self.check(False, True, 'Allocate %s with malformed request (alloc_id="") check (produces %s exception, should produce InvalidCapacity exception)'%(ttype,e.__class__.__name__))
        else:
            self.check(False, True, 'Allocate %s with malformed request (alloc_id="") check (returns %s, should produce InvalidCapacity exception)'%(ttype,retval))
            
    def testFRONTEND_3_2_03(self):
        ''' RX_DIG 2.3 Verify InvalidCapacityException on malformed request (missing alloc ID)
        '''
        ttype = 'RX_DIGITIZER'
        tuner = generateTunerRequest()
        # now try None
        tuner['ALLOC_ID'] = None
        tAlloc = generateTunerAlloc(tuner)
        try:
            retval = self.dut_ref.allocateCapacity(tAlloc)
        except CF.Device.InvalidCapacity:
            self.check(True, True, 'Allocate %s with malformed request (alloc_id=None) check (produces InvalidCapcity exception)'%(ttype))
        except Exception, e:
            self.check(False, True, 'Allocate %s with malformed request (alloc_id=None) check (produces %s exception, should produce InvalidCapacity exception)'%(ttype,e.__class__.__name__))
        else:
            self.check(False, True, 'Allocate %s with malformed request (alloc_id=None) check (returns %s, should produce InvalidCapacity exception)'%(ttype,retval))
    
    def testFRONTEND_3_2_04(self):
        ''' RX_DIG 2.4 Verify failure on alloc with invalid group id (generate new uuid)
        '''
        ttype = 'RX_DIGITIZER'
        tuner = generateTunerRequest()
        tuner['GROUP_ID'] = str(uuid.uuid4())
        tAlloc = generateTunerAlloc(tuner)
        try:
            retval = self.dut_ref.allocateCapacity(tAlloc)
        except Exception, e:
            self.check(False, True, 'Allocate %s with invalid GROUP_ID check (produces %s exception, should return False)'%(ttype,e.__class__.__name__))
        else:
            self.check(False, retval, 'Allocate %s with invalid GROUP_ID check'%(ttype))
        
    def testFRONTEND_3_2_05(self):
        ''' RX_DIG 2.5 Verify failure on alloc with invalid rf flow id (generate new uuid)
        '''
        ttype = 'RX_DIGITIZER'
        tuner = generateTunerRequest()
        tuner['RF_FLOW_ID'] = str(uuid.uuid4())
        tAlloc = generateTunerAlloc(tuner)
        try:
            retval = self.dut_ref.allocateCapacity(tAlloc)
        except Exception, e:
            self.check(False, True, 'Allocate %s with invalid RF_FLOW_ID check (produces %s exception, should return False)'%(ttype,e.__class__.__name__))
        else:
            self.check(False, retval, 'Allocate %s with invalid RF_FLOW_ID check'%(ttype))
        
    def testFRONTEND_3_2_06(self):
        ''' RX_DIG 2.6 Allocate Listener via listener struct
        '''
        tuner = generateTunerRequest()
        ttype='RX_DIGITIZER'
        tAlloc = generateTunerAlloc(tuner)
        #self.dut_ref.allocateCapacity(tAlloc)
        if not self.check(self.dut_ref.allocateCapacity(tAlloc), True, 'Allocate controller %s'%(ttype)) and DEBUG_LEVEL >= 4:
            # Do some DEBUG
            print 'RX_DIG 2.6 FAILURE - Allocate controller %s'%(ttype)
            pp(tuner)
            pp(tAlloc)
        
        tListener = generateListenerRequest(tuner)
        tListenerAlloc = generateListenerAlloc(tListener)
        if not self.check(self.dut_ref.allocateCapacity(tListenerAlloc), True, 'Allocate listener %s using listener allocation struct'%(ttype)) and DEBUG_LEVEL >= 4:
            # Do some DEBUG
            print 'RX_DIG 2.6 FAILURE - Allocate listener %s using listener allocation struct'%(ttype)
            pp(tuner)
            pp(tAlloc)
            pp(tListener)
            pp(tListenerAlloc)
        
        print "DEBUG -- done with allocations, now time to deallocate"
        
        # Deallocate listener using listener allocation struct
        try:
            self.dut_ref.deallocateCapacity(tListenerAlloc)
        except Exception,e:
            self.check(False, True, 'Deallocated listener %s using listener allocation struct without error'%(ttype))
        else:
            self.check(True, True, 'Deallocated listener %s using listener allocation struct without error'%(ttype))
            
        #print "DEBUG -- done with deallocation of listener, now time to deallocate the controller"
        try:
            self.dut_ref.deallocateCapacity(tAlloc)
        except Exception,e:
            self.check(False, True, 'Deallocated controller %s using controller allocation struct without error'%(ttype))
        else:
            self.check(True, True, 'Deallocated controller %s using controller allocation struct without error'%(ttype))
        
    def testFRONTEND_3_2_07(self):
        ''' RX_DIG 2.7 Allocate Listener via tuner allocation struct
        '''
        tuner = generateTunerRequest()
        ttype='RX_DIGITIZER'
        tAlloc = generateTunerAlloc(tuner)
        if not self.dut_ref.allocateCapacity(tAlloc) and DEBUG_LEVEL >= 4:
            # Do some DEBUG
            print 'RX_DIG 2.7 FAILURE - Allocate controller %s'%(ttype)
            pp(tuner)
            pp(tAlloc)
        
        tunerStatusProp =  self._getTunerStatusProp(tuner['ALLOC_ID'])
        tListener = copy.deepcopy(tuner)
        tListener['ALLOC_ID'] = str(uuid.uuid4())
        tListener['CONTROL'] = False
        tListener['CF'] = tunerStatusProp['FRONTEND::tuner_status::center_frequency']
        tListener['BW'] = tunerStatusProp['FRONTEND::tuner_status::bandwidth']
        tListenerAlloc = generateTunerAlloc(tListener)

        if not self.check(self.dut_ref.allocateCapacity(tListenerAlloc), True, 'Allocate listener %s using tuner allocation struct'%(ttype)) and DEBUG_LEVEL >= 4:
            # Do some DEBUG
            print 'RX_DIG 2.7 FAILURE - Allocate listener %s using tuner allocation struct'%(ttype)
            pp(tuner)
            pp(tAlloc)
            pp(tListener)
            pp(tListenerAlloc)
        
        # Deallocate listener using tuner allocation struct
        try:
            self.dut_ref.deallocateCapacity(tListenerAlloc)
        except Exception,e:
            self.check(False, True, 'Deallocated listener %s using tuner allocation struct without error'%(ttype))
        else:
            self.check(True, True, 'Deallocated listener %s using tuner allocation struct without error'%(ttype))
        try:
            self.dut_ref.deallocateCapacity(tAlloc)
        except Exception,e:
            self.check(False, True, 'Deallocated controller %s using controller allocation struct without error'%(ttype))
        else:
            self.check(True, True, 'Deallocated controller %s using controller allocation struct without error'%(ttype))
        
    def testFRONTEND_3_2_08(self):
        ''' RX_DIG 2.8 Verify failure on listener alloc w/o matching existing alloc id
        '''
        tuner = generateTunerRequest()
        ttype='RX_DIGITIZER'
        tAlloc = generateTunerAlloc(tuner)
        if not self.dut_ref.allocateCapacity(tAlloc) and DEBUG_LEVEL >= 4:
            # Do some DEBUG
            print 'RX_DIG 2.8 FAILURE - Controller allocation'
            pp(tuner)
            pp(tAlloc)
        tListener = generateListenerRequest(tuner)
        tListener['ALLOC_ID'] = str(uuid.uuid4())
        tListenerAlloc = generateListenerAlloc(tListener)
        if not self.check(self.dut_ref.allocateCapacity(tListenerAlloc), False, 'Allocate listener %s using listener allocation struct with bad allocation id check'%(ttype)) and DEBUG_LEVEL >= 4:
            # Do some DEBUG
            print 'RX_DIG 2.8 FAILURE - Allocate listener %s using listener allocation struct with bad allocation id check'%(ttype)
            pp(tuner)
            pp(tAlloc)
            pp(tListener)
            pp(tListenerAlloc)
        try:
            self.dut_ref.deallocateCapacity(tAlloc)
            self.dut_ref.deallocateCapacity(tListenerAlloc)
        except:
            pass # Don't care if pass/fail in this test
        
    def testFRONTEND_3_2_09(self):
        ''' RX_DIG 2.9 Verify failure on listener alloc w/o suitable existing channel (bad freq)
        '''
        tuner = generateTunerRequest()
        ttype='RX_DIGITIZER'
        tAlloc = generateTunerAlloc(tuner)
        self.dut_ref.allocateCapacity(tAlloc)
        tListener = copy.deepcopy(tuner)
        tListener['ALLOC_ID'] = str(uuid.uuid4())
        tListener['CF'] = tuner['CF'] * 2.0
        #tListener['BW'] = tuner['BW'] * 2.0
        tListener['SR'] = tuner['SR'] * 2.0
        #rdListener = generateTunerRequest()
        tListener['CONTROL'] = False
        tListenerAlloc = generateTunerAlloc(tListener)
        self.check(self.dut_ref.allocateCapacity(tListenerAlloc), False, 'Allocate listener %s using tuner allocation struct without suitable controller %s check'%(ttype,ttype))
        try:
            self.dut_ref.deallocateCapacity(tAlloc)
            self.dut_ref.deallocateCapacity(tListenerAlloc)
        except:
            pass # Don't care if pass/fail in this test
        
    def testFRONTEND_3_2_10(self):
        ''' RX_DIG 2.10 Verify listener allocations are deallocated following deallocation of controlling allocation
        '''
        tuner = generateTunerRequest()
        ttype='RX_DIGITIZER'
        tAlloc = generateTunerAlloc(tuner)
        self.dut_ref.allocateCapacity(tAlloc)
        tListener = generateListenerRequest(tuner)
        tListenerAlloc = generateListenerAlloc(tListener)
        self.check(self.dut_ref.allocateCapacity(tListenerAlloc), True, 'Allocate listener %s using listener allocation struct'%(ttype))
        try:
            self.dut_ref.deallocateCapacity(tAlloc)
        except Exception, e:
            self.check(False, True, 'Deallocated controller %s which has a listener allocation'%(ttype))
        else:
            self.check(True, True, 'Deallocated controller %s which has a listener allocation'%(ttype))
        has_listener = self._tunerStatusHasAllocId(tListener['LISTENER_ID'])
        self.check(has_listener, False, 'Listener %s deallocated  as result of controller %s deallocation'%(ttype,ttype))
        
    def testFRONTEND_3_2_11(self):
        ''' RX_DIG 2.11 allocate below minimum center frequency
        '''
        tuner = generateTunerRequest()
        ttype='RX_DIGITIZER'
        low = getMinCenterFreq()
        
        tuner['CF'] = float(int(low / 2.0))
        tAlloc = generateTunerAlloc(tuner)
        self.check(self.dut_ref.allocateCapacity(tAlloc), False, 'Allocate %s below lowest frequency in range(%s < %s)'%(ttype,tuner['CF'],low))
        
    def testFRONTEND_3_2_12(self):
        ''' RX_DIG 2.12 allocate above maximum center frequency
        '''
        tuner = generateTunerRequest()
        ttype='RX_DIGITIZER'
        high = getMaxCenterFreq()
        
        tuner['CF'] = float(high * 2.0)
        tAlloc = generateTunerAlloc(tuner)
        self.check(self.dut_ref.allocateCapacity(tAlloc), False, 'Allocate %s above highest frequency in range(%s > %s)'%(ttype,tuner['CF'],high))
        
    def testFRONTEND_3_2_13a(self):
        ''' RX_DIG 2.13a allocate at minimum center frequency
        '''
        tuner = generateTunerRequest()
        ttype='RX_DIGITIZER'
        low=getMinCenterFreq()
        
        tuner['CF'] = float(low)
        tAlloc = generateTunerAlloc(tuner)
        if not self.check(self.dut_ref.allocateCapacity(tAlloc), True, 'Allocate %s at lowest center frequency in range (%s)'%(ttype,low)) and DEBUG_LEVEL >= 4:
            # Do some DEBUG
            print 'RX_DIG 2.13a FAILURE'
            pp(tuner)
            pp(tAlloc)
        
    def testFRONTEND_3_2_13b(self):
        ''' RX_DIG 2.13b allocate just below minimum center frequency (partial coverage, should fail)
        '''
        tuner = generateTunerRequest()
        ttype='RX_DIGITIZER'
        low, sr, bw = getMinValues()
        for idx in range(self.device_discovery[ttype]):
            if getMinCenterFreq(idx) <= low:
                low = getMinCenterFreq(idx)
                bw = getMinBandwidth(idx)
                sr = getMinSampleRate(idx)
        bw_sr = max(bw,sr)
        
        tuner['CF'] = float(low-bw_sr/2.0)
        tuner['BW'] = float(bw)
        tuner['SR'] = float(sr)
        tAlloc = generateTunerAlloc(tuner)
        if not self.check(self.dut_ref.allocateCapacity(tAlloc), False, 'Check failure when allocating partially covered %s channel at lowest frequency in range (%s)'%(ttype,low)) and DEBUG_LEVEL >= 4:
            # Do some DEBUG
            print 'RX_DIG 2.13b FAILURE'
            pp(tuner)
            pp(tAlloc)

    def testFRONTEND_3_2_14a(self):
        ''' RX_DIG 2.14a allocate at maximum center frequency
        '''
        tuner = generateTunerRequest()
        ttype='RX_DIGITIZER'
        high = getMaxCenterFreq()

        tuner['CF'] = float(high)
        tAlloc = generateTunerAlloc(tuner)
        if not self.check(self.dut_ref.allocateCapacity(tAlloc), True, 'Allocate %s at highest center frequency in range(%s)'%(ttype,high)) and DEBUG_LEVEL >= 4:
            # Do some DEBUG
            print 'RX_DIG 2.14a FAILURE'
            pp(tuner)
            pp(tAlloc)

    def testFRONTEND_3_2_14b(self):
        ''' RX_DIG 2.14b allocate just above maximum center frequency (partial coverage, should fail)
        '''
        tuner = generateTunerRequest()
        ttype='RX_DIGITIZER'
        high, sr, bw = getMaxValues()
        for idx in range(self.device_discovery[ttype]):
            if getMaxCenterFreq(idx) >= high:
                high = getMaxCenterFreq(idx)
                bw = getMinBandwidth(idx)
                sr = getMinSampleRate(idx)
        bw_sr = max(bw,sr)

        tuner['CF'] = float(high+bw_sr/2.0)
        tuner['BW'] = float(bw)
        tuner['SR'] = float(sr)
        tAlloc = generateTunerAlloc(tuner)
        if not self.check(self.dut_ref.allocateCapacity(tAlloc), False, 'Check failure when allocating partially covered %s channel at highest frequency in range (%s)'%(ttype,high)) and DEBUG_LEVEL >= 4:
            # Do some DEBUG
            print 'RX_DIG 2.14b FAILURE'
            pp(tuner)
            pp(tAlloc)

    def testFRONTEND_3_2_15(self):
        ''' RX_DIG 2.15 allocate with bandwidth = 0 (succeed)
        '''
        ttype='RX_DIGITIZER'
        tuner = generateTunerRequest()
        
        tuner['BW'] = float(0.0)
        tAlloc = generateTunerAlloc(tuner)
        self.check(self.dut_ref.allocateCapacity(tAlloc), True, 'Allocate %s without specifying bandwidth (BW=0)'%(ttype))
        
    def testFRONTEND_3_2_16(self):
        ''' RX_DIG 2.16 allocate with sample rate = 0 (succeed)
        '''
        ttype='RX_DIGITIZER'
        tuner = generateTunerRequest()
        
        tuner['SR'] = float(0.0)
        tAlloc = generateTunerAlloc(tuner)
        self.check(self.dut_ref.allocateCapacity(tAlloc), True, 'Allocate %s without specifying sample rate (SR=0)'%(ttype))
        
    def testFRONTEND_3_2_17(self):
        ''' RX_DIG 2.17 allocate below minimum bandwidth capable (succeed)
        '''
        ttype='RX_DIGITIZER'
        tuner = generateTunerRequest()
        low = getMinBandwidth()
        
        tuner['BW'] = float(int(low / 1.333333333))
        tuner['SR'] = float(0)
        tAlloc = generateTunerAlloc(tuner)
        self.check(self.dut_ref.allocateCapacity(tAlloc), True, 'Allocate %s below lowest bandwidth in range(%s < %s)'%(ttype,tuner['BW'],low))
        
    def testFRONTEND_3_2_18(self):
        ''' RX_DIG 2.18 allocate above maximum bandwidth capable (fail)
        '''
        ttype='RX_DIGITIZER'
        tuner = generateTunerRequest()
        high = getMaxBandwidth()
        
        if self.check(high, 0, 'Upper bandwidth range set to 0, cannot test above highest bandwidth', silentFailure=True, successMsg='info'):
            return
        
        tuner['BW'] = float(high * 2.0)
        tuner['SR'] = float(0)
        tAlloc = generateTunerAlloc(tuner)
        failed = not self.check(self.dut_ref.allocateCapacity(tAlloc), False, 'Allocate %s above highest bandwidth in range(%s > %s)'%(ttype,tuner['BW'],high))
        # DEBUG
        '''
        if failed:
            print 'DEBUG - failed max bw alloc test'
            print 'alloc request:'
            pp(tuner)
            print 'tuner status:'
            pp(self._getTunerStatusProp(tuner['ALLOC_ID']))
            print 'END DEBUG - failed max bw alloc test'
        '''
        
    def testFRONTEND_3_2_19(self):
        ''' RX_DIG 2.19 allocate outside of bandwidth tolerance (fail)
        '''
        ttype='RX_DIGITIZER'
        tuner = generateTunerRequest()
        low = getMinBandwidth()
        
        if self.check(low, 0, 'Lower bandwidth range set to 0, cannot test tolerance below lowest bandwidth', silentFailure=True, successMsg='info'):
            return
        
        tuner['BW'] = float(int(low / 2.0))
        tuner['BW_TOLERANCE'] = float(10.0)
        tuner['SR'] = float(0)
        tAlloc = generateTunerAlloc(tuner)
        failed = not self.check(self.dut_ref.allocateCapacity(tAlloc), False, 'Allocate %s outside of bandwidth tolerance (%s + %s%% < %s'%(ttype,tuner['BW'],tuner['BW_TOLERANCE'],low))
        # DEBUG
        '''
        if failed:
            print 'DEBUG - failed outside bw tolerance test'
            print 'alloc request:'
            pp(tuner)
            print 'tuner status:'
            pp(self._getTunerStatusProp(tuner['ALLOC_ID']))
            print 'END DEBUG - failed outside bw tolerance test'
        '''
        
    def testFRONTEND_3_2_20(self):
        ''' RX_DIG 2.20 allocate below minimum sample rate capable (succeed)
        '''
        ttype='RX_DIGITIZER'
        tuner = generateTunerRequest()
        low = getMinSampleRate(idx=0)
        
        tuner['SR'] = float(int(low / 1.333333333))
        tuner['BW'] = float(0)
        tAlloc = generateTunerAlloc(tuner)
        self.check(self.dut_ref.allocateCapacity(tAlloc), True, 'Allocate %s below lowest sample rate in range(%s < %s)'%(ttype,tuner['SR'],low))
        
    def testFRONTEND_3_2_21(self):
        ''' RX_DIG 2.21 allocate above maximum sample rate capable (fail)
        '''
        ttype='RX_DIGITIZER'
        tuner = generateTunerRequest()
        high = getMaxSampleRate(idx=0, cap=False)
        
        tuner['SR'] = float(high * 2.0)
        tuner['BW'] = float(0)
        tAlloc = generateTunerAlloc(tuner)
        self.check(self.dut_ref.allocateCapacity(tAlloc), False, 'Allocate %s above highest sample rate in range(%s > %s)'%(ttype,tuner['SR'],high))
        
    def testFRONTEND_3_2_22(self):
        ''' RX_DIG 2.22 allocate outside of sample rate tolerance (fail)
        '''
        ttype='RX_DIGITIZER'
        tuner = generateTunerRequest()
        low = getMinSampleRate(idx=0)
        
        tuner['SR'] = float(int(low / 2.0))
        tuner['SR_TOLERANCE'] = float(10.0)
        tuner['BW'] = float(0)
        tAlloc = generateTunerAlloc(tuner)
        failed = not self.check(self.dut_ref.allocateCapacity(tAlloc), False, 'Allocate %s outside of sample rate tolerance (%s + %s%% < %s'%(ttype,tuner['SR'],tuner['SR_TOLERANCE'],low))
        # DEBUG
        '''
        if failed:
            print 'DEBUG - failed outside sr tolerance test'
            print 'alloc request:'
            pp(tuner)
            print 'tuner status:'
            pp(self._getTunerStatusProp(tuner['ALLOC_ID']))
            print 'END DEBUG - failed outside sr tolerance test'
        '''
        
    def testFRONTEND_3_3_01(self):
        ''' RX_DIG 3.1 Verify connection to Tuner port
        '''
        port_name = 'DigitalTuner_in'
        tuner_control = self.dut.getPort('DigitalTuner_in')
        tuner_control._narrow(FRONTEND.FrontendTuner)
        
        # Verify connection to Tuner port
        self.check(tuner_control != None, True, 'Can get %s port'%(port_name))
        self.check(CORBA.is_nil(tuner_control), False, 'Port reference is not nil')
        
    def testFRONTEND_3_3_02(self):
        ''' RX_DIG 3.2 Verify digital tuner port functions exist
        '''
        port_name = 'DigitalTuner_in'
        tuner_control = self.dut.getPort('DigitalTuner_in')
        tuner_control._narrow(FRONTEND.FrontendTuner)
        function_list = self.digital_tuner_idl
        
        for attr in function_list:
            try:
                self.check(callable(getattr(tuner_control,attr)), True, '%s port has function %s'%(port_name,attr))
            except AttributeError, e:
                self.check(False, True, '%s port has function %s'%(port_name,attr))
                
    def testFRONTEND_3_3_03(self):
        ''' RX_DIG 3.3 Verify digital tuner port getTunerType function
        '''
        port_name = 'DigitalTuner_in'
        tuner_control = self.dut.getPort('DigitalTuner_in')
        tuner_control._narrow(FRONTEND.FrontendTuner)
        controller = generateTunerRequest()

        # make allocations
        controller_id = controller['ALLOC_ID']
        controller_alloc = generateTunerAlloc(controller)
        self.check(self.dut_ref.allocateCapacity(controller_alloc),True,'ERROR -- could not allocate controller',throwOnFailure=True,silentSuccess=True)
        
        try:
            status_val = self._getTunerStatusProp(controller_id, 'FRONTEND::tuner_status::tuner_type')
        except KeyError:
            status_val = None
        
        try:
            resp = tuner_control.getTunerType(controller_id)
        except FRONTEND.NotSupportedException:
            self.check(True,True,'%s.getTunerType produces NotSupportedException'%(port_name))
        except Exception, e:
            self.check(True,False,'%s.getTunerType produces exception %s'%(port_name,e))
        else:
            self.check(type(resp), str, '%s.getTunerType has correct return type'%(port_name))
            self.check(resp in ['RX','TX','RX_DIGITIZER','CHANNELIZER','RX_DIGITIZER_CHANNELIZER','DDC'], True, '%s.getTunerType return value is within expected results'%(port_name))
            self.check(resp, 'RX_DIGITIZER', '%s.getTunerType return value is correct for RX_DIGITIZER'%(port_name))
            if status_val!=None:
                self.check(resp, status_val, '%s.getTunerType matches frontend tuner status prop'%(port_name))
                
            
    def testFRONTEND_3_3_04(self):
        ''' RX_DIG 3.4 Verify digital tuner port getTunerDeviceControl function w/ controller
        '''
        port_name = 'DigitalTuner_in'
        tuner_control = self.dut.getPort('DigitalTuner_in')
        tuner_control._narrow(FRONTEND.FrontendTuner)
        controller = generateTunerRequest()

        # make allocations
        controller_id = controller['ALLOC_ID']
        controller_alloc = generateTunerAlloc(controller)
        self.check(self.dut_ref.allocateCapacity(controller_alloc),True,'%s.getTunerDeviceControl(controller_id) ERROR -- could not allocate controller'%(port_name),throwOnFailure=True,silentSuccess=True)
            
        try:
            resp = tuner_control.getTunerDeviceControl(controller_id)
        except FRONTEND.NotSupportedException:
            self.check(True,True,'%s.getTunerDeviceControl(controller_id) produces NotSupportedException'%(port_name))
        except Exception, e:
            self.check(True,False,'%s.getTunerDeviceControl(controller_id) produces exception %s'%(port_name,e))
        else:
            self.check(type(resp), bool, '%s.getTunerDeviceControl(controller_id) has correct return type'%(port_name))
            self.check(resp in [True,False], True, '%s.getTunerDeviceControl(controller_id) return value is within expected results'%(port_name))
            self.check(resp, True, '%s.getTunerDeviceControl(controller_id) return True for controller alloc_id'%(port_name))
            
            
    def testFRONTEND_3_3_05(self):
        ''' RX_DIG 3.5 Verify digital tuner port getTunerDeviceControl function w/ listener
        '''
        port_name = 'DigitalTuner_in'
        tuner_control = self.dut.getPort('DigitalTuner_in')
        tuner_control._narrow(FRONTEND.FrontendTuner)
        
        controller = generateTunerRequest()
        pp(controller)
        listener = generateListenerRequest(controller)

        # make allocations
        controller_id = controller['ALLOC_ID']
        controller_alloc = generateTunerAlloc(controller)
        self.check(self.dut_ref.allocateCapacity(controller_alloc),True,'%s.getTunerDeviceControl(listener_id) ERROR -- could not allocate controller'%(port_name),throwOnFailure=True,silentSuccess=True)
        listener_id = listener['LISTENER_ID']
        listener_alloc = generateListenerAlloc(listener)
        self.check(self.dut_ref.allocateCapacity(listener_alloc),True,'%s.getTunerDeviceControl(listener_id) ERROR -- could not allocate listener'%(port_name),throwOnFailure=True,silentSuccess=True)
        
        try:
            resp = tuner_control.getTunerDeviceControl(listener_id)
        except FRONTEND.NotSupportedException:
            self.check(True,True,'%s.getTunerDeviceControl(listener_id) produces NotSupportedException'%(port_name))
        except Exception, e:
            self.check(True,False,'%s.getTunerDeviceControl(listener_id) produces exception %s'%(port_name,e))
        else:
            self.check(type(resp), bool, '%s.getTunerDeviceControl(listener_id) has correct return type'%(port_name))
            self.check(resp in [True,False], True, '%s.getTunerDeviceControl(listener_id) return value is within expected results'%(port_name))
            self.check(resp, False, '%s.getTunerDeviceControl(listener_id) returns False for listener alloc_id'%(port_name))
            
            
    def testFRONTEND_3_3_06(self):
        ''' RX_DIG 3.6 Verify digital tuner port getTunerGroupId function
        '''
        port_name = 'DigitalTuner_in'
        tuner_control = self.dut.getPort('DigitalTuner_in')
        tuner_control._narrow(FRONTEND.FrontendTuner)
        controller = generateTunerRequest()

        # make allocations
        controller_id = controller['ALLOC_ID']
        controller_alloc = generateTunerAlloc(controller)
        self.check(self.dut_ref.allocateCapacity(controller_alloc),True,'ERROR -- could not allocate controller',throwOnFailure=True,silentSuccess=True)
        
        try:
            status_val = self._getTunerStatusProp(controller_id, 'FRONTEND::tuner_status::group_id')
        except KeyError:
            status_val = None
        
        try:
            resp = tuner_control.getTunerGroupId(controller_id)
        except FRONTEND.NotSupportedException:
            self.check(True,True,'%s.getTunerGroupId produces NotSupportedException'%(port_name))
        except Exception, e:
            self.check(True,False,'%s.getTunerGroupId produces exception %s'%(port_name,e))
        else:
            self.check(type(resp), str, '%s.getTunerGroupId has correct return type'%(port_name))
            self.check(type(resp), str, '%s.getTunerGroupId return value is within expected results'%(port_name))
            if status_val!=None:
                self.check(resp, status_val, '%s.getTunerGroupId matches frontend tuner status prop'%(port_name))
            
            
    def testFRONTEND_3_3_07(self):
        ''' RX_DIG 3.7 Verify digital tuner port getTunerRfFlowId function
        '''
        port_name = 'DigitalTuner_in'
        tuner_control = self.dut.getPort('DigitalTuner_in')
        tuner_control._narrow(FRONTEND.FrontendTuner)
        controller = generateTunerRequest()

        # make allocations
        controller_id = controller['ALLOC_ID']
        controller_alloc = generateTunerAlloc(controller)
        self.check(self.dut_ref.allocateCapacity(controller_alloc),True,'ERROR -- could not allocate controller',throwOnFailure=True,silentSuccess=True)
        
        try:
            status_val = self._getTunerStatusProp(controller_id, 'FRONTEND::tuner_status::rf_flow_id')
        except KeyError:
            status_val = None
            
        try:
            resp = tuner_control.getTunerRfFlowId(controller_id)
        except FRONTEND.NotSupportedException:
            self.check(True,True,'%s.getTunerRfFlowId produces NotSupportedException'%(port_name))
        except Exception, e:
            self.check(True,False,'%s.getTunerRfFlowId produces exception %s'%(port_name,e))
        else:
            self.check(type(resp), str, '%s.getTunerRfFlowId has correct return type'%(port_name))
            self.check(type(resp), str, '%s.getTunerRfFlowId return value is within expected results'%(port_name))
            if status_val!=None:
                self.check(resp, status_val, '%s.getTunerRfFlowId matches frontend tuner status prop'%(port_name))
            
            
    def testFRONTEND_3_3_08(self):
        ''' RX_DIG 3.8 Verify digital tuner port getTunerCenterFrequency function
        '''
        port_name = 'DigitalTuner_in'
        tuner_control = self.dut.getPort('DigitalTuner_in')
        tuner_control._narrow(FRONTEND.FrontendTuner)
        controller = generateTunerRequest()

        # make allocations
        controller_id = controller['ALLOC_ID']
        controller_alloc = generateTunerAlloc(controller)
        self.check(self.dut_ref.allocateCapacity(controller_alloc),True,'ERROR -- could not allocate controller',throwOnFailure=True,silentSuccess=True)
            
        try:
            status_val = self._getTunerStatusProp(controller_id, 'FRONTEND::tuner_status::center_frequency')
        except KeyError:
            status_val = None
            
        try:
            resp = tuner_control.getTunerCenterFrequency(controller_id)
        except FRONTEND.NotSupportedException:
            self.check(True,True,'%s.getTunerCenterFrequency produces NotSupportedException'%(port_name))
        except Exception, e:
            self.check(True,False,'%s.getTunerCenterFrequency produces exception %s'%(port_name,e))
        else:
            self.check(type(resp), float, '%s.getTunerCenterFrequency has correct return type'%(port_name))
            self.check(resp >= 0.0, True, '%s.getTunerCenterFrequency return value is within expected results'%(port_name))
            if status_val!=None:
                self.checkAlmostEqual(resp, status_val, '%s.getTunerCenterFrequency matches frontend tuner status prop'%(port_name),places=0)
            
            
    def testFRONTEND_3_3_09(self):
        ''' RX_DIG 3.9 Verify digital tuner port getTunerBandwidth function
        '''
        port_name = 'DigitalTuner_in'
        tuner_control = self.dut.getPort('DigitalTuner_in')
        tuner_control._narrow(FRONTEND.FrontendTuner)
        controller = generateTunerRequest()

        # make allocations
        controller_id = controller['ALLOC_ID']
        controller_alloc = generateTunerAlloc(controller)
        self.check(self.dut_ref.allocateCapacity(controller_alloc),True,'ERROR -- could not allocate controller',throwOnFailure=True,silentSuccess=True)
            
        try:
            status_val = self._getTunerStatusProp(controller_id, 'FRONTEND::tuner_status::bandwidth')
        except KeyError:
            status_val = None
            
        # getTunerBandwidth
        # double: >= 0?
        try:
            resp = tuner_control.getTunerBandwidth(controller_id)
        except FRONTEND.NotSupportedException:
            self.check(True,True,'%s.getTunerBandwidth produces NotSupportedException'%(port_name))
        except Exception, e:
            self.check(True,False,'%s.getTunerBandwidth produces exception %s'%(port_name,e))
        else:
            self.check(type(resp), float, '%s.getTunerBandwidth has correct return type'%(port_name))
            self.check(resp >= 0.0, True, '%s.getTunerBandwidth return value is within expected results'%(port_name))
            if status_val!=None:
                self.checkAlmostEqual(resp, status_val, '%s.getTunerBandwidth matches frontend tuner status prop'%(port_name),places=0)
            
            
    def testFRONTEND_3_3_10(self):
        ''' RX_DIG 3.10 Verify digital tuner port getTunerOutputSampleRate function
        '''
        port_name = 'DigitalTuner_in'
        tuner_control = self.dut.getPort('DigitalTuner_in')
        tuner_control._narrow(FRONTEND.FrontendTuner)
        controller = generateTunerRequest()

        # make allocations
        controller_id = controller['ALLOC_ID']
        controller_alloc = generateTunerAlloc(controller)
        self.check(self.dut_ref.allocateCapacity(controller_alloc),True,'ERROR -- could not allocate controller',throwOnFailure=True,silentSuccess=True)
            
        try:
            status_val = self._getTunerStatusProp(controller_id, 'FRONTEND::tuner_status::sample_rate')
        except KeyError:
            status_val = None
        
        try:
            resp = tuner_control.getTunerOutputSampleRate(controller_id)
        except FRONTEND.NotSupportedException:
            self.check(True,True,'%s.getTunerOutputSampleRate produces NotSupportedException'%(port_name))
        except Exception, e:
            self.check(True,False,'%s.getTunerOutputSampleRate produces exception %s'%(port_name,e))
        else:
            self.check(type(resp), float, '%s.getTunerOutputSampleRate has correct return type'%(port_name))
            self.check(resp >= 0.0, True, '%s.getTunerOutputSampleRate return value is within expected results'%(port_name))
            if status_val!=None:
                self.checkAlmostEqual(resp, status_val, '%s.getTunerOutputSampleRate matches frontend tuner status prop'%(port_name),places=0)
            
            
    def testFRONTEND_3_3_11(self):
        ''' RX_DIG 3.11 Verify digital tuner port getTunerAgcEnable function
        '''
        port_name = 'DigitalTuner_in'
        tuner_control = self.dut.getPort('DigitalTuner_in')
        tuner_control._narrow(FRONTEND.FrontendTuner)
        controller = generateTunerRequest()

        # make allocations
        controller_id = controller['ALLOC_ID']
        controller_alloc = generateTunerAlloc(controller)
        self.check(self.dut_ref.allocateCapacity(controller_alloc),True,'ERROR -- could not allocate controller',throwOnFailure=True,silentSuccess=True)
            
        try:
            status_val = self._getTunerStatusProp(controller_id, 'FRONTEND::tuner_status::agc')
        except KeyError:
            status_val = None
            
        try:
            resp = tuner_control.getTunerAgcEnable(controller_id)
        except FRONTEND.NotSupportedException:
            self.check(True,True,'%s.getTunerAgcEnable produces NotSupportedException'%(port_name))
        except Exception, e:
            self.check(True,False,'%s.getTunerAgcEnable produces exception %s'%(port_name,e))
        else:
            self.check(type(resp), bool, '%s.getTunerAgcEnable has correct return type'%(port_name))
            self.check(resp in [True,False], True, '%s.getTunerAgcEnable return value is within expected results'%(port_name))
            if status_val!=None:
                self.check(resp, status_val, '%s.getTunerAgcEnable matches frontend tuner status prop'%(port_name))
            
            
    def testFRONTEND_3_3_12(self):
        ''' RX_DIG 3.12 Verify digital tuner port getTunerGain function
        '''
        port_name = 'DigitalTuner_in'
        tuner_control = self.dut.getPort('DigitalTuner_in')
        tuner_control._narrow(FRONTEND.FrontendTuner)
        controller = generateTunerRequest()

        # make allocations
        controller_id = controller['ALLOC_ID']
        controller_alloc = generateTunerAlloc(controller)
        self.check(self.dut_ref.allocateCapacity(controller_alloc),True,'ERROR -- could not allocate controller',throwOnFailure=True,silentSuccess=True)
            
        try:
            status_val = self._getTunerStatusProp(controller_id, 'FRONTEND::tuner_status::gain')
        except KeyError:
            status_val = None
            
        try:
            resp = tuner_control.getTunerGain(controller_id)
        except FRONTEND.NotSupportedException:
            self.check(True,True,'%s.getTunerGain produces NotSupportedException'%(port_name))
        except Exception, e:
            self.check(True,False,'%s.getTunerGain produces exception %s'%(port_name,e))
        else:
            self.check(type(resp), float, '%s.getTunerGain has correct return type'%(port_name))
            self.check(type(resp), float, '%s.getTunerGain return value is within expected results'%(port_name))
            if status_val!=None:
                self.checkAlmostEqual(resp, status_val, '%s.getTunerGain matches frontend tuner status prop'%(port_name),places=2)
            
            
    def testFRONTEND_3_3_13(self):
        ''' RX_DIG 3.13 Verify digital tuner port getTunerReferenceSource function
        '''
        port_name = 'DigitalTuner_in'
        tuner_control = self.dut.getPort('DigitalTuner_in')
        tuner_control._narrow(FRONTEND.FrontendTuner)
        controller = generateTunerRequest()

        # make allocations
        controller_id = controller['ALLOC_ID']
        controller_alloc = generateTunerAlloc(controller)
        self.check(self.dut_ref.allocateCapacity(controller_alloc),True,'ERROR -- could not allocate controller',throwOnFailure=True,silentSuccess=True)
            
        try:
            status_val = self._getTunerStatusProp(controller_id, 'FRONTEND::tuner_status::reference_source')
        except KeyError:
            status_val = None
            
        try:
            resp = tuner_control.getTunerReferenceSource(controller_id)
        except FRONTEND.NotSupportedException:
            self.check(True,True,'%s.getTunerReferenceSource produces NotSupportedException'%(port_name))
        except Exception, e:
            self.check(True,False,'%s.getTunerReferenceSource produces exception %s'%(port_name,e))
        else:
            self.check(type(resp) in [int,long], True, '%s.getTunerReferenceSource returns correct type'%(port_name))
            self.check(resp in [0,1], True, '%s.getTunerReferenceSource return value within expected results'%(port_name))
            if status_val!=None:
                self.check(resp, status_val, '%s.getTunerReferenceSource matches frontend tuner status prop'%(port_name))
            
            
    def testFRONTEND_3_3_14(self):
        ''' RX_DIG 3.14 Verify digital tuner port getTunerEnable function
        '''
        port_name = 'DigitalTuner_in'
        tuner_control = self.dut.getPort('DigitalTuner_in')
        tuner_control._narrow(FRONTEND.FrontendTuner)
        controller = generateTunerRequest()

        # make allocations
        controller_id = controller['ALLOC_ID']
        controller_alloc = generateTunerAlloc(controller)
        self.check(self.dut_ref.allocateCapacity(controller_alloc),True,'ERROR -- could not allocate controller',throwOnFailure=True,silentSuccess=True)
            
        try:
            status_val = self._getTunerStatusProp(controller_id, 'FRONTEND::tuner_status::enabled')
        except KeyError:
            status_val = None

        try:
            resp = tuner_control.getTunerEnable(controller_id)
        except FRONTEND.NotSupportedException:
            self.check(True,True,'%s.getTunerEnable produces NotSupportedException'%(port_name))
        except Exception, e:
            self.check(True,False,'%s.getTunerEnable produces exception %s'%(port_name,e))
        else:
            self.check(type(resp), bool, '%s.getTunerEnable has correct return type'%(port_name))
            self.check(resp in [True,False], True, '%s.getTunerEnable return value is within expected results'%(port_name))
            if status_val!=None:
                self.check(resp, status_val, '%s.getTunerEnable matches frontend tuner status prop'%(port_name))
            
            
    def testFRONTEND_3_3_15(self):
        ''' RX_DIG 3.15 Verify digital tuner port getTunerStatus function
        '''
        port_name = 'DigitalTuner_in'
        tuner_control = self.dut.getPort('DigitalTuner_in')
        tuner_control._narrow(FRONTEND.FrontendTuner)
        controller = generateTunerRequest()

        # make allocations
        controller_id = controller['ALLOC_ID']
        controller_alloc = generateTunerAlloc(controller)
        self.check(self.dut_ref.allocateCapacity(controller_alloc),True,'ERROR -- could not allocate controller',throwOnFailure=True,silentSuccess=True)
            
        try:
            status_val = self._getTunerStatusProp(controller_id)
        except KeyError:
            status_val = None
        props_type = type(properties.props_from_dict({}))
            
        try:
            resp = tuner_control.getTunerStatus(controller_id)
        except FRONTEND.NotSupportedException:
            self.check(True,True,'%s.getTunerStatus produces NotSupportedException'%(port_name))
        except Exception, e:
            self.check(True,False,'%s.getTunerStatus produces exception %s'%(port_name,e))
        else:
            self.check(type(resp), props_type, '%s.getTunerStatus has correct return type'%(port_name))
            self.check(type(resp), props_type, '%s.getTunerStatus return value is within expected results'%(port_name))
            resp = properties.props_to_dict(resp)
            #pp(resp)
            self.check(controller_id in resp['FRONTEND::tuner_status::allocation_id_csv'].split(','), True, '%s.getTunerStatus return value has correct tuner status for allocation ID requested'%(port_name))
            if status_val!=None:
                self.check(resp, status_val, '%s.getTunerStatus matches frontend tuner status prop'%(port_name))
            
        
        # Verify setter functions
        # for each of the following, do bounds checking in addition to simple setter checking
        # setTunerCenterFrequency
        # setTunerBandwidth
        # setTunerOutputSampleRate
        # setTunerGain
          
        # Verify in-bounds retune
            
    def testFRONTEND_3_3_16(self):
        ''' RX_DIG 3.16 Verify digital tuner port setTunerCenterFrequency function in-bounds retune
        '''
        port_name = 'DigitalTuner_in'
        tuner_control = self.dut.getPort('DigitalTuner_in')
        tuner_control._narrow(FRONTEND.FrontendTuner)
        controller = generateTunerRequest()

        # make allocations
        controller_id = controller['ALLOC_ID']
        controller_alloc = generateTunerAlloc(controller)
        self.check(self.dut_ref.allocateCapacity(controller_alloc),True,'ERROR -- could not allocate controller',throwOnFailure=True,silentSuccess=True)
        
        #check Center Freq: tune to min, max, then orig
        try:
            cf = tuner_control.getTunerCenterFrequency(controller_id)
        except FRONTEND.NotSupportedException:
            self.check(True,True,'%s.getTunerCenterFrequency produces NotSupportedException -- cannot verify setTunerCenterFrequency function'%(port_name), successMsg='info')
            try:
                tuner_control.setTunerCenterFrequency(controller_id, getMinCenterFreq(idx=0))
            except FRONTEND.NotSupportedException:
                self.check(True,True,'%s.setTunerCenterFrequency produces NotSupportedException'%(port_name))
            else:
                self.check(True,True,'%s.setTunerCenterFrequency executes without throwing exception'%(port_name))
        except Exception, e:
            self.check(False, True,'%s.getTunerCenterFrequency produces Exception -- cannot verify setTunerCenterFrequency function',failureMsg='WARN')
            try:
                tuner_control.setTunerCenterFrequency(controller_id, getMinCenterFreq(idx=0))
            except FRONTEND.NotSupportedException:
                self.check(True,True,'%s.setTunerCenterFrequency produces NotSupportedException'%(port_name))
            else:
                self.check(True,True,'%s.setTunerCenterFrequency executes without throwing exception'%(port_name))
        else:
            try:
                tuner_control.setTunerCenterFrequency(controller_id, getMinCenterFreq(idx=0))
            except FRONTEND.NotSupportedException:
                self.check(True,True,'%s.setTunerCenterFrequency produces NotSupportedException'%(port_name))
            except FRONTEND.BadParameterException, e:
                self.check(False, True,'In-bounds setting of frequency - set to minimum CF (%s) produces BadParameterException'%getMinCenterFreq(idx=0) )
                raise
            except FRONTEND.FrontendException, e:
                self.check(False, True,'In-bounds setting of frequency - set to minimum CF (%s) produces FrontendException'%getMinCenterFreq(idx=0) )
                raise
            except Exception, e:
                self.check(False, True,'In-bounds setting of frequency - set to minimum CF (%s) produces Exception'%getMinCenterFreq(idx=0))
                raise
            else:
                self.checkAlmostEqual(getMinCenterFreq(idx=0),tuner_control.getTunerCenterFrequency(controller_id),'In-bounds re-tune of frequency - tuned to minimum CF (%s)'%(getMinCenterFreq(idx=0)),places=0)
                tuner_control.setTunerCenterFrequency(controller_id, getMaxCenterFreq(idx=0))
                self.checkAlmostEqual(getMaxCenterFreq(idx=0),tuner_control.getTunerCenterFrequency(controller_id),'In-bounds re-tune of frequency - tuned to maximum CF (%s)'%(getMaxCenterFreq(idx=0)),places=0)
                tuner_control.setTunerCenterFrequency(controller_id, cf)
                self.checkAlmostEqual(cf,tuner_control.getTunerCenterFrequency(controller_id),'In-bounds re-tune of frequency - tuned back to original CF (%s)'%(cf),places=0)
            
            
    def testFRONTEND_3_3_17(self):
        ''' RX_DIG 3.17 Verify digital tuner port setTunerBandwidth function in-bounds retune
        '''
        port_name = 'DigitalTuner_in'
        tuner_control = self.dut.getPort('DigitalTuner_in')
        tuner_control._narrow(FRONTEND.FrontendTuner)
        controller = generateTunerRequest()

        # make allocations
        controller_id = controller['ALLOC_ID']
        controller_alloc = generateTunerAlloc(controller)
        self.check(self.dut_ref.allocateCapacity(controller_alloc),True,'ERROR -- could not allocate controller',throwOnFailure=True,silentSuccess=True)
                
        #Check Bandwidth: tune to min, max, then orig
        try:
            bw = tuner_control.getTunerBandwidth(controller_id)
        except FRONTEND.NotSupportedException:
            self.check(True,True,'%s.getTunerBandwidth produces NotSupportedException -- cannot verify setTunerBandwidth function'%(port_name), successMsg='info')
            try:
                tuner_control.setTunerBandwidth(controller_id, getMinBandwidth(idx=0))
            except FRONTEND.NotSupportedException:
                self.check(True,True,'%s.setTunerBandwidth produces NotSupportedException'%(port_name))
            else:
                self.check(True,True,'%s.setTunerBandwidth executes without throwing exception'%(port_name))
        except Exception, e:
            self.check(False, True,'%s.getTunerBandwidth produces Exception -- cannot verify setTunerBandwidth function',failureMsg='WARN')
            try:
                tuner_control.setTunerBandwidth(controller_id, getMinBandwidth(idx=0))
            except FRONTEND.NotSupportedException:
                self.check(True,True,'%s.setTunerBandwidth produces NotSupportedException'%(port_name))
            else:
                self.check(True,True,'%s.setTunerBandwidth executes without throwing exception'%(port_name))
        else:
            try:
                tuner_control.setTunerBandwidth(controller_id, getMinBandwidth(idx=0))
            except FRONTEND.NotSupportedException:
                self.check(True,True,'%s.setTunerBandwidth produces NotSupportedException'%(port_name))
            except FRONTEND.BadParameterException, e:
                self.check(False, True,'In-bounds setting of bandwidth - set to minimum BW (%s) produces BadParameterException'%getMinBandwidth(idx=0) )
                raise
            except FRONTEND.FrontendException, e:
                self.check(False, True,'In-bounds setting of bandwidth - set to minimum BW (%s) produces FrontendException'%getMinBandwidth(idx=0) )
                raise
            except Exception, e:
                self.check(False, True,'In-bounds setting of bandwidth - set to minimum BW (%s) produces Exception'%getMinBandwidth(idx=0))
                raise
            else:
                self.checkAlmostEqual(getMinBandwidth(idx=0),tuner_control.getTunerBandwidth(controller_id),'In-bounds re-tune of bandwidth - set to minimum BW (%s)'%getMinBandwidth(idx=0),places=0)
                tuner_control.setTunerBandwidth(controller_id, getMaxBandwidth(idx=0))
                self.checkAlmostEqual(getMaxBandwidth(idx=0),tuner_control.getTunerBandwidth(controller_id),'In-bounds re-tune of bandwidth - set to maximum BW (%s)'%getMaxBandwidth(idx=0),places=0)
                tuner_control.setTunerBandwidth(controller_id, bw)
                self.checkAlmostEqual(bw,tuner_control.getTunerBandwidth(controller_id),'In-bounds re-tune of bandwidth - set to original BW (%s)'%bw,places=0)

                
    def testFRONTEND_3_3_18(self):
        ''' RX_DIG 3.18 Verify digital tuner port setTunerOutputSampleRate function in-bounds retune
        '''
            
        port_name = 'DigitalTuner_in'
        tuner_control = self.dut.getPort('DigitalTuner_in')
        tuner_control._narrow(FRONTEND.FrontendTuner)
        controller = generateTunerRequest()

        # make allocations
        controller_id = controller['ALLOC_ID']
        controller_alloc = generateTunerAlloc(controller)
        self.check(self.dut_ref.allocateCapacity(controller_alloc),True,'ERROR -- could not allocate controller',throwOnFailure=True,silentSuccess=True)
            
        #Check SR: tune to min, max, then orig
        try:
            sr = tuner_control.getTunerOutputSampleRate(controller_id)
        except FRONTEND.NotSupportedException:
            self.check(True,True,'%s.getTunerOutputSampleRate produces NotSupportedException -- cannot verify setTunerOutputSampleRate function'%(port_name), successMsg='info')
            try:
                tuner_control.setTunerOutputSampleRate(controller_id, getMinSampleRate(idx=0))
            except FRONTEND.NotSupportedException:
                self.check(True,True,'%s.setTunerOutputSampleRate produces NotSupportedException'%(port_name))
            else:
                self.check(True,True,'%s.setTunerOutputSampleRate executes without throwing exception'%(port_name))
        except Exception, e:
            self.check(False, True,'%s.getTunerOutputSampleRate produces Exception -- cannot verify setTunerOutputSampleRate function',failureMsg='WARN')
            try:
                tuner_control.setTunerOutputSampleRate(controller_id, getMinSampleRate(idx=0))
            except FRONTEND.NotSupportedException:
                self.check(True,True,'%s.setTunerOutputSampleRate produces NotSupportedException'%(port_name))
            else:
                self.check(True,True,'%s.setTunerOutputSampleRate executes without throwing exception'%(port_name))
        else:
            try:
                tuner_control.setTunerOutputSampleRate(controller_id, getMinSampleRate(idx=0))
            except FRONTEND.NotSupportedException:
                self.check(True,True,'%s.setTunerOutputSampleRate produces NotSupportedException'%(port_name))
            except FRONTEND.BadParameterException, e:
                self.check(False, True,'In-bounds setting of sample rate - set to minimum SR (%s) produces BadParameterException'%getMinSampleRate(idx=0) )
                raise
            except FRONTEND.FrontendException, e:
                self.check(False, True,'In-bounds setting of sample rate - set to minimum SR (%s) produces FrontendException'%getMinSampleRate(idx=0) )
                raise
            except Exception, e:
                self.check(False, True,'In-bounds setting of sample rate - set to minimum SR (%s) produces Exception'%getMinSampleRate(idx=0))
                raise
            else:
                self.checkAlmostEqual(getMinSampleRate(idx=0),tuner_control.getTunerOutputSampleRate(controller_id),'In-bounds re-tune of sample rate - set to minimum SR (%s)'%getMinSampleRate(idx=0),places=0)
                tuner_control.setTunerOutputSampleRate(controller_id, getMaxSampleRate(idx=0))   
                self.checkAlmostEqual(getMaxSampleRate(idx=0),tuner_control.getTunerOutputSampleRate(controller_id),'In-bounds re-tune of sample rate - set to maximum SR (%s)'%getMaxSampleRate(idx=0),places=0)
                tuner_control.setTunerOutputSampleRate(controller_id, sr)   
                self.checkAlmostEqual(sr,tuner_control.getTunerOutputSampleRate(controller_id),'In-bounds re-tune of sample rate - set to original SR (%s)'%sr,places=0)

        
    def testFRONTEND_3_3_19(self):
        ''' RX_DIG 3.19 Verify digital tuner port setTunerGain function in-bounds retune
        '''
            
        port_name = 'DigitalTuner_in'
        tuner_control = self.dut.getPort('DigitalTuner_in')
        tuner_control._narrow(FRONTEND.FrontendTuner)
        controller = generateTunerRequest()

        # make allocations
        controller_id = controller['ALLOC_ID']
        controller_alloc = generateTunerAlloc(controller)
        self.check(self.dut_ref.allocateCapacity(controller_alloc),True,'ERROR -- could not allocate controller',throwOnFailure=True,silentSuccess=True)
        
        # check gain: set to min, max, then orig
        try:
            gain = tuner_control.getTunerGain(controller_id)
        except FRONTEND.NotSupportedException:
            self.check(True,True,'%s.getTunerGain produces NotSupportedException -- cannot verify setTunerGain function'%(port_name), successMsg='info')
            try:
                tuner_control.setTunerGain(controller_id, getMinGain(idx=0))
            except FRONTEND.NotSupportedException:
                self.check(True,True,'%s.setTunerGain produces NotSupportedException'%(port_name))
            else:
                self.check(True,True,'%s.setTunerGain executes without throwing exception'%(port_name))
        except Exception, e:
            self.check(False, True,'%s.getTunerGain produces Exception -- cannot verify setTunerGain function',failureMsg='WARN')
            try:
                tuner_control.setTunerGain(controller_id, getMinGain(idx=0))
            except FRONTEND.NotSupportedException:
                self.check(True,True,'%s.setTunerGain produces NotSupportedException'%(port_name))
            else:
                self.check(True,True,'%s.setTunerGain executes without throwing exception'%(port_name))
        else:
            try:
                tuner_control.setTunerGain(controller_id, getMinGain(idx=0))
            except FRONTEND.NotSupportedException:
                self.check(True,True,'%s.setTunerGain produces NotSupportedException'%(port_name))
            except FRONTEND.BadParameterException, e:
                self.check(False, True,'In-bounds setting of gain - set to minimum gain (%s) produces BadParameterException'%getMinGain(idx=0))
                raise
            except FRONTEND.FrontendException, e:
                self.check(False, True,'In-bounds setting of gain - set to minimum gain (%s) produces FrontendException'%getMinGain(idx=0))
                raise
            except Exception, e:
                self.check(False, True,'In-bounds setting of gain - set to minimum gain (%s) produces Exception'%getMinGain(idx=0))
                raise
            else:
                self.checkAlmostEqual(getMinGain(idx=0),tuner_control.getTunerGain(controller_id),'In-bounds setting of gain - set to minimum gain (%s)'%getMinGain(idx=0),places=2)
                tuner_control.setTunerGain(controller_id, getMaxGain(idx=0))
                self.checkAlmostEqual(getMaxGain(idx=0),tuner_control.getTunerGain(controller_id),'In-bounds setting of gain - set to maximum gain (%s)'%getMaxGain(idx=0),places=2)
                tuner_control.setTunerGain(controller_id, gain)
                self.checkAlmostEqual(gain,tuner_control.getTunerGain(controller_id),'In-bounds setting of gain - set to original gain (%s)'%gain,places=2)

        
    def testFRONTEND_3_3_20(self):
        ''' RX_DIG 3.20 Verify digital tuner port setTunerCenterFrequency function out of bounds retune
        '''
            
        port_name = 'DigitalTuner_in'
        tuner_control = self.dut.getPort('DigitalTuner_in')
        tuner_control._narrow(FRONTEND.FrontendTuner)
        controller = generateTunerRequest()

        # make allocations
        controller_id = controller['ALLOC_ID']
        controller_alloc = generateTunerAlloc(controller)
        self.check(self.dut_ref.allocateCapacity(controller_alloc),True,'ERROR -- could not allocate controller',throwOnFailure=True,silentSuccess=True)
                    
        #Verify outside-bounds retune
        #check Center Freq:
        try:
            cf = tuner_control.getTunerCenterFrequency(controller_id)
        except FRONTEND.NotSupportedException:
            self.check(True,True,'%s.getTunerCenterFrequency produces NotSupportedException -- cannot verify out-of-bounds frequency tuning'%(port_name), successMsg='info')
        except Exception, e:
            self.check(False, True,'%s.getTunerCenterFrequency produces Exception -- cannot verify out-of-bounds frequency tuning',failureMsg='WARN')
        else:
            try:
                tuner_control.setTunerCenterFrequency(controller_id, getMaxCenterFreq(idx=0) + cf)
            except FRONTEND.NotSupportedException:
                self.check(True,True,'%s.setTunerCenterFrequency produces NotSupportedException -- cannot verify out-of-bounds frequency tuning'%(port_name))
            except FRONTEND.BadParameterException, e:
                self.check(True, True,'Out-of-bounds re-tune of frequency produces BadParameterException')
            except FRONTEND.FrontendException, e:
                self.check(False, True,'Out-of-bounds re-tune of frequency produces BadParameterException (produces FrontendException instead)')
                raise
            except Exception, e:
                self.check(False, True,'Out-of-bounds re-tune of frequency produces BadParameterException (produces another Exception instead)')
                raise
            else:
                self.check(False, True,'Out-of-bounds re-tune of frequency produces BadParameterException')
            if not self.checkAlmostEqual(cf, tuner_control.getTunerCenterFrequency(controller_id),'Out-of-bounds re-tune of frequency - CF unchanged',places=0):
                try:
                    tuner_control.setTunerCenterFrequency(controller_id, cf)
                except:
                    pass

        
    def testFRONTEND_3_3_21(self):
        ''' RX_DIG 3.21 Verify digital tuner port setTunerBandwidth function out of bounds retune
        '''
            
        port_name = 'DigitalTuner_in'
        tuner_control = self.dut.getPort('DigitalTuner_in')
        tuner_control._narrow(FRONTEND.FrontendTuner)
        controller = generateTunerRequest()

        # make allocations
        controller_id = controller['ALLOC_ID']
        controller_alloc = generateTunerAlloc(controller)
        self.check(self.dut_ref.allocateCapacity(controller_alloc),True,'ERROR -- could not allocate controller',throwOnFailure=True,silentSuccess=True)
        
        #Check Bandwidth      
        try:
            bw = tuner_control.getTunerBandwidth(controller_id)
        except FRONTEND.NotSupportedException:
            self.check(True,True,'%s.getTunerBandwidth produces NotSupportedException -- cannot verify out-of-bounds bandwidth tuning'%(port_name), successMsg='info')
        except Exception, e:
            self.check(False, True,'%s.getTunerBandwidth produces Exception -- cannot verify out-of-bounds bandwidth tuning',failureMsg='WARN')
        else:
            try:
                tuner_control.setTunerBandwidth(controller_id, getMaxBandwidth(idx=0) + bw)
            except FRONTEND.NotSupportedException:
                self.check(True,True,'%s.setTunerBandwidth produces NotSupportedException -- cannot verify out-of-bounds bandwidth tuning'%(port_name))
            except FRONTEND.BadParameterException, e:
                self.check(True, True,'Out-of-bounds re-tune of bandwidth produces BadParameterException')
            except FRONTEND.FrontendException, e:
                self.check(False, True,'Out-of-bounds re-tune of bandwidth produces BadParameterException (produces FrontendException instead)')
                raise
            except Exception, e:
                self.check(False, True,'Out-of-bounds re-tune of bandwidth produces BadParameterException (produces another Exception instead)')
                raise
            else:
                self.check(False, True,'Out-of-bounds re-tune of bandwidth produces BadParameterException')
                # DEBUG
                '''
                print 'DEBUG - out of bounds retune of bw did not produce exception'
                print 'DEBUG - tuned bw: %s'%(getMaxBandwidth(idx=0) + bw)
                print 'DEBUG - tuner status:'
                pp(self._getTunerStatusProp(controller_id))
                '''
            new_bw = tuner_control.getTunerBandwidth(controller_id)
            if not self.checkAlmostEqual(bw, new_bw,'Out-of-bounds re-tune of bandwidth - BW unchanged',places=0):
                # DEBUG
                '''
                print 'DEBUG - out of bounds retune of bw incorrectly caused change in bw'
                print 'DEBUG - orig bw: %s  new bw: %s  tuned bw: %s'%(bw,new_bw,getMaxBandwidth(idx=0) + bw)
                # end DEBUG
                '''
                try:
                    tuner_control.setTunerBandwidth(controller_id, bw)
                except:
                    pass

        
    def testFRONTEND_3_3_22(self):
        ''' RX_DIG 3.22 Verify digital tuner port setTunerOutputSampleRate function out of bounds retune
        '''
            
        port_name = 'DigitalTuner_in'
        tuner_control = self.dut.getPort('DigitalTuner_in')
        tuner_control._narrow(FRONTEND.FrontendTuner)
        controller = generateTunerRequest()

        # make allocations
        controller_id = controller['ALLOC_ID']
        controller_alloc = generateTunerAlloc(controller)
        self.check(self.dut_ref.allocateCapacity(controller_alloc),True,'ERROR -- could not allocate controller',throwOnFailure=True,silentSuccess=True)
            
        #Check SR
        try:
            sr = tuner_control.getTunerOutputSampleRate(controller_id)
        except FRONTEND.NotSupportedException:
            self.check(True,True,'%s.getTunerOutputSampleRate produces NotSupportedException -- cannot verify out-of-bounds sample rate tuning'%(port_name), successMsg='info')
        except Exception, e:
            self.check(False, True,'%s.getTunerOutputSampleRate produces Exception -- cannot verify out-of-bounds sample rate tuning',failureMsg='WARN')
        else:
            try:
                tuner_control.setTunerOutputSampleRate(controller_id, getMaxSampleRate(idx=0, cap=False) + sr)
            except FRONTEND.NotSupportedException:
                self.check(True,True,'%s.setTunerOutputSampleRate produces NotSupportedException -- cannot verify out-of-bounds sample rate tuning'%(port_name))
            except FRONTEND.BadParameterException, e:
                self.check(True, True,'Out-of-bounds re-tune of sample rate produces BadParameterException')
            except FRONTEND.FrontendException, e:
                self.check(False, True,'Out-of-bounds re-tune of sample rate produces BadParameterException (produces FrontendException instead)')
                raise
            except Exception, e:
                self.check(False, True,'Out-of-bounds re-tune of sample rate produces BadParameterException (produces another Exception instead)')
                raise
            else:
                self.check(False, True,'Out-of-bounds re-tune of sample rate produces BadParameterException')
            new_sr = tuner_control.getTunerOutputSampleRate(controller_id)
            if not self.checkAlmostEqual(sr, new_sr,'Out-of-bounds re-tune of sample rate - SR unchanged',places=0):
                # DEBUG
                '''
                print 'DEBUG - out of bounds retune of sr incorrectly caused change in sr'
                print 'DEBUG - orig sr: %s  new sr: %s  tuned sr: %s'%(sr,new_sr,getMaxSampleRate(idx=0, cap=False) + sr)
                # end DEBUG
                '''
                try:
                    tuner_control.setTunerOutputSampleRate(controller_id, sr)
                except:
                    pass

        
    def testFRONTEND_3_3_23(self):
        ''' RX_DIG 3.23 Verify digital tuner port setTunerGain function out of bounds retune
        '''
            
        port_name = 'DigitalTuner_in'
        tuner_control = self.dut.getPort('DigitalTuner_in')
        tuner_control._narrow(FRONTEND.FrontendTuner)
        controller = generateTunerRequest()

        # make allocations
        controller_id = controller['ALLOC_ID']
        controller_alloc = generateTunerAlloc(controller)
        self.check(self.dut_ref.allocateCapacity(controller_alloc),True,'ERROR -- could not allocate controller',throwOnFailure=True,silentSuccess=True)
        
        #Check gain
        try:
            gain = tuner_control.getTunerGain(controller_id)
        except FRONTEND.NotSupportedException:
            self.check(True,True,'%s.getTunerGain produces NotSupportedException -- cannot verify out-of-bounds gain setting'%(port_name), successMsg='info')
        except Exception, e:
            self.check(False, True,'%s.getTunerGain produces Exception -- cannot verify out-of-bounds gain tuning',failureMsg='WARN')
        else:
            try:
                tuner_control.setTunerGain(controller_id, getMaxGain(idx=0) + abs(getMaxGain(idx=0)-getMinGain(idx=0)) + 1)
            except FRONTEND.NotSupportedException:
                self.check(True,True,'%s.setTunerGain produces NotSupportedException -- cannot verify out-of-bounds gain setting'%(port_name))
            except FRONTEND.BadParameterException, e:
                self.check(True, True,'Out-of-bounds setting of gain produces BadParameterException')
            except FRONTEND.FrontendException, e:
                self.check(False, True,'Out-of-bounds setting of gain produces BadParameterException (produces FrontendException instead)')
                raise
            except Exception, e:
                self.check(False, True,'Out-of-bounds re-tune of gain produces BadParameterException (produces another Exception instead)')
                raise
            else:
                self.check(False, True,'Out-of-bounds setting of gain produces BadParameterException')
            new_gain = tuner_control.getTunerGain(controller_id)
            if not self.checkAlmostEqual(gain, new_gain,'Out-of-bounds setting of gain - gain unchanged',places=2):
                '''
                # DEBUG
                print 'DEBUG - out of bounds retune of gain incorrectly caused change in gain'
                print 'DEBUG - orig gain: %s  new gain: %s  tuned gain: %s'%(gain,new_gain,getMaxGain(idx=0) + abs(getMaxGain(idx=0)-getMinGain(idx=0)) + 1)
                # end DEBUG
                '''
                try:
                    tuner_control.setTunerGain(controller_id, gain)
                except:
                    pass

        
    def testFRONTEND_3_3_24(self):
        ''' RX_DIG 3.24 Verify digital tuner port setTunerAgcEnable function
        '''
            
        port_name = 'DigitalTuner_in'
        tuner_control = self.dut.getPort('DigitalTuner_in')
        tuner_control._narrow(FRONTEND.FrontendTuner)
        controller = generateTunerRequest()

        # make allocations
        controller_id = controller['ALLOC_ID']
        controller_alloc = generateTunerAlloc(controller)
        self.check(self.dut_ref.allocateCapacity(controller_alloc),True,'ERROR -- could not allocate controller',throwOnFailure=True,silentSuccess=True)
        
        # test changing values for the rest
        # setTunerAgcEnable
        try:
            orig = tuner_control.getTunerAgcEnable(controller_id)
        except FRONTEND.NotSupportedException:
            self.check(True,True,'%s.getTunerAgcEnable produces NotSupportedException -- cannot test setTunerAgcEnable function'%(port_name))
            try:
                tuner_control.setTunerAgcEnable(controller_id, False)
            except FRONTEND.NotSupportedException:
                self.check(True,True,'%s.setTunerAgcEnable produces NotSupportedException'%(port_name))
            else:
                self.check(True,True,'%s.setTunerAgcEnable executes without throwing exception'%(port_name))
        else:
            try:
                tuner_control.setTunerAgcEnable(controller_id, not orig)
            except FRONTEND.NotSupportedException:
                self.check(True,True,'%s.setTunerAgcEnable produces NotSupportedException'%(port_name))
            else:
                self.check(not orig,tuner_control.getTunerAgcEnable(controller_id),'setting agc enable -- set to new value')
                tuner_control.setTunerAgcEnable(controller_id, orig)
                self.check(orig,tuner_control.getTunerAgcEnable(controller_id),'setting agc enable -- set back to original value')

        
    def testFRONTEND_3_3_25(self):
        ''' RX_DIG 3.25 Verify digital tuner port setTunerReferenceSource function
        '''
            
        port_name = 'DigitalTuner_in'
        tuner_control = self.dut.getPort('DigitalTuner_in')
        tuner_control._narrow(FRONTEND.FrontendTuner)
        controller = generateTunerRequest()

        # make allocations
        controller_id = controller['ALLOC_ID']
        controller_alloc = generateTunerAlloc(controller)
        self.check(self.dut_ref.allocateCapacity(controller_alloc),True,'ERROR -- could not allocate controller',throwOnFailure=True,silentSuccess=True)
            
        # setTunerReferenceSource
        try:
            orig = tuner_control.getTunerReferenceSource(controller_id)
        except FRONTEND.NotSupportedException:
            self.check(True,True,'%s.getTunerReferenceSource produces NotSupportedException -- cannot test setTunerReferenceSource function'%(port_name))
            try:
                tuner_control.setTunerReferenceSource(controller_id, False)
            except FRONTEND.NotSupportedException:
                self.check(True,True,'%s.setTunerReferenceSource produces NotSupportedException'%(port_name))
            else:
                self.check(True,True,'%s.setTunerReferenceSource executes without throwing exception'%(port_name))
        else:
            try:
                tuner_control.setTunerReferenceSource(controller_id, int(not orig))
            except FRONTEND.NotSupportedException:
                self.check(True,True,'%s.setTunerReferenceSource produces NotSupportedException'%(port_name))
            else:
                self.check(int(not orig),tuner_control.getTunerReferenceSource(controller_id),'setting tuner reference source -- set to new value')
                tuner_control.setTunerReferenceSource(controller_id, orig)
                self.check(orig,tuner_control.getTunerReferenceSource(controller_id),'setting tuner reference source -- set back to original value')

        
    def testFRONTEND_3_3_26(self):
        ''' RX_DIG 3.26 Verify digital tuner port setTunerEnable function
        '''
            
        port_name = 'DigitalTuner_in'
        tuner_control = self.dut.getPort('DigitalTuner_in')
        tuner_control._narrow(FRONTEND.FrontendTuner)
        controller = generateTunerRequest()

        # make allocations
        controller_id = controller['ALLOC_ID']
        controller_alloc = generateTunerAlloc(controller)
        self.check(self.dut_ref.allocateCapacity(controller_alloc),True,'ERROR -- could not allocate controller',throwOnFailure=True,silentSuccess=True)
            
        # setTunerEnable
        try:
            orig = tuner_control.getTunerEnable(controller_id)
        except FRONTEND.NotSupportedException:
            self.check(True,True,'%s.getTunerEnable produces NotSupportedException -- cannot test setTunerEnable function'%(port_name))
            try:
                tuner_control.setTunerEnable(controller_id, True)
            except FRONTEND.NotSupportedException:
                self.check(True,True,'%s.setTunerEnable produces NotSupportedException'%(port_name))
            else:
                self.check(True,True,'%s.setTunerEnable executes without throwing exception'%(port_name))
        else:
            try:
                tuner_control.setTunerEnable(controller_id, not orig)
            except FRONTEND.NotSupportedException:
                self.check(True,True,'%s.setTunerEnable produces NotSupportedException'%(port_name))
            else:
                self.check(not orig,tuner_control.getTunerEnable(controller_id),'setting tuner enable -- set to new value')
                tuner_control.setTunerEnable(controller_id, orig)
                self.check(orig,tuner_control.getTunerEnable(controller_id),'setting tuner enable -- set back to original value')

        
    def testFRONTEND_3_3_27(self):
        ''' RX_DIG 3.27 Verify digital tuner port getter functions w/ bad alloc id
        '''
            
        port_name = 'DigitalTuner_in'
        tuner_control = self.dut.getPort('DigitalTuner_in')
        tuner_control._narrow(FRONTEND.FrontendTuner)
        controller = generateTunerRequest()
        function_list = self.digital_tuner_idl

        # make allocations
        controller_id = controller['ALLOC_ID']
        controller_alloc = generateTunerAlloc(controller)
        self.check(self.dut_ref.allocateCapacity(controller_alloc),True,'ERROR -- could not allocate controller',throwOnFailure=True,silentSuccess=True)
            
        # verify invalid alloc_id -> FrontendException
        bad_id = str(uuid.uuid4())
        for attr in filter(lambda x: x.startswith('get'),function_list):
            f = getattr(tuner_control,attr)
            try:
                resp = f(bad_id)
            except FRONTEND.NotSupportedException:
                self.check(True,True,'%s.%s called with bad alloc_id produces NotSupportedException'%(port_name,attr))
            except FRONTEND.FrontendException:
                self.check(True,True,'%s.%s called with bad alloc_id (should produce FrontendException)'%(port_name,attr))
            except Exception, e:
                self.check(False,True,'%s.%s called with bad alloc_id (produces %s exception, should produce FrontendException)'%(port_name,attr,e.__class__.__name__))
            else:
                self.check(False,True,'%s.%s called with bad alloc_id (does not produce exception, should produce FrontendException)'%(port_name,attr))

        
    def testFRONTEND_3_3_28(self):
        ''' RX_DIG 3.28 Verify digital tuner port setTunerCenterFrequency function w/ bad alloc id
        '''
        
        port_name = 'DigitalTuner_in'
        tuner_control = self.dut.getPort('DigitalTuner_in')
        tuner_control._narrow(FRONTEND.FrontendTuner)
        controller = generateTunerRequest()

        # make allocations
        controller_id = controller['ALLOC_ID']
        controller_alloc = generateTunerAlloc(controller)
        self.check(self.dut_ref.allocateCapacity(controller_alloc),True,'ERROR -- could not allocate controller',throwOnFailure=True,silentSuccess=True)
                
        # setTunerCenterFrequency
        bad_id = str(uuid.uuid4())
        try:
            tuner_control.setTunerCenterFrequency(bad_id, float(getMinCenterFreq(idx=0)))
        except FRONTEND.NotSupportedException:
            self.check(True,True,'%s.setTunerCenterFrequency called with bad alloc_id produces NotSupportedException'%(port_name))
        except FRONTEND.FrontendException:
            self.check(True,True,'%s.setTunerCenterFrequency called with bad alloc_id produces FrontendException'%(port_name))
        except Exception, e:
            self.check(False,True,'%s.setTunerCenterFrequency called with bad alloc_id (produces %s exception, should produce FrontendException)'%(port_name,e.__class__.__name__))
        else:
            self.check(False,True,'%s.setTunerCenterFrequency called with bad alloc_id produces FrontendException (no exception)'%(port_name))

        
    def testFRONTEND_3_3_29(self):
        ''' RX_DIG 3.29 Verify digital tuner port setTunerBandwidth function w/ bad alloc id
        '''
        
        port_name = 'DigitalTuner_in'
        tuner_control = self.dut.getPort('DigitalTuner_in')
        tuner_control._narrow(FRONTEND.FrontendTuner)
        controller = generateTunerRequest()

        # make allocations
        controller_id = controller['ALLOC_ID']
        controller_alloc = generateTunerAlloc(controller)
        self.check(self.dut_ref.allocateCapacity(controller_alloc),True,'ERROR -- could not allocate controller',throwOnFailure=True,silentSuccess=True)
            
        # setTunerBandwidth
        bad_id = str(uuid.uuid4())
        try:
            tuner_control.setTunerBandwidth(bad_id, float(getMinBandwidth(idx=0)))
        except FRONTEND.NotSupportedException:
            self.check(True,True,'%s.setTunerBandwidth called with bad alloc_id produces NotSupportedException'%(port_name))
        except FRONTEND.FrontendException:
            self.check(True,True,'%s.setTunerBandwidth called with bad alloc_id produces FrontendException'%(port_name))
        except Exception, e:
            self.check(False,True,'%s.setTunerBandwidth called with bad alloc_id (produces %s exception, should produce FrontendException)'%(port_name,e.__class__.__name__))
        else:
            self.check(False,True,'%s.setTunerBandwidth called with bad alloc_id produces FrontendException (no exception)'%(port_name))

        
    def testFRONTEND_3_3_30(self):
        ''' RX_DIG 3.30 Verify digital tuner port setTunerOutputSampleRate function w/ bad alloc id
        '''
        
        port_name = 'DigitalTuner_in'
        tuner_control = self.dut.getPort('DigitalTuner_in')
        tuner_control._narrow(FRONTEND.FrontendTuner)
        controller = generateTunerRequest()

        # make allocations
        controller_id = controller['ALLOC_ID']
        controller_alloc = generateTunerAlloc(controller)
        self.check(self.dut_ref.allocateCapacity(controller_alloc),True,'ERROR -- could not allocate controller',throwOnFailure=True,silentSuccess=True)

        # setTunerOutputSampleRate
        bad_id = str(uuid.uuid4())
        try:
            tuner_control.setTunerOutputSampleRate(bad_id, float(getMinSampleRate(idx=0)))
        except FRONTEND.NotSupportedException:
            self.check(True,True,'%s.setTunerOutputSampleRate called with bad alloc_id produces NotSupportedException'%(port_name))
        except FRONTEND.FrontendException:
            self.check(True,True,'%s.setTunerOutputSampleRate called with bad alloc_id produces FrontendException'%(port_name))
        except Exception, e:
            self.check(False,True,'%s.setTunerOutputSampleRate called with bad alloc_id (produces %s exception, should produce FrontendException)'%(port_name,e.__class__.__name__))
        else:
            self.check(False,True,'%s.setTunerOutputSampleRate called with bad alloc_id produces FrontendException (no exception)'%(port_name))

        
    def testFRONTEND_3_3_31(self):
        ''' RX_DIG 3.31 Verify digital tuner port setTunerGain function w/ bad alloc id
        '''
        
        port_name = 'DigitalTuner_in'
        tuner_control = self.dut.getPort('DigitalTuner_in')
        tuner_control._narrow(FRONTEND.FrontendTuner)
        controller = generateTunerRequest()

        # make allocations
        controller_id = controller['ALLOC_ID']
        controller_alloc = generateTunerAlloc(controller)
        self.check(self.dut_ref.allocateCapacity(controller_alloc),True,'ERROR -- could not allocate controller',throwOnFailure=True,silentSuccess=True)
            
        # setTunerGain
        bad_id = str(uuid.uuid4())
        try:
            tuner_control.setTunerGain(bad_id, float(getMinGain(idx=0)))
        except FRONTEND.NotSupportedException:
            self.check(True,True,'%s.setTunerGain called with bad alloc_id produces NotSupportedException'%(port_name))
        except FRONTEND.FrontendException:
            self.check(True,True,'%s.setTunerGain called with bad alloc_id produces FrontendException'%(port_name))
        except Exception, e:
            self.check(False,True,'%s.setTunerGain called with bad alloc_id (produces %s exception, should produce FrontendException)'%(port_name,e.__class__.__name__))
        else:
            self.check(False,True,'%s.setTunerGain called with bad alloc_id produces FrontendException (no exception)'%(port_name))

        
    def testFRONTEND_3_3_32(self):
        ''' RX_DIG 3.32 Verify digital tuner port setTunerAgcEnable function w/ bad alloc id
        '''
        
        port_name = 'DigitalTuner_in'
        tuner_control = self.dut.getPort('DigitalTuner_in')
        tuner_control._narrow(FRONTEND.FrontendTuner)
        controller = generateTunerRequest()

        # make allocations
        controller_id = controller['ALLOC_ID']
        controller_alloc = generateTunerAlloc(controller)
        self.check(self.dut_ref.allocateCapacity(controller_alloc),True,'ERROR -- could not allocate controller',throwOnFailure=True,silentSuccess=True)
            
        # setTunerAgcEnable
        bad_id = str(uuid.uuid4())
        try:
            tuner_control.setTunerAgcEnable(bad_id, False)
        except FRONTEND.NotSupportedException:
            self.check(True,True,'%s.setTunerAgcEnable called with bad alloc_id produces NotSupportedException'%(port_name))
        except FRONTEND.FrontendException:
            self.check(True,True,'%s.setTunerAgcEnable called with bad alloc_id produces FrontendException'%(port_name))
        except Exception, e:
            self.check(False,True,'%s.setTunerAgcEnable called with bad alloc_id (produces %s exception, should produce FrontendException)'%(port_name,e.__class__.__name__))
        else:
            self.check(False,True,'%s.setTunerAgcEnable called with bad alloc_id produces FrontendException (no exception)'%(port_name))

        
    def testFRONTEND_3_3_33(self):
        ''' RX_DIG 3.33 Verify digital tuner port setTunerReferenceSource function w/ bad alloc id
        '''
        
        port_name = 'DigitalTuner_in'
        tuner_control = self.dut.getPort('DigitalTuner_in')
        tuner_control._narrow(FRONTEND.FrontendTuner)
        controller = generateTunerRequest()

        # make allocations
        controller_id = controller['ALLOC_ID']
        controller_alloc = generateTunerAlloc(controller)
        self.check(self.dut_ref.allocateCapacity(controller_alloc),True,'ERROR -- could not allocate controller',throwOnFailure=True,silentSuccess=True)
            
        # setTunerReferenceSource
        bad_id = str(uuid.uuid4())
        try:
            tuner_control.setTunerReferenceSource(bad_id, 0)
        except FRONTEND.NotSupportedException:
            self.check(True,True,'%s.setTunerReferenceSource called with bad alloc_id produces NotSupportedException'%(port_name))
        except FRONTEND.FrontendException:
            self.check(True,True,'%s.setTunerReferenceSource called with bad alloc_id produces FrontendException'%(port_name))
        except Exception, e:
            self.check(False,True,'%s.setTunerReferenceSource called with bad alloc_id (produces %s exception, should produce FrontendException)'%(port_name,e.__class__.__name__))
        else:
            self.check(False,True,'%s.setTunerReferenceSource called with bad alloc_id produces FrontendException (no exception)'%(port_name))

        
    def testFRONTEND_3_3_34(self):
        ''' RX_DIG 3.34 Verify digital tuner port setTunerEnable function w/ bad alloc id
        '''
        
        port_name = 'DigitalTuner_in'
        tuner_control = self.dut.getPort('DigitalTuner_in')
        tuner_control._narrow(FRONTEND.FrontendTuner)
        controller = generateTunerRequest()

        # make allocations
        controller_id = controller['ALLOC_ID']
        controller_alloc = generateTunerAlloc(controller)
        self.check(self.dut_ref.allocateCapacity(controller_alloc),True,'ERROR -- could not allocate controller',throwOnFailure=True,silentSuccess=True)
            
        # setTunerEnable
        bad_id = str(uuid.uuid4())
        try:
            tuner_control.setTunerEnable(bad_id, False)
        except FRONTEND.NotSupportedException:
            self.check(True,True,'%s.setTunerEnable called with bad alloc_id produces NotSupportedException'%(port_name))
        except FRONTEND.FrontendException:
            self.check(True,True,'%s.setTunerEnable called with bad alloc_id produces FrontendException'%(port_name))
        except Exception, e:
            self.check(False,True,'%s.setTunerEnable called with bad alloc_id (produces %s exception, should produce FrontendException)'%(port_name,e.__class__.__name__))
        else:
            self.check(False,True,'%s.setTunerEnable called with bad alloc_id produces FrontendException (no exception)'%(port_name))

        
    def testFRONTEND_3_4_DataFlow1(self):
        ''' RX_DIG 4 DataFlow - First Port
        '''
        self._testFRONTEND_3_4_DataFlow(1)

    def testFRONTEND_3_4_DataFlow2(self):
        ''' RX_DIG 4 DataFlow - Second Port
        '''
        self._testFRONTEND_3_4_DataFlow(2)

    def testFRONTEND_3_4_DataFlow3(self):
        ''' RX_DIG 4 DataFlow - Third Port
        '''
        self._testFRONTEND_3_4_DataFlow(3)

    def testFRONTEND_3_4_DataFlow4(self):
        ''' RX_DIG 4 DataFlow - Fourth Port
        '''
        self._testFRONTEND_3_4_DataFlow(4)

    # TODO - noseify
    def _testFRONTEND_3_4_DataFlow(self, port_num):
        ''' RX_DIG 4 DataFlow
        '''

        ttype='RX_DIGITIZER'
        controller = generateTunerRequest()
        #controller['CF'] = float(getMinCenterFreq(idx=0) + max(getMinBandwidth(idx=0),getMinSampleRate(idx=0)))
        controller['BW'] = float(getMinBandwidth(idx=0))
        controller['SR'] = float(getMinSampleRate(idx=0))
        listener1 = generateListenerRequest(controller)
        listener2 = generateListenerRequest(controller)

        tuner_control = self.dut.getPort('DigitalTuner_in')
        scd = SCDParser.parse(self.scd_file)
        count = 0
        for port in sorted(self.scd.get_componentfeatures().get_ports().get_uses(),reverse=True):
            comp_port_type = port.get_repid().split(':')[1].split('/')[-1]
            comp_port_name = port.get_usesname()
            if comp_port_type in self.port_map:
                count += 1
                if count == port_num:
                    self._testBULKIO(tuner_control,comp_port_name,comp_port_type,ttype,controller,listener1,listener2)
            elif comp_port_type == "dataSDDS":
                count += 1
                if count == port_num:
                    self._testSDDS(tuner_control,comp_port_name,comp_port_type,ttype,controller,listener1,listener2)
            else:
                print 'WARNING - skipping %s port named %s, not supported BULKIO port type'%(comp_port_type,comp_port_name)
                continue

    def _testBULKIO(self,tuner_control,comp_port_name,comp_port_type,ttype,controller,listener1=None,listener2=None):
        if comp_port_type == 'dataSDDS':
            return self._testSDDS(tuner_control,comp_port_name,comp_port_type,ttype,controller,listener1,listener2)
        print 'Testing data flow on port:',comp_port_type,comp_port_name
        pp(controller)
        comp_port_obj = self.dut.getPort(str(comp_port_name))
        dataSink1 = sb.DataSink()
        dataSink2 = sb.DataSink()
        dataSink3 = sb.DataSink()
        dataSink4 = sb.DataSink()
        dataSink1_port_obj = dataSink1.getPort(self.port_map[comp_port_type])
        dataSink2_port_obj = dataSink2.getPort(self.port_map[comp_port_type])
        dataSink3_port_obj = dataSink3.getPort(self.port_map[comp_port_type])
        dataSink4_port_obj = dataSink4.getPort(self.port_map[comp_port_type])
        
        #sb.start()
        
        # alloc a tuner
        controller['ALLOC_ID'] = "control:"+str(uuid.uuid4()) # unique for each loop
        tAlloc = generateTunerAlloc(controller)
        pp(controller)
        pp(tAlloc)
        comp_port_obj.connectPort(dataSink1_port_obj, controller['ALLOC_ID'])
        self.dut_ref.allocateCapacity(tAlloc)
        
        # verify basic data flow
        print >> sys.stderr,'attempting to get data from tuner'
        for attempt in xrange(10):
            time.sleep(1.0)
            data1 = dataSink1.getData()
            print >> sys.stderr,'attempt',attempt,'len(data1)=',len(data1)
            if len(data1)>0:
                break
        self.check(len(data1)>0,True,'%s: Received data from tuner allocation'%(comp_port_name))
        
        # verify SRI
        try:
            status = properties.props_to_dict(tuner_control.getTunerStatus(controller['ALLOC_ID']))
        except FRONTEND.NotSupportedException, e:
            status = self._getTunerStatusProp(controller['ALLOC_ID'])
        pp(status)
        
        #verify SRI
        sri1 = dataSink1.sri()
        self._verifySRI (sri1,status,comp_port_name)  
     
        # verify multi-out port
        bad_conn_id = "bad:"+str(uuid.uuid4())
        comp_port_obj.connectPort(dataSink2_port_obj, bad_conn_id)
        for attempt in xrange(5):
            time.sleep(1.0)
            data2 = dataSink2.getData()
            #print >> sys.stderr,'attempt',attempt,'len(data2)=',len(data2)
            if len(data2)>0:
                break
        #print 'data2',len(data2)
        self.check(len(data2)>0,False,'%s: Did not receive data from tuner allocation with wrong alloc_id (multiport test)'%(comp_port_name))
        sri1 = dataSink1.sri()
        sri2 = dataSink2.sri()
        print 'sri2',sri2
        self.check(sri1.streamID==sri2.streamID,False,'%s: Did not receive correct SRI from tuner allocation with wrong alloc_id (multiport test)'%(comp_port_name))
        
        if self.device_discovery[ttype] < 2:
            self.check(True,True,'%s: Cannot fully test multiport because only single %s tuner capability'%(comp_port_name,ttype),successMsg='info')
        else:
            pass # TODO - additional multiport tests here
    
        if listener1:
            # verify listener
            listener1 = generateListenerRequest(controller) # unique for each loop
            listener1['LISTENER_ID'] = "listener1:"+listener1['LISTENER_ID']
            listenerAlloc1 = generateListenerAlloc(listener1)
            comp_port_obj.connectPort(dataSink3_port_obj, listener1['LISTENER_ID'])
            self.dut_ref.allocateCapacity(listenerAlloc1)
            
            for attempt in xrange(5):
                time.sleep(1.0)
                data3 = dataSink3.getData()
                #print >> sys.stderr,'attempt',attempt,'len(data3)=',len(data3)
                if len(data3)>0:
                    break
            #print 'data3',len(data3)
            self.check(len(data3)>0,True,'%s: Received data from listener allocation'%(comp_port_name))
            sri1 = dataSink1.sri()
            sri3 = dataSink3.sri()
            print 'sri3',sri3
            self.check(sri1.streamID==sri3.streamID,True,'%s: Received correct SRI from listener allocation'%(comp_port_name))
            
            # verify EOS
            if listener2:
                listener2 = generateListenerRequest(controller) # unique for each loop
                listener2['LISTENER_ID'] = "listener2:"+listener2['LISTENER_ID']
                listenerAlloc2 = generateListenerAlloc(listener2)
                comp_port_obj.connectPort(dataSink4_port_obj, listener2['LISTENER_ID'])
                self.dut_ref.allocateCapacity(listenerAlloc2)               
                time.sleep(1.0)
                #for port_dict in port_list:       
                    #data4 = dataSink4.getData()
            self.dut_ref.deallocateCapacity(listenerAlloc1)
            self.check(dataSink3.eos(),True,'%s: Listener received EOS after deallocation of listener'%(comp_port_name))
            self.check(dataSink1.eos(),False,'%s: Controller did not receive EOS after deallocation of listener'%(comp_port_name))
            self.dut_ref.deallocateCapacity(tAlloc)
            self.check(dataSink1.eos(),True,'%s: Controller did receive EOS after deallocation of tuner'%(comp_port_name))
            if listener2:
                self.check(dataSink4.eos(),True,'%s: Listener received EOS after deallocation of tuner'%(comp_port_name))
    
    def _testSDDS(self,tuner_control,comp_port_name,comp_port_type,ttype,controller,listener1=None,listener2=None):
        print 'Testing SDDS port Behavior'
        comp_port_obj = self.dut.getPort(str(comp_port_name))
        dataSink1 = sb.DataSinkSDDS()
        dataSink2 = sb.DataSinkSDDS()
        dataSink1_port_obj = dataSink1.getPort("dataSDDSIn")
        dataSink2_port_obj = dataSink2.getPort("dataSDDSIn")
        
        # alloc a tuner
        controller['ALLOC_ID'] = "control:"+str(uuid.uuid4()) # unique for each loop
        tAlloc = generateTunerAlloc(controller)
        comp_port_obj.connectPort(dataSink1_port_obj, controller['ALLOC_ID'])
        self.dut_ref.allocateCapacity(tAlloc)

        time.sleep(4)
        
        sri1 = dataSink1._sink.sri
        if not sri1:
            self.check(False, True, "%s: No SRI pushed after connection and Allocation. Cannot continue Test"%(comp_port_name))
            return
        
        attachments1 = dataSink1._sink.attachments
        if not attachments1:
            self.check(False, True, "%s: No Attach Sent after connection and Allocation. Cannot continue Test"%(comp_port_name))
            return
        try:
            status = properties.props_to_dict(tuner_control.getTunerStatus(controller['ALLOC_ID']))
        except FRONTEND.NotSupportedException, e:
            status = self._getTunerStatusProp(controller['ALLOC_ID'])
        
        #verify SRI
        self._verifySRI (sri1,status,comp_port_name)       

        #verify Attachment
        self._verifyAttach(attachments1,status,comp_port_name)

        # verify multi-out port
        bad_conn_id = "bad:"+str(uuid.uuid4())
        comp_port_obj.connectPort(dataSink2_port_obj, bad_conn_id)
        for attempt in xrange(5):
            time.sleep(1.0)
            attachments2 = dataSink2._sink.attachments
            sri2 = dataSink2._sink.sri
            if sri2 or attachments2:
                break
        self.check(not(sri2),True,'%s: Did not receive sri from tuner allocation with wrong alloc_id (multiport test)'%(comp_port_name))
        self.check(not(attachments2),True,'%s: Did not receive attach from tuner allocation with wrong alloc_id (multiport test)'%(comp_port_name))
        
        comp_port_obj.disconnectPort(bad_conn_id)
        
        # verify listener
        listener1 = generateListenerRequest(controller) # unique for each loop
        listener1['LISTENER_ID'] = "listener1:"+listener1['LISTENER_ID']
        listenerAlloc1 = generateListenerAlloc(listener1)
        comp_port_obj.connectPort(dataSink2_port_obj, listener1['LISTENER_ID'])
        self.dut_ref.allocateCapacity(listenerAlloc1)
        
        time.sleep(0.1)
        
        sri2 = dataSink2._sink.sri
        if not sri2:
            self.check(False, True, "%s: No SRI pushed after connection and Listener Allocation. Cannot continue Test"%(comp_port_name))
            return
        
        attachments2 = dataSink2._sink.attachments
        if not attachments2:
            self.check(False, True, "%s: No Attach Sent after connection and Listener Allocation. Cannot continue Test"%(comp_port_name))
            return

        self.check(sri1.streamID==sri2.streamID,True,'%s: Received correct SRI from listener allocation'%(comp_port_name))
        self._compareAttach(attachments1,attachments2,comp_port_name)

        self.dut_ref.deallocateCapacity(listenerAlloc1)
        time.sleep(1)
        
        attachments2 = dataSink2._sink.attachments
        self.check(not(attachments2), True,'%s: Detach Listener on deallocation of listener'%(comp_port_name))

        self.dut_ref.deallocateCapacity(tAlloc)
        time.sleep(1)
        
        attachments1 = dataSink1._sink.attachments
        self.check(not(attachments1), True,'%s: Detach Data on deallocation'%(comp_port_name))

    def _compareAttach(self,attachments1,attachments2,comp_port_name=""):
        attachmentIDs1 = attachments1.keys()
        self.check(1,len(attachmentIDs1), "%s: Received Correct Number of Attachments on Listener"%(comp_port_name))
        attachmentID1 = attachmentIDs1[0]
        sddsStreamDef1 = attachments1[attachmentID1][0]
              
        attachmentIDs2 = attachments2.keys()
        self.check(1,len(attachmentIDs2), "%s: Received Correct Number of Attachments on Listener"%(comp_port_name))
        attachmentID2 = attachmentIDs2[0]
        sddsStreamDef2 = attachments2[attachmentID2][0]
        self.check(sddsStreamDef1.id==sddsStreamDef2.id,True,'%s: Received correct attach from listener allocation'%(comp_port_name))


    def _verifyAttach(self,attachments,status,comp_port_name=""):
        attachmentIDs = attachments.keys()
        self.check(1,len(attachmentIDs), "%s: Received Correct Number of Attachments"%(comp_port_name))
        attachmentID = attachmentIDs[0]
        sddsStreamDef1 = attachments[attachmentID][0]
        
        # Sample rate is stored as a double in frontend tuner status, but as an
        # unsigned long in the SDDS Stream Definition. Also, SDDS value is
        # calculated using 1/xdelta, which was previously calculated using 1/sr
        # Due to precision and rounding issues, especially on 32-bit systems,
        # a difference < 1.0 is considered correct.
        if DEBUG_LEVEL >= 4:
            print 'srate: fts:',  repr(status['FRONTEND::tuner_status::sample_rate']), ' fts rounded:', repr(round(status['FRONTEND::tuner_status::sample_rate']))
            print 'srate: sdds:', repr(sddsStreamDef1.sampleRate)
            print 'srate: diff:', repr(sddsStreamDef1.sampleRate-status['FRONTEND::tuner_status::sample_rate']), ' diff truncated:', repr(int(sddsStreamDef1.sampleRate-status['FRONTEND::tuner_status::sample_rate']))
        self.check(int(sddsStreamDef1.sampleRate-status['FRONTEND::tuner_status::sample_rate']), 0, '%s: Attach SampleRate has correct value'%(comp_port_name))
        self.check(status['FRONTEND::tuner_status::output_multicast'], sddsStreamDef1.multicastAddress, '%s: Attach multicast Address has correct value'%(comp_port_name))
        self.check(status['FRONTEND::tuner_status::output_vlan'], sddsStreamDef1.vlan, '%s: Attach vlan has correct value'%(comp_port_name))
        self.check(status['FRONTEND::tuner_status::output_port'], sddsStreamDef1.port, '%s: Attach port has correct value'%(comp_port_name))


    def _verifySRI(self,sri,status,comp_port_name=""):
        
        # verify SRI

    
        self.checkAlmostEqual(status['FRONTEND::tuner_status::sample_rate'], 1.0/sri.xdelta, '%s: SRI xdelta has correct value'%(comp_port_name),places=0)
        
        #complex is an optional property but if it is present check that it matches sri.
        if 'FRONTEND::tuner_status::complex' in status:
            self.check(status['FRONTEND::tuner_status::complex'],sri.mode,'%s: SRI mode has correct value'%(comp_port_name))
         
        # verify SRI keywords
        keywords = properties.props_to_dict(sri.keywords)
        if 'COL_RF' in keywords:
            self.check(True,True,'%s: SRI has COL_RF keyword'%(comp_port_name))
            self.checkAlmostEqual(status['FRONTEND::tuner_status::center_frequency'],keywords['COL_RF'],'%s: SRI keyword COL_RF has correct value'%(comp_port_name),places=0)
        else:
            self.check(False,True,'%s: SRI has COL_RF keyword'%(comp_port_name))
             
        if 'CHAN_RF' in keywords:
            self.check(True,True,'%s: SRI has CHAN_RF keyword'%(comp_port_name))
            self.checkAlmostEqual(status['FRONTEND::tuner_status::center_frequency'],keywords['CHAN_RF'],'%s: SRI keyword CHAN_RF has correct value'%(comp_port_name),places=0)
        else:
            self.check(False,True,'%s: SRI has CHAN_RF keyword'%(comp_port_name))
             
        if 'FRONTEND::BANDWIDTH' in keywords:
            self.check(True,True,'%s: SRI has FRONTEND::BANDWIDTH keyword'%(comp_port_name))
            if not self.checkAlmostEqual(status['FRONTEND::tuner_status::bandwidth'],keywords['FRONTEND::BANDWIDTH'],'%s: SRI keyword FRONTEND::BANDWIDTH has correct value'%(comp_port_name),places=0):
                self.checkAlmostEqual(status['FRONTEND::tuner_status::sample_rate'],keywords['FRONTEND::BANDWIDTH'],'%s: SRI keyword FRONTEND::BANDWIDTH has sample rate value'%(comp_port_name),places=0, silentFailure=True, successMsg='WARN')
        else:
            self.check(False,True,'%s: SRI has FRONTEND::BANDWIDTH keyword'%(comp_port_name))
             
        if 'FRONTEND::RF_FLOW_ID' in keywords:
            self.check(True,True,'%s: SRI has FRONTEND::RF_FLOW_ID keyword'%(comp_port_name))
            self.check(status['FRONTEND::tuner_status::rf_flow_id'],keywords['FRONTEND::RF_FLOW_ID'],'%s: SRI keyword FRONTEND::RF_FLOW_ID has correct value'%(comp_port_name))
        else:
            self.check(False,True,'%s: SRI has FRONTEND::RF_FLOW_ID keyword'%(comp_port_name))
             
        if 'FRONTEND::DEVICE_ID' in keywords:
            self.check(True,True,'%s: SRI has FRONTEND::DEVICE_ID keyword'%(comp_port_name))
            #self.check(1,keywords['FRONTEND::DEVICE_ID'],'SRI keyword FRONTEND::DEVICE_ID has correct value')
        else:
            self.check(False,True,'%s: SRI has FRONTEND::DEVICE_ID keyword'%(comp_port_name))    
         
    # TODO - noseify
    def testFRONTEND_3_5_TunerStatusProperties(self):
        ''' RX_DIG 5 TunerStatusProperties
        '''
        #self.testReport.append('\nTest 3.5 - Tuner Status Properties')
        
        tuner_control = self.dut.getPort('DigitalTuner_in')
        tuner_control._narrow(FRONTEND.FrontendTuner)
        
        controller = generateTunerRequest()
        listener1 = generateListenerRequest(controller)
        listener2 = generateListenerRequest(controller)
        
        # make allocations
        controller_id = controller['ALLOC_ID']
        controller_alloc = generateTunerAlloc(controller)
        self.check(self.dut_ref.allocateCapacity(controller_alloc),True,'ERROR -- could not allocate controller',throwOnFailure=True,silentSuccess=True)

        listener1_id = listener1['LISTENER_ID']
        listener1_alloc = generateListenerAlloc(listener1)
        retval = self.dut_ref.allocateCapacity(listener1_alloc)
        if not retval:
            self.testReport.append('Could not allocate listener1 -- limited test')
            listener1 = None
        else:
            listener2_id = listener2['LISTENER_ID']
            listener2_alloc = generateListenerAlloc(listener2)
            retval = self.dut_ref.allocateCapacity(listener2_alloc)
            if not retval:
                self.testReport.append('Could not allocate listener2 -- limited test')
                listener2 = None
        
        # Verify correct tuner status structure (fields, types)
        # check presence of tuner status property
        # check that it contains the required fields of correct data type
        # check which optional fields it contains, and that they are of correct data type
        # check for unknown/undefined fields
        try:
            status = self._getTunerStatusProp(controller_id)
        except KeyError:
            self.check(False, True, 'Device has FRONTEND::tuner_status property (failure, cannot complete test)')
        else:
            if status == None:
                self.check(False, True, 'Device has FRONTEND::tuner_status property (failure, cannot complete test)')
            else:
                self.check(True, True, 'Device has FRONTEND::tuner_status property')
                for name,dtype in self.FE_tuner_status_fields_req.items():
                    if status.has_key(name):
                        self.check(True, True, 'tuner_status has required field %s'%name)
                        self.check(type(status[name]) in dtype, True, 'value has correct data type for %s'%(name))
                    else:
                        self.check(False, True, 'tuner_status has required field %s'%name)
                for name,dtype in self.FE_tuner_status_fields_opt.items():
                    if status.has_key(name):
                        self.check(True, True, 'tuner_status has OPTIONAL field %s'%name)#, successMsg='yes')
                        self.check(type(status[name]) in dtype, True, 'value has correct data type for %s'%(name))
                    else:
                        self.check(False, True, 'tuner_status has OPTIONAL field %s'%name, failureMsg='no')
                all_names = self.FE_tuner_status_fields_req.keys()+self.FE_tuner_status_fields_opt.keys()
                for name in filter(lambda x: x not in all_names,status.keys()):
                    self.check(False, True, 'tuner_status has UNKNOWN field %s'%name, failureMsg='WARN')
    
        # Verify alloc_id_csv is populated after controller allocation
        try:
            status_val = self._getTunerStatusProp(controller_id,'FRONTEND::tuner_status::allocation_id_csv')
        except KeyError:
            pass
        else:
            if status_val == None:
                self.check(True, False, 'controller allocation id added to tuner status after allocation of controller (could not get tuner status prop)')
            else:
                self.check(controller_id, status_val.split(',')[0], 'controller allocation id added to tuner status after allocation of controller (must be first in CSV list)')
        
        # Verify tuner is enabled following allocation
        try:
            status_val = self._getTunerStatusProp(controller_id,'FRONTEND::tuner_status::enabled')
        except KeyError:
            pass
        else:
            if status_val == None:
                self.check(True, False, 'Tuner is enabled in tuner status after tuner allocation (could not get tuner status prop)')
            else:
                self.check(True, status_val, 'Tuner is enabled in tuner status after tuner allocation')

        if listener1:
            # Verify listener allocation id is added after allocation of listener        
            try:
                status_val = self._getTunerStatusProp(controller_id,'FRONTEND::tuner_status::allocation_id_csv')
            except KeyError:
                pass
            else:
                if status_val == None:
                    self.check(True, False, 'listener allocation id added to tuner status after allocation of listener (could not get tuner status prop)')
                else:
                    self.check(listener1_id in status_val.split(',')[1:], True, 'listener allocation id added to tuner status after allocation of listener (must not be first in CSV list)')
        
        if tuner_control:
            # Verify frequency prop
            try:
                val = tuner_control.getTunerCenterFrequency(controller_id)
            except FRONTEND.NotSupportedException, e:
                 pass
            else:
                try:
                    status_val = self._getTunerStatusProp(controller_id,'FRONTEND::tuner_status::center_frequency')
                except KeyError:
                    pass
                else:
                    self.checkAlmostEqual(status_val, val, 'correct value for FRONTEND::tuner_status::center_frequency property',places=0)
            #setTunerCenterFrequency
                
            # Verify bandwidth prop
            try:
                val = tuner_control.getTunerBandwidth(controller_id)
            except FRONTEND.NotSupportedException, e:
                 pass
            else:
                try:
                    status_val = self._getTunerStatusProp(controller_id,'FRONTEND::tuner_status::bandwidth')
                except KeyError:
                    pass
                else:
                    self.checkAlmostEqual(status_val, val, 'correct value for FRONTEND::tuner_status::bandwidth property',places=0)
            #setTunerBandwidth
            
            # Verify sample rate prop
            try:
                val = tuner_control.getTunerOutputSampleRate(controller_id)
            except FRONTEND.NotSupportedException, e:
                 pass
            else:
                try:
                    status_val = self._getTunerStatusProp(controller_id,'FRONTEND::tuner_status::sample_rate')
                except KeyError:
                    pass
                else:
                    self.checkAlmostEqual(status_val, val, 'correct value for FRONTEND::tuner_status::sample_rate property',places=0)
            #setTunerOutputSampleRate
            
            # Verify group id prop
            try:
                val = tuner_control.getTunerGroupId(controller_id)
            except FRONTEND.NotSupportedException, e:
                 pass
            else:
                try:
                    status_val = self._getTunerStatusProp(controller_id,'FRONTEND::tuner_status::group_id')
                except KeyError:
                    pass
                else:
                    self.check(status_val, val, 'correct value for FRONTEND::tuner_status::group_id property')
            
            # Verify rf flow id prop
            try:
                val = tuner_control.getTunerRfFlowId(controller_id)
            except FRONTEND.NotSupportedException, e:
                 pass
            else:
                try:
                    status_val = self._getTunerStatusProp(controller_id,'FRONTEND::tuner_status::rf_flow_id')
                except KeyError:
                    pass
                else:
                    self.check(status_val, val, 'correct value for FRONTEND::tuner_status::rf_flow_id property')
        
        if listener1:
            # Verify listener allocation id is removed after deallocation of listener
            self.dut_ref.deallocateCapacity(listener1_alloc)
            try:
                status_val = self._getTunerStatusProp(controller_id,'FRONTEND::tuner_status::allocation_id_csv')
            except KeyError:
                pass
            else:
                self.check(listener1_id in status_val, False, 'listener allocation id removed from tuner status after deallocation of listener')
            
        # Verify controller allocation id is removed after deallocation of controller
        self.dut_ref.deallocateCapacity(controller_alloc)
        try:
            status = self._getTunerStatusProp(controller_id)
        except KeyError:
            pass
        else:
            self.check(None, status, 'controller allocation id removed from tuner status after deallocation of controller')
        
        if listener2:
            # Verify listener allocation id is removed after deallocation of controller
            #self.dut_ref.deallocateCapacity(controllerAlloc)
            try:
                status = self._getTunerStatusProp(listener2_id)
            except KeyError:
                pass
            else:
                self.check(None, status, 'listener allocation id removed from tuner status after deallocation of controller')

    def testFRONTENDAllocationPropertiesWriteOnly(self):
        
        tuner_allocation = CF.DataType(id='FRONTEND::tuner_allocation',value=any.to_any(None))
        listener_allocation = CF.DataType(id='FRONTEND::listener_allocation',value=any.to_any(None))

        try:
            result = self.dut_ref.query([tuner_allocation])
        except CF.UnknownProperties:
            self.check(True, True, 'Query of Tuner Allocation Property throws expected exception')
        except Exception, e:
            self.check(False, True, 'Query of Tuner Allocation Property throws unexpected exception')
        else:
            self.check(False, True, 'Query of Tuner Allocation Property does not throw expected exception')

        try:
            result = self.dut_ref.query([listener_allocation])
        except CF.UnknownProperties:
            self.check(True, True, 'Query of Listener Allocation Property throws expected exception')
        except Exception, e:
            self.check(False, True, 'Query of Listener Allocation Property throws unexpected exception')
        else:
            self.check(False, True, 'Query of Listener Allocation Property does not throw expected exception')

    @classmethod
    def printTestReport(self):
        sys.stderr.writelines(self.testReport)

    #Helpers
    def check(self, A, B, message, throwOnFailure=False, silentFailure=False, silentSuccess=False, indent_width=0, failureMsg='FAILURE', successMsg='ok'):
        # successMsg suggestions: PASS, YES, ok, u'\u2714' (check mark)
        # failureMsg suggestions: FAIL, NO, u'\u2718' (x mark)
        if 'Total checks made' in self.testReportStats: self.testReportStats['Total checks made']+=1
        else: self.testReportStats['Total checks made']=1
        if A == B:
            if not silentSuccess:
                self.testReport.append(self._buildRow(message,successMsg,indent_width))
                tmp = 'Checks that returned "%s"'%successMsg[:4]
                if tmp in self.testReportStats: self.testReportStats[tmp]+=1
                else: self.testReportStats[tmp]=1
            return True # success!
        else:
            if not silentFailure:
                self.testReport.append(self._buildRow(message,failureMsg,indent_width))
                tmp = 'Checks that returned "%s"'%failureMsg[:4]
                if tmp in self.testReportStats: self.testReportStats[tmp]+=1
                else: self.testReportStats[tmp]=1
                if throwOnFailure:
                    #self.testReport.append('Terminal error, stopping current test...')
                    self.getToShutdownState()
                    self.assertFalse(failureMsg+'::'+message)
            return False # failure!
        
    def checkAlmostEqual(self, A, B, message, throwOnFailure=False, silentFailure=False, silentSuccess=False, indent_width=0, failureMsg='FAILURE', successMsg='ok', places=7):
        # successMsg suggestions: PASS, YES, ok, u'\u2714' (check mark)
        # failureMsg suggestions: FAIL, NO, u'\u2718' (x mark)
        #print "DEBUG","A=",A,"B=",B
        if 'Total checks made' in self.testReportStats: self.testReportStats['Total checks made']+=1
        else: self.testReportStats['Total checks made']=1
        if round(B-A, places) == 0:
            if not silentSuccess:
                self.testReport.append(self._buildRow(message,successMsg,indent_width))
                tmp = 'Checks that returned "%s"'%successMsg[:4]
                if tmp in self.testReportStats: self.testReportStats[tmp]+=1
                else: self.testReportStats[tmp]=1
            return True # success!
        else:
            if not silentFailure:
                self.testReport.append(self._buildRow(message,failureMsg,indent_width))
                tmp = 'Checks that returned "%s"'%failureMsg[:4]
                if tmp in self.testReportStats: self.testReportStats[tmp]+=1
                else: self.testReportStats[tmp]=1
                if throwOnFailure:
                    #self.testReport.append('Terminal error, stopping current test...')
                    self.getToShutdownState()
                    self.assertFalse(failureMsg+'::'+message)
            return False # failure!

    def _buildRow(self, lhs, rhs, indent_width=0, filler='.', len_total=80, rhs_width=4, depth=1):
        ''' builds a row (or multiple rows, if required) that fit within len_total columns
            format: <indent><lhs><at least 3 filler characters><rhs>
            -will be split over multiple lines if necessary
            -pads rhs text to number of characters specified by rhs_width using spaces
            -truncates rhs text to number of characters specified by rhs_width
        '''
        min_filler = 3
        max_lines = 5
        filler_width = len_total - (indent_width + len(lhs) + rhs_width)
        if filler_width >= min_filler:
            return (' '*indent_width + lhs + filler*filler_width + rhs)[0:len_total]
        else:
            lhs1_width = len_total - (indent_width + min_filler + rhs_width)
            idx = lhs.rfind(' ',0,lhs1_width) # try to split on a space
            if idx == -1:
                idx = (lhs+' ').find(' ') # split at first space, if any, or take the whole string
            line1 = ' '*indent_width + lhs[:idx]
            if depth==1:
                indent_width += 4
            if depth >= max_lines:
                return line1
            else:
                line2 = self._buildRow(lhs[idx:], rhs, indent_width, filler, len_total, rhs_width, depth=depth+1)
                return line1 + '\n' + line2
        
    def _tunerStatusHasAllocId(self,alloc_id):
        props = self.dut.query([])
        props = properties.props_to_dict(props)
        for tuner in props['FRONTEND::tuner_status']:
            if alloc_id in tuner['FRONTEND::tuner_status::allocation_id_csv'].split(','):
                return True
        return False
    
    def _findTunerStatusProps(match={},notmatch={}):
        ''' query latest props, find tuner status associated with key/value pairs
            in "match" dict where the key/value pairs of "notmatch" dict don't match
            return a list of tuner status prop dicts
            return empty list no tuner status satisfies the criteria
            if FRONTEND::tuner_status prop not found, raises KeyError
            if any key in match or notmatch not found, raises KeyError
        '''
        props = self.dut.query([])
        props = properties.props_to_dict(props)
        tuners = copy.deepcopy(props['FRONTEND::tuner_status'])
        for k,v in match.items():
            bad = []
            for tuner in tuners:
                if tuner[k] != v:
                    bad.append(tuner)
            tuners = [x for x in tuners if x not in bad]
            #tuners = filter(lambda x: x not in bad, tuners)
        for k,v in notmatch.items():
            bad = []
            for tuner in tuners:
                if tuner[k] == v:
                    bad.append(tuner)
            tuners = [x for x in tuners if x not in bad]
            #tuners = filter(lambda x: x not in bad, tuners)
        return tuners
    
    def _getTunerStatusProp(self,alloc_id,name=None):
        ''' query latest props, find tuner status associated with alloc_id
            if name arg is specified, return the tuner status property of that name
            otherwise, return the tuner status prop as a dict
            return None if either alloc_id or name not found
            if FRONTEND::tuner_status prop not found, raises KeyError
        '''
        props = self.dut.query([])
        props = properties.props_to_dict(props)
        for tuner in props['FRONTEND::tuner_status']:
            if alloc_id in tuner['FRONTEND::tuner_status::allocation_id_csv'].split(','):
                break
        else:
            return None
        
        if name!=None:
            try:
                return tuner[name]
            except KeyError:
                return None
        else:
            return tuner

###############################
# ALLOCATION HELPER FUNCTIONS #
###############################

def getMaxCenterFreq(idx=None):
    # If idx==None, iterate through all and find max
    if DEBUG_LEVEL >= 4:
        pp(DEVICE_INFO['capabilities'])

    max_cf = 0
    if idx == None:
        for chan in DEVICE_INFO['capabilities']:
            max_cf = max(max_cf,chan['RX_DIGITIZER']['CF'][-1])
    else:
        try:
            max_cf = DEVICE_INFO['capabilities'][idx]['RX_DIGITIZER']['CF'][-1]
        except IndexError:
            # bad idx value, just return idx 0
            max_cf = DEVICE_INFO['capabilities'][0]['RX_DIGITIZER']['CF'][-1]

    return max_cf

def getMaxSampleRate(idx=None, cap=True):
    # If idx==None, iterate through all and find max
    # If cap == True, cap max SR at sr_limit
    max_sr = 0
    if idx == None:
        for chan in DEVICE_INFO['capabilities']:
            max_sr = max(max_sr,chan['RX_DIGITIZER']['SR'][-1])
    else:
        try:
            max_sr = DEVICE_INFO['capabilities'][idx]['RX_DIGITIZER']['SR'][-1]
        except IndexError:
            # bad idx value, just return idx 0
            max_sr = DEVICE_INFO['capabilities'][0]['RX_DIGITIZER']['SR'][-1]

    if cap and 'sr_limit' in DEVICE_INFO and DEVICE_INFO['sr_limit'] > 0:
        max_sr = min(max_sr, DEVICE_INFO['sr_limit'])
    return max_sr

def getMaxBandwidth(idx=None):
    # If idx==None, iterate through all and find max
    # TODO - any need to account for sr_limit here?
    max_bw = 0
    if idx == None:
        for chan in DEVICE_INFO['capabilities']:
            max_bw = max(max_bw,chan['RX_DIGITIZER']['BW'][-1])
    else:
        try:
            max_bw = DEVICE_INFO['capabilities'][idx]['RX_DIGITIZER']['BW'][-1]
        except IndexError:
            # bad idx value, just return idx 0
            max_bw = DEVICE_INFO['capabilities'][0]['RX_DIGITIZER']['BW'][-1]
    return max_bw 

def getMaxValues(idx=None):
    # If idx==None, iterate through all and find max
    max_cf = getMaxCenterFreq(idx)
    max_sr = getMaxSampleRate(idx)
    max_bw = getMaxBandwidth(idx)
    return max_cf, max_sr, max_bw

def getMinCenterFreq(idx=None):
    # If idx==None, iterate through all and find min
    min_cf = DEVICE_INFO['capabilities'][0]['RX_DIGITIZER']['CF'][0]
    if idx == None:
        for chan in DEVICE_INFO['capabilities']:
            min_cf = min(min_cf,chan['RX_DIGITIZER']['CF'][0])
    else:
        try:
            min_cf = DEVICE_INFO['capabilities'][idx]['RX_DIGITIZER']['CF'][0]
        except IndexError:
            # bad idx value, just return idx 0
            min_cf = DEVICE_INFO['capabilities'][0]['RX_DIGITIZER']['CF'][0]

    return min_cf

def getMinSampleRate(idx=None):
    # If idx==None, iterate through all and find min
    min_sr = DEVICE_INFO['capabilities'][0]['RX_DIGITIZER']['SR'][0]
    if idx == None:
        for chan in DEVICE_INFO['capabilities']:
            min_sr = min(min_sr,chan['RX_DIGITIZER']['SR'][0])
    else:
        try:
            min_sr = DEVICE_INFO['capabilities'][idx]['RX_DIGITIZER']['SR'][0]
        except IndexError:
            # bad idx value, just return idx 0
            min_sr = DEVICE_INFO['capabilities'][0]['RX_DIGITIZER']['SR'][0]

    if 'sr_limit' in DEVICE_INFO and DEVICE_INFO['sr_limit'] > 0:
        min_sr = min(min_sr, DEVICE_INFO['sr_limit'])
    return min_sr

def getMinBandwidth(idx=None):
    # If idx==None, iterate through all and find min
    min_bw = DEVICE_INFO['capabilities'][0]['RX_DIGITIZER']['BW'][0]
    if idx == None:
        for chan in DEVICE_INFO['capabilities']:
            min_bw = min(min_bw,chan['RX_DIGITIZER']['BW'][0])
    else:
        try:
            min_bw = DEVICE_INFO['capabilities'][idx]['RX_DIGITIZER']['BW'][0]
        except IndexError:
            # bad idx value, just return idx 0
            min_bw = DEVICE_INFO['capabilities'][0]['RX_DIGITIZER']['BW'][0]
    return min_bw 

def getMinValues(idx=None):
    # If idx==None, iterate through all and find min
    min_cf = getMinCenterFreq(idx)
    min_sr = getMinSampleRate(idx)
    min_bw = getMinBandwidth(idx)
    return min_cf, min_sr, min_bw

def getMaxGain(idx=None):
    # If idx==None, iterate through all and find min
    max_gain = DEVICE_INFO['capabilities'][0]['RX_DIGITIZER']['GAIN'][-1]
    if idx == None:
        for chan in DEVICE_INFO['capabilities']:
            max_gain = max(max_gain,chan['RX_DIGITIZER']['GAIN'][-1])
    else:
        try:
            max_gain = DEVICE_INFO['capabilities'][idx]['RX_DIGITIZER']['GAIN'][-1]
        except IndexError:
            # bad idx value, just return idx 0
            max_gain = DEVICE_INFO['capabilities'][0]['RX_DIGITIZER']['GAIN'][-1]

    return max_gain

def getMinGain(idx=None):
    # If idx==None, iterate through all and find min
    min_gain = DEVICE_INFO['capabilities'][0]['RX_DIGITIZER']['GAIN'][0]
    if idx == None:
        for chan in DEVICE_INFO['capabilities']:
            min_gain = min(min_gain,chan['RX_DIGITIZER']['GAIN'][0])
    else:
        try:
            min_gain = DEVICE_INFO['capabilities'][idx]['RX_DIGITIZER']['GAIN'][0]
        except IndexError:
            # bad idx value, just return idx 0
            min_gain = DEVICE_INFO['capabilities'][0]['RX_DIGITIZER']['GAIN'][0]

    return min_gain

def defaultGenerateTunerRequest(idx=0):
    #Pick a random set for CF,BW,SR and return
    value = {}
    value['ALLOC_ID'] = str(uuid.uuid4())
    value['TYPE'] = 'RX_DIGITIZER'
    value['BW_TOLERANCE'] = 100.0
    value['SR_TOLERANCE'] = 100.0
    value['RF_FLOW_ID'] = ''
    value['GROUP_ID'] = ''
    value['CONTROL'] = True

    # TODO - does CF need to be an int? it was previously cast to int before returning.
    value['CF'] = getValueInRange(DEVICE_INFO['capabilities'][idx]['RX_DIGITIZER']['CF'])
    sr_subrange = DEVICE_INFO['capabilities'][idx]['RX_DIGITIZER']['SR']
    if 'sr_limit' in DEVICE_INFO and DEVICE_INFO['sr_limit'] > 0:
        sr_subrange = getSubranges([0,DEVICE_INFO['sr_limit']], DEVICE_INFO['capabilities'][idx]['RX_DIGITIZER']['SR'])
    value['SR'] = getValueInRange(sr_subrange)
    # Usable BW is typically equal to SR if complex samples, otherwise half of SR
    BW_MULT = 1.0 if DEVICE_INFO['capabilities'][idx]['RX_DIGITIZER']['COMPLEX'] else 0.5
    value['BW'] = 0.8*value['SR']*BW_MULT # Try 80% of SR
    if isValueInRange(value['BW'], DEVICE_INFO['capabilities'][idx]['RX_DIGITIZER']['BW']):
        # success! all done, return value
        return value

    # Can't use 80% of SR as BW, try to find a BW value within SR tolerances
    bw_min = value['SR']*BW_MULT
    bw_max = value['SR']*(1.0+(value['SR_TOLERANCE']/100.0))*BW_MULT
    tolerance_range = [bw_min,bw_max]
    bw_subrange = getSubranges(tolerance_range, DEVICE_INFO['capabilities'][idx]['RX_DIGITIZER']['BW'])
    if len(bw_subrange) > 0:
        # success! get BW value and return
        value['BW'] = getValueInRange(bw_subrange)
        return value

    # last resort
    value['BW'] = getValueInRange(DEVICE_INFO['capabilities'][idx]['RX_DIGITIZER']['BW'])
    return value

generateTunerRequest=defaultGenerateTunerRequest

def generateListenerRequest(c):
    value = {}
    value['LISTENER_ID'] = str(uuid.uuid4()) 
    value['ALLOC_ID'] = c['ALLOC_ID']
    return value

def generateListenerAlloc(value):
    allocationPropDict = {'FRONTEND::listener_allocation':{
                'FRONTEND::listener_allocation::existing_allocation_id': value['ALLOC_ID'],
                'FRONTEND::listener_allocation::listener_allocation_id': value['LISTENER_ID'],
                }}
    return properties.props_from_dict(allocationPropDict)

def generateTunerAlloc(value):
    #generate the allocation
    allocationPropDict = {'FRONTEND::tuner_allocation':{
                'FRONTEND::tuner_allocation::tuner_type': value['TYPE'],
                'FRONTEND::tuner_allocation::allocation_id': value['ALLOC_ID'],
                'FRONTEND::tuner_allocation::center_frequency': float(value['CF']),
                'FRONTEND::tuner_allocation::bandwidth': float(value['BW']),
                'FRONTEND::tuner_allocation::bandwidth_tolerance': float(value['BW_TOLERANCE']),
                'FRONTEND::tuner_allocation::sample_rate': float(value['SR']),
                'FRONTEND::tuner_allocation::sample_rate_tolerance': float(value['SR_TOLERANCE']),
                'FRONTEND::tuner_allocation::device_control': value['CONTROL'],
                'FRONTEND::tuner_allocation::group_id': value['GROUP_ID'],
                'FRONTEND::tuner_allocation::rf_flow_id': value['RF_FLOW_ID'],
                }}
    return properties.props_from_dict(allocationPropDict)

def getValueInRange(values):
    try:
        if len(values) == 1:
            # only one exact value
            retval = values[0]
        elif len(values) == 0 or len(values)%2 == 1:
            # invalid
            retval = 0
        elif len(values) == 2:
            # basic range
            retval = random.uniform(values[0],values[1])
        else:
            # range has gap
            options = []
            for (low,high) in zip(values[::2],values[1::2]):
                options.append(random.uniform(low,high))
            retval = random.choice(options)
    except TypeError:
        # Not iterable...
        retval = 0
    return retval

def isValueInRange(value, values):
    try:
        if len(values) == 1:
            # only one exact value
            retval = (value == values[0])
        elif len(values) == 0 or len(values)%2 == 1:
            # invalid
            retval = False
        elif len(values) == 2:
            # basic range
            retval = ( value >= values[0] and value <= values[1] )
        else:
            # range has gap
            retval = False
            for (low,high) in zip(values[::2],values[1::2]):
                retval = retval or ( value >= low and value <= high )
    except TypeError:
        # Not iterable...
        retval = False
    return retval

def getSubrange(range1, range2):
    # TODO - add checks for valid input
    low=max(range1[0],range2[0])
    high=min(range1[1],range2[1])
    return [low,high] if low <= high else []

def getSubranges(range1, values):
    # range1 must have exactly 2 elements
    # values may have a single element, or any even number of elements
    # returns list of values that are within range1
    try:
        if len(range1) != 2:
            # invalid range1
            retval = []
        elif len(values) == 1:
            retval = values if  isValueInRange(values[0],range1) else []
        elif len(values) == 0 or len(values)%2 == 1:
            # invalid values
            retval = []
        else:
            retval = []
            for (low,high) in zip(values[::2],values[1::2]):
                r = getSubrange(range1, [low,high])
                retval.extend(r)
    except TypeError:
        # Not iterable...
        retval = []
    return retval

#########################################################
## CODE FROM unit_test_helpers                         ##
#########################################################
    
def isMatch(prop, modes, kinds, actions):
    if prop.get_mode() == None:
        m = "readwrite"
    else:
        m = prop.get_mode()
    matchMode = (m in modes)
    if prop.__class__ in (PRFParser.simple, PRFParser.simpleSequence):
        if prop.get_action() == None:
            a = "external"
        else:
            a = prop.get_action().get_type()
        matchAction = (a in actions)

        matchKind = False
        if prop.get_kind() == None:
            k = ["configure"]
        else:
            k = prop.get_kind()
        for kind in k:
            if kind.get_kindtype() in kinds:
                matchKind = True

    elif prop.__class__ in (PRFParser.struct, PRFParser.structSequence):
        matchAction = True # There is no action, so always match

        matchKind = False
        if prop.get_configurationkind() == None:
            k = ["configure"]
        else:
            k = prop.get_configurationkind()
        for kind in k:
            if kind.get_kindtype() in kinds:
                matchKind = True

        if k in kinds:
            matchKind = True


    return matchMode and matchKind and matchAction
       
def getPropertySet(spd_file, kinds=("configure",), \
                             modes=("readwrite", "writeonly", "readonly"), \
                             action="external", \
                             includeNil=True):
    """
    A useful utility function that extracts specified property types from
    the PRF file and turns them into a CF.PropertySet
    """
    propertySet = []

    spd = SPDParser.parse(spd_file)
    prf_file = spd.get_propertyfile().get_localfile().get_name()
    if (prf_file[0] != '/'):
        prf_file = os.path.join(os.path.dirname(spd_file), prf_file)
    prf = PRFParser.parse(prf_file)

    # Simples
    for prop in prf.get_simple():
        if isMatch(prop, modes, kinds, (action,)): 
            if prop.get_value() is not None:
                dt = properties.to_tc_value(prop.get_value(), prop.get_type())
            elif not includeNil:
                continue
            else:
                dt = any.to_any(None)
            p = CF.DataType(id=str(prop.get_id()), value=dt)
            propertySet.append(p)

    # Simple Sequences
    for prop in prf.get_simplesequence():
        if isMatch(prop, modes, kinds, (action,)): 
            if prop.get_values() is not None:
                seq = []
                for v in prop.get_values().get_value():
                    seq.append(properties.to_pyvalue(v, prop.get_type()))
                dt = any.to_any(seq)
            elif not includeNil:
                continue
            else:
                dt = any.to_any(None)
            p = CF.DataType(id=str(prop.get_id()), value=dt)
            propertySet.append(p)

    # Structures
    for prop in prf.get_struct():
        if isMatch(prop, modes, kinds, (action,)): 
            if prop.get_simple() is not None:
                fields = []
                hasValue = False
                for s in prop.get_simple():
                    if s.get_value() is not None:
                        hasValue = True
                    dt = properties.to_tc_value(s.get_value(), s.get_type())
                    fields.append(CF.DataType(id=str(s.get_id()), value=dt))
                if not hasValue and not includeNil:
                    continue
                dt = any.to_any(fields)
            else:
                dt = any.to_any(None)
            p = CF.DataType(id=str(prop.get_id()), value=dt)
            propertySet.append(p)
    # Structures

    for prop in prf.get_structsequence():
        if isMatch(prop, modes, kinds, (action,)):
          baseProp = []
          if prop.get_struct() != None:
            fields = []
            for internal_prop in prop.get_struct().get_simple():
                fields.append(CF.DataType(id=str(internal_prop.get_id()), value=any.to_any(None)))
          for val in prop.get_structvalue():
            baseProp.append(copy.deepcopy(fields))
            for entry in val.get_simpleref():
              val_type = None
              for internal_prop in prop.get_struct().get_simple():
                  if str(internal_prop.get_id()) == entry.refid:
                      val_type = internal_prop.get_type()
              for subfield in baseProp[-1]:
                  if subfield.id == entry.refid:
                    subfield.value = properties.to_tc_value(entry.get_value(), val_type)
          anybp = []
          for bp in baseProp:
              anybp.append(properties.props_to_any(bp))
          p = CF.DataType(id=str(prop.get_id()), value=any.to_any(anybp))
          propertySet.append(p)
    # Struct Sequence

    return propertySet
