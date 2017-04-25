from pySPM import Block, utils
import numpy as np
import matplotlib.pyplot as plt
import struct
import os.path
import zlib
import re


class ITM:

    def __init__(self, filename):
        """
        Create the ITM object out of the filename.
        Note that this works for all .ITA,.ITM, .ITS files as they have the same structure
        """
        self.filename = filename
        assert os.path.exists(filename)
        self.f = open(self.filename, 'rb')
        self.Type = self.f.read(8)
        assert self.Type == b'ITStrF01'
        self.root = Block.Block(self.f)
        d = self.root.goto('Meta/SI Image').dictList()
        self.size = {
            'pixels': {
                'x': d[b'res_x']['long'],
                'y': d[b'res_y']['long']},
            'real': {
                'x': d[b'fieldofview']['float'],
                'y': d[b'fieldofview']['float'],
                'unit': 'm'}}
        try:
            self.size['Scans'] = \
                self.root.goto(
                    'filterdata/TofCorrection/ImageStack/Reduced Data/ImageStackScans/Image.NumberOfScans').getULong()
        except:
            pass
        self.peaks = {}
        self.MeasData = {}
        try:
            self.Nscan = int(self.root.goto('propend/Measurement.ScanNumber').getKeyValue(16)['SVal'])
        except:
            self.Nscan = None
            
        try:
            R = [z for z in self.root.goto('MassIntervalList').getList() if z[
                'name'].decode() == 'mi']
            N = len(R)
            for x in R:
                try:
                    X = self.root.goto('MassIntervalList/mi['+str(x['id'])+']')
                    d = X.dictList()
                    self.peaks[d[b'id']['long']] = d
                except ValueError:
                    pass
        except:
            pass

    def getIntensity(self):
        """
        Retieve the total Ion image
        """
        X, Y = self.size['pixels']['x'], self.size['pixels']['y']
        return np.array(struct.unpack('<'+str(X*Y)+'I',
                                      zlib.decompress(self.root.goto('Meta/SI Image/intensdata').value))).reshape((Y, X))

    def get_LMIG_info(self):
        rs = self.getValues(start=True)
        re = self.getValues()
        Val = [["Parameter name", "Value at start", "Value at end"]]
        for i, x in enumerate(rs):
            Val.append([x, rs[x], re[x]])

    def getValues(self, pb=False, names=[], startsWith="", nest=False, hidePrefix=True):
        """
        Beta function: Retieve a list of the values
        """
        Vals = {}
        for start in [True, False]:
            List = self.root.goto(['propend', 'propstart'][start]).getList()
            if pb:
                import tqdm
                List = tqdm.tqdm(List)
            for l in List:
                Node = self.root.goto(['propend', 'propstart'][
                                      start]).gotoItem(l['name'], l['id'])
                r = Node.getKeyValue(16)
                del Node
                S = Vals
                if r['Key'] in names or ( names==[] and r['Key'].startswith(startsWith) ):
                    if hidePrefix:
                        key_name = r['Key'][len(startsWith):]
                    else:
                        key_name = r['Key']
                    if nest:
                        K = key_name.split('.')
                        for k in K:
                            if k not in S:
                                S[k] = {}
                            S = S[k]
                        S['value @'+['end', 'start'][start]] = r['SVal']
                    else:
                        if start:
                            Vals[key_name] = [r['SVal']]
                        else:
                            Vals[key_name].append(r['SVal'])
        return Vals

    def showValues(self, pb=False, gui=False, **kargs):
        html = True
        if 'html' in kargs:
            html = kargs['html']
            del kargs['html']
        if gui:
            from pySPM import GUI
            Vals = self.getValues(pb, nest=True, **kargs)
            GUI.ShowValues(Vals)
        else:
            Vals = self.getValues(pb, **kargs)
            Table = [["Parameter Name", "Value @start", "Value @end"]]
            for x in Vals:
                Table.append((x, *Vals[x]))
            if not html:
                print(utils.aa_table(Table, header=True))
            else:
                from IPython.core.display import display, HTML
                res = utils.html_table(Table, header=True)
                display(HTML(res))

    def channel2mass(self, channels, sf=None, k0=None, binning=1):
        """
        Calculate the mass from the time of flight
        The parameters sf and k0 will be read from the file (calibration used by iontof) in case they are None
        The binning just multiply the channels in order to get the correct answer (used for the ITA files for the moment)
        """
        if sf is None or k0 is None:
            V = self.root.goto(
                'filterdata/TofCorrection/Spectrum/Reduced Data/IMassScaleSFK0')
        if sf is None:
            sf = V.goto('sf').getDouble()
        if k0 is None:
            k0 = V.goto('k0').getDouble()
        return ((binning*channels-k0)/(sf))**2

    def getSpectrum(self):
        """
        Retieve a mass,spectrum array
        """
        RAW = zlib.decompress(self.root.goto(
            'filterdata/TofCorrection/Spectrum/Reduced Data/IITFSpecArray/CorrectedData').value)
        D = np.array(struct.unpack("<{0}f".format(len(RAW)//4), RAW))
        ch = np.arange(len(D))
        return channel2mass(ch, binning=2), D

    def getMeasData(self, name='Instrument.LMIG.Emission_Current'):
        """
        Allows to recover the data saved during the measurements.
        This function is like getValues, but instead of giving the values at the beginning and at the end, 
        it track the changes of them during the measurement.
        """
        if name in self.MeasData:
            return self.MeasData[name]
            
        for idx, child in enumerate(self.root.goto('rawdata')):
            if child.name == b'  20':
                r = child.getKeyValue()
                if not r['Key'] in self.MeasData:
                    self.MeasData[r['Key']] = []
                self.MeasData[r['Key']].append((idx,r['Value']))
        return self.MeasData[name]

    def showMeasData(self, name='Instrument.LMIG.Emission_Current', ax=None, **kargs):
        t = self.getMeasData('Measurement.AcquisitionTime')
        idx = [x[0] for x in t]
        time = [x[1] for x in t]
        
        Meas = self.getMeasData(name)
        
        MeasData = [x[1] for x in Meas]
        MeasIdx = [x[0] for x in Meas]
        t = np.interp(MeasIdx,idx, time)
        if ax is None:
            ax = plt.gca()
        ax.plot(t, MeasData, **kargs)
        ax.set_xlabel("Time [s]");

    def showSpectrum(self, low=0, high=None, ax=None, log=False):
        """
        Plot the (summed) spectrum
        low and high: mass boundary of the plotted data
        ax: matplotlib axis
        log: plot the log of the intensity if True
        """
        m, s = self.getSpectrum()
        if ax is None:
            import matplotlib.pyplot as plt
            ax = plt.gca()
        if high is None:
            high = m[-1]
        mask = np.logical_and(m >= low, m <= high)
        M = m[mask]
        S = s[mask]
        if log:
            S = np.log(S)
        ax.plot(M, S)
        self.get_masses()

        for P in self.peaks:
            p = self.peaks[P]
            c = p[b'cmass']['float']
            mask = (m >= p[b'lmass']['float'])*(m <= p[b'umass']['float'])
            if c >= low and c <= high:
                i = np.argmin(abs(m-c))
                ax.axvline(m[i], color='red')
                ax.fill_between(m[mask], *ax.get_ylim(), color='red', alpha=.2)
                ax.annotate(p[b'assign']['utf16'], (m[i], ax.get_ylim()[
                            1]), (2, -10), va='top', textcoords='offset points')

    def get_masses(self, mass_list=None):
        """
        retrieve the peak list as a dictionnary
        """
        if mass_list is None:
            masses = self.peaks
        else:
            masses = mass_list
        result = []
        for P in masses:
            if mass_list is None:
                p = self.peaks[P]
            else:
                p = P
            result.append({
                'id': p[b'id']['long'],
                'desc': p[b'desc']['utf16'],
                'assign': p[b'assign']['utf16'],
                'lmass': p[b'lmass']['float'],
                'cmass': p[b'cmass']['float'],
                'umass': p[b'umass']['float']})
        return result

    def getRawData(self, scan=0):
        """
        Function which allows you to read and parse the raw data.
        With this you are able to reconstruct the data.
        Somehow the number of channel is double in the raw data compared
        to the compressed version saved in the ITA files.
        scan: The scan number. Start at 0
        """
        assert scan < self.Nscan
        found = False
        RAW = b''
        list_ = self.root.goto('rawdata').getList()
        startFound = False
        for x in list_:
            if x['name'] == b'   6':
                if not startFound:
                    startFound = x['id'] == scan
                else:
                    break
            elif startFound and x['name'] == b'  14':
                self.root.f.seek(x['bidx'])
                child = Block.Block(self.root.f)
                RAW += zlib.decompress(child.value)
        Blocks = {}
        _Block = []
        PixelOrder = np.zeros(
            (self.size['pixels']['y'], self.size['pixels']['x']))
        i = 0
        while i < len(RAW):
            b = RAW[i:i+4]
            if b[3:4] == b'\xc0':
                if len(_Block):
                    Blocks[(x, y)] = _Block
                b = b[:3] + b'\x00'
                x = struct.unpack('<I', b)[0]
                i += 4
                b = RAW[i:i+4]
                if b[3:4] != b'\xd0':
                    raise TypeError("Expecting a D0 block at {}".format(i+3))
                b = b[:3] + b'\x00'
                y = struct.unpack('<I', b)[0]
                i += 4
                b = RAW[i:i+4]
                if b[3:4] != b'\x40':
                    raise TypeError("Expecting a 40 block at {}".format(i+3))
                b = b[:3] + b'\x00'
                _Block = []
                id = struct.unpack('<I', b)[0]
                PixelOrder[y, x] = id
            else:
                _Block.append(struct.unpack('<I', b)[0])
            i += 4
        return PixelOrder, Blocks

    def show_masses(self, mass_list=None):
        """
        Display the peak list (assignment name with lower, center and upper mass)
        """
        for m in self.get_masses():
            if mass_list is None or m['id'] in [z['id'] for z in mass_list]:
                print(
                    "{id}: ({desc}) [{assign}] {lmass:.2f}u - {umass:.2f}u (center: {cmass:.2f}u)".format(**m))

    def showStage(self, ax=None, markers=False):
        """
        Display an image of the stage used
        ax: maplotlib axis to be ploted in. If None the current one (or new) will be used
        markers: If True will display on the map the Position List items.
        """
        W = self.root.goto('SampleHolderInfo/bitmap/res_x').getLong()
        H = self.root.goto('SampleHolderInfo/bitmap/res_y').getLong()

        if ax is None:
            import matplotlib.pyplot as plt
            fig, ax = plt.subplots(1, 1, figsize=(W*10/H, 10))

        Dat = zlib.decompress(self.root.goto(
            'SampleHolderInfo/bitmap/imagedata').value)
        I = 255*np.array(struct.unpack("<"+str(W*H*3)+"B", Dat)
                         ).reshape((H, W, 3))
        ax.imshow(I)
        if markers:
            X = self.root.goto('Meta/SI Image[0]/stageposition_x').getDouble()
            Y = self.root.goto('Meta/SI Image[0]/stageposition_y').getDouble()

            def toXY(xy, W, H):
                sx = 23
                sy = 23
                return (913+sx*xy[0], 1145+sy*xy[1])

            for x in self.root.goto('SampleHolderInfo/positionlist'):
                if x.name == b'shpos':
                    y = pickle.loads(x.goto('pickle').value)
                    pos = toXY((y['stage_x'], y['stage_y']), W, H)
                    if pos[0] >= 0 and pos[0] < W and pos[1] >= 0 and pos[1] < H:
                        ax.annotate(y['name'], xy=pos, xytext=(-15, -25), textcoords='offset points',
                                    arrowprops=dict(arrowstyle='->', facecolor='black'))
                pos = toXY((X, Y), W, H)
                ax.plot(pos[0], pos[1], 'xr')
        ax.set_xlim((0, W))
        ax.set_ylim((0, H))

    def showPeaks(self):
        self.getMassInt()
        for p in self.peaks:
            P = {k.decode('utf8'): self.peaks[p][k] for k in self.peaks[p]}
            print("{0}) {peaklabel}".format(p, **P))
