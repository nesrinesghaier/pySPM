# *-* encoding: utf-8 *-*
try:
    from pySPM import ToF
    from pySPM.SPM import *
    from pySPM import align
    import pySPM.nanoscan
    from pySPM.nanoscan import Nanoscan
    from pySPM.Bruker import Bruker
    from pySPM.ITA import ITA, ITA_collection
    from pySPM.ITM import ITM
    from pySPM.collection import Collection
except:
    # python2.7
    import ToF
    from SPM import *
    import align
    import nanoscan
    import Bruker
    from ITA import ITA, ITA_collection
    from ITM import ITM
    from collection import Collection
    

__all__ = ["ITA","ITM","PCA","Block","SPM","Bruker","nanoscan"]
__version__ = '0.1.1'
__author__ = 'Olivier Scholder'
__copyright__ = "Copyright 2017, EMPA, Dübendorf, Switzerland"
__email__ = "olivier.scholder@empa.ch"