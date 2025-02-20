from __future__ import print_function
from __future__ import division
from __future__ import unicode_literals

import posixpath as path
import numpy as np
from scipy import interpolate
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import getpass
import json
import requests
import IPython.display
import ast
import sys
import pandas as pd
import datetime
import time
import pickle
import inspect

import sys
sys.path.insert(0, '/Users/bpb/repos/omaat/BASTet_py3')
from omsi.dataformat.omsi_file import *
# import abc
# from future.utils import with_metaclass

try:
    import ipywidgets
except ImportError:
    import IPython.html.widgets as ipywidgets

# Bind input to raw_input for python 2 compatibility
# forces python2's input to return a string instead of executable
try:
   input = raw_input
except NameError:
   pass

# class MassRangeReductionStrategy(with_metaclass(abc.ABCMeta, object)):
#     @abc.abstractmethod
#     def reduceImage(self,data):
#         pass

#     def remoteReduceOperation(self, **kwargs):
#         """
#         Return a string for performing the same reduction operational remotely as part of the data request
#         from OpenMSI. Return None in case remote execution is not supported.
#         """
#         return None

#     def supportsRemoteReduce(self):
#         return self.remoteReduceOperation() is not None

class PeakArea():
    def reduceImage(self,data):
        return np.sum(data,2)
    def remoteReduceOperation(self, **kwargs):
        return '[{"min_dim": 2, "reduction": "sum", "axis": -1}]'
    def supportsRemoteReduce(self):
        return self.remoteReduceOperation() is not None

class PeakHeight():
    def reduceImage(self,data):
        return np.max(data,2)
    def remoteReduceOperation(self, **kwargs):
        return '[{"min_dim": 2, "reduction": "max", "axis": -1}]'
    def supportsRemoteReduce(self):
        return self.remoteReduceOperation() is not None

class AreaNearPeak():
    """instead of simply taking the sum or the max to get the "size" of a peak, this code finds the peak within a range and
        sums the data points 'halfpeakwidth' to the left and to the right of the peak
        if there is no peak, the boundary condition ends up being that it just takes the first halfpeakwidth+1 datapoints in the range
        but if there is no peak, we assume this value is very low anyways"""
    def __init__(self,halfpeakwidth=2):
        self.halfpeakwidth=halfpeakwidth

    def reduceImage(self,data):
        result = np.zeros((data.shape[0],data.shape[1]))
        maxMasses = np.argmax(data,2)
        for x in range(data.shape[0]):
            for y in range(data.shape[1]):
                peak=(list(range(-self.halfpeakwidth,self.halfpeakwidth+1))+maxMasses[x,y]).astype(int)
                for p in peak:
                    if p<0:
                        continue
                    if p>= data.shape[2]:
                        continue
                    result[x,y]+=data[x,y,p]
        return result

    def remoteReduceOperation(self, **kwargs):
        return '[{"min_dim": 2, "reduction": "area_near_peak", "halfpeakwidth": %s}]' % str(self.halfpeakwidth)

    def supportsRemoteReduce(self):
        return self.remoteReduceOperation() is not None

class ArrayedImage(object):
    """
    On abject that represents an OpenMSI image with arrayed samples on it.
    This class has various useful methods to help you extract data out.
    """
    def __init__(self,originalSize,ions,filename,expIndex,dataIndex,mz):
        """
        you won't want to call the constructor, use the 'login' function
        to create an OpenMSIsession object
        """
        self.imStack = np.zeros((originalSize[0],originalSize[1],len(ions)))
        self.originalSize=originalSize
        self.ions=ions
        self.mz=mz
        self.filename=filename
        self.expIndex=expIndex
        self.dataIndex=dataIndex
        self.baseImage=None
        self.xCenters=None
        self.yCenters=None
        self.spotList=None
        self.spotLocations=None
        self.Nrows=None
        self.Ncolumns=None
        self.spectra_df=None
        self.rough_position_draw_points = None
        self.fine_position_draw_points = None

    def __str__(self):
        spotstr=""
        if self.xCenters is not None:
            spotstr="{:d}".format(len(self.xCenters))
        else:
            spotstr="None"

        spotListstr=""
        if self.spotList:
            spotListstr="{:d}".format(len(self.spotList))
        else:
            spotListstr="None"

        return "ArrayedImage based on "+self.filename+\
                "\nIons loaded: "+str(self.ions)+\
                "\n# of spot locations defined: "+spotstr+\
                "\n# of spot pixel masks defined: "+spotListstr

    def get_xy_centers(self):
        '''
        A generalized approach to setting the x and y centers:

        Start off by checking if xCenters is none.  if yes, then get it from handles
        if no, then you are all set.

        if fine positioning has been done, than the centers are extracted from
        the graphics handles of the drawing objects for fine positioning

        if fine positioning has not been done, but rough positioning has
        then the x and y centers are taken from the rough positioning handles to the
        interior points.  these are stored redundantly for each handle object.

        if neither rough or fine positioning has been done and xCenters does not
        exist than raise error

        '''
        if self.xCenters is not None:
            # if x and y centers exist then they should be used as is
            # functions that do not directly specify x and y centers
            # should set x and y centers to default values.
            return
        elif self.fine_position_draw_points is not None:
            self.xCenters = [c.point.center[0] for c in self.fine_position_draw_points]
            self.yCenters = [c.point.center[1] for c in self.fine_position_draw_points]
            return
        elif self.rough_position_draw_points is not None:
            self.xCenters = self.rough_position_draw_points[0].h1.get_xdata()
            self.yCenters = self.rough_position_draw_points[0].h1.get_ydata()
            return
        else:
            raise ValueError("There are no defined spots")


    def roughPosition(self,Nx,Ny,dragRadius=4,pointMarkerSize=12,hexagonalOffset=0,colormap='gray',markercolor='blue'):
        """
        Use a GUI to define a trapezoidal grid of spot centers
        If there are spot centers stored in this object already, this method will overwrite them!
        It also stores the (row,column) positions of the spots as a last of 1-indexed tuples
        :param Nx: number of columns
        :param Ny: number of rows
        :param dragRadius: the size of the draggable circle shown in the GUI
        :param pointMarkerSize: the size of the grid points in the GUI
        :param colormap: the color map used for the base image. default is 'gray'
        :return: no return value
        """

        #set the x and y centers and fine tuned position markers to null values:
        self.xCenters=None
        self.yCenters=None
        #set the fine position to default
        self.fine_position_draw_points = None

        # define the row column indices in the arrayedanalysis object
        self.spotLocations=[(row+1,column+1) for row in range(Ny) for column in range(Nx)]
        self.Ncolumns=Nx
        self.Nrows=Ny

        bkImage=self.baseImage
        fig = plt.figure(num = 'Trapezoidial Interpolation Spot Adjustment')
        fig.set_facecolor('white')
        ax = fig.add_subplot(111)
        plt.imshow(bkImage,colormap)

        ax.set_xlim(0-dragRadius,bkImage.shape[1]+dragRadius)
        ax.set_ylim(bkImage.shape[0]+dragRadius,0-dragRadius)
        ax.set_aspect('equal')

        circles = []
        circles.append(patches.Circle((0,0), dragRadius, fc=markercolor, alpha=0.5, ))
        circles.append(patches.Circle((0,bkImage.shape[0]), dragRadius, fc=markercolor, alpha=0.5, ))
        circles.append(patches.Circle((bkImage.shape[1],0), dragRadius, fc=markercolor, alpha=0.5, ))
        circles.append(patches.Circle((bkImage.shape[1],bkImage.shape[0]), dragRadius, fc=markercolor, alpha=0.5, ))

        rowAlpha=chr(ord('A')+Ny-1)
        annotations = [plt.annotate("A1",(0,0),color="white",horizontalalignment='center', verticalalignment='center'),
                        plt.annotate("".join([rowAlpha,"1"]),(0,bkImage.shape[0]),color="white",horizontalalignment='center', verticalalignment='center'),
                        plt.annotate("".join(["A",str(Nx)]),(bkImage.shape[1],0),color="white",horizontalalignment='center', verticalalignment='center'),
                        plt.annotate("".join([rowAlpha,str(Nx)]),(bkImage.shape[1],bkImage.shape[0]),color="white",horizontalalignment='center', verticalalignment='center')]

        p = []
        for d in circles:
            p.append(d.center)
        p = np.asarray(p)
        xi, yi = barycentric_trapezoidial_interpolation(Nx,Ny,p,hexagonalOffset=hexagonalOffset)

        h1, = ax.plot(xi, yi, '.', markersize = pointMarkerSize, color = markercolor)

        drs = []
        for c, circ in enumerate(circles):
            ax.add_patch(circ)
            dr = DraggablePointForBarycentricInterpolation(circ,h1,ax, Nx, Ny,annotations[c],hexagonalOffset)
            dr.connect()
            drs.append(dr)


        plt.show()

        self.rough_position_draw_points = drs

    def fineTunePosition(self,markerRadius=3,colormap='gray',markercolor="blue",spotLabelsAlwaysOn=False):
        """
        Use a GUI to check the positions of the spots and manually adjust them if need be
        :param markerRadius: the radius of the draggable markers in the GUI. Default is 2.
                             Because these markers are drawn by matplotlib on top of a scaled MS image,
                             the the radius of the markers the radius of the spots may not always match exactly
        :param colormap: colormap of the base image. Default is 'gray'
        :param spotLabelsAlwaysOn: show Row/Column lables on the spots all the time?
        :return: no return value.
        """


        #xCenters and yCenters are required here and elsewhere.
        self.get_xy_centers()
        xRough=self.xCenters
        yRough=self.yCenters
        # now that x and y centers have been initalized, reset x and y centers
        self.xCenters=None
        self.yCenters=None

        fig = plt.figure(num = 'Fine Tune Spot Adjustment')
        fig.set_facecolor('white')
        ax = fig.add_subplot(111)
        plt.imshow(self.baseImage,cmap=colormap)
        ax.set_aspect('equal')

        drs = []
        circles = []
        annotations=[]
        L = len(xRough)
        for i in range(L):
            circ=patches.Circle((xRough[i],yRough[i]), markerRadius, fc=markercolor, alpha=0.5, )
            circles.append(circ)

            txt=alphaRowString(self.spotLocations[i])
            a=plt.annotate(txt,(xRough[i],yRough[i]),color="white",horizontalalignment='center', verticalalignment='center'   )
            a.set_animated(False)
            if not spotLabelsAlwaysOn:
                a.set_visible(False)
                annotations.append(a)

            ax.add_patch(circ)
            dr = DraggablePoint(circ,a,annotations)
            dr.connect()
            drs.append(dr)

        plt.show()

        self.fine_position_draw_points = drs

    def roughPosition_with_dialogs(self,colormap="gray",markercolor="blue"):
        params = get_default_params()

        arrayed_analysis_columns = params['arrayed_analysis_columns']
        arrayed_analysis_rows = params['arrayed_analysis_rows']
        arrayed_analysis_offset = params['arrayed_analysis_offset']

        arrayed_analysis_columns = int(input("Number of columns? leave blank for default (\"{:d}\") ".format(arrayed_analysis_columns)) or arrayed_analysis_columns)
        arrayed_analysis_rows = int(input("Number of rows? leave blank for default (\"{:d}\") ".format(arrayed_analysis_rows)) or arrayed_analysis_rows)
        arrayed_analysis_offset = float(input("Hexagonal Offset? This shifts every other line by this many spots. leave blank for default (\"{:f}\") ".format(arrayed_analysis_offset)) or arrayed_analysis_offset)

        params['arrayed_analysis_columns'] = arrayed_analysis_columns
        params['arrayed_analysis_rows'] = arrayed_analysis_rows
        params['arrayed_analysis_offset'] = arrayed_analysis_offset

        update_default_params(params)

        self.roughPosition(arrayed_analysis_columns,arrayed_analysis_rows,colormap=colormap,markercolor=markercolor,hexagonalOffset=arrayed_analysis_offset)



    def optimizeSpots(self,
                      halfboxsize=2,
                      optimizationrounds=3,
                      integrationRadius=2,
                      ionWeighting=None,
                      avoidOverlaps=True,
                      pixelwiseOverlapAvoidance=False,
                      overlapDistance_squared=None,
                      verbose=False,
                      progressbar=None,
                      raiseExceptions=False,
                      minimumScore=0):
        """
        Performs a local optimization to align the spot centers to maxima spots on the image

        the parameters affect the way the local optimization is run, but the defaults should be
        a good start.

        :param halfboxsize: How many pixels to the left, right, up and down should be compared
                            every round of the optimization (i.e. "how local" is the optimization).
                            If spots are farther apart from each other you can set this higher.
                            Also note it will increase the time it takes to run the algorithm.
                            Default is 2.
        :param optimizationrounds: How many cycles of optimization should be performed. Default is 3.
        :param integrationRadius: The radius of the spots used in calculations.
        :param ionWeighting: How much should each ion be weighted when calculating scores for each
                             spot location? this needs to be an array of floats the same length as
                             there are ions in the image. by default all ions are equally weighted
                             (i.e. if there's 3 ions, the default ends up being [1,1,1]
        :param avoidOverlaps: Should the optimizer try to avoid spots from overlapping with each other?
                              Default is True.
        :param pixelwiseOverlapAvoidance:  There are two methods of determining if two spots are overlapping:
                                           Distance-wise and pixel-wise. The former checks the distance between
                                           spots using the pythagorean theorem, while the latter checks if any of
                                           the pixels in a spot's integration map are shared by another spot.
                                           pixel-wise overlap checking is much slower, so only use it if
                                           distance-wise is not satisfactory. Default is False.
        :param overlapDistance_squared: The minimum distance two spots have to be from each other,
                                        from center to center, to not be considered overlapping
                                        Only used if pixelwiseOverlapAvoidance is False.
                                        By default the overlapDistance is integrationRadius*2
        :param verbose: Prints the progress and any irregularities that occur during the optimization. Default is False
        :param raiseExceptions: Raise exceptions if either:
                                1) spots are so close to the image's edge that the algorithm tries to place spots there
                                2) It's impossible to find a location for a spot that satisfies the minimumScore and
                                overlap avoidance requirements.
                                Default is False.
                                Even if this is set to False, an exception will /still/ be raised if the best score for
                                a spot is zero, because this probably means that there's not a single location that
                                the optimizer could choose that didn't overlap with other spots.
        :param minimumScore: Require that at least a score this high is obtainable before moving a spot to a new
                             location. If there are spots missing in the grid, you may want to set this. Default is 0.
        :return: no return value
        """

        #xCenters and yCenters are required here and elsewhere.
        self.get_xy_centers() #They must be calculated from either the rough or fine position handles

        if not overlapDistance_squared:
            overlapDistance_squared=(integrationRadius*2.0)**2

        imStack2=self.imStack
        imWidth=imStack2.shape[1]
        imHeight=imStack2.shape[0]
        xEdges, yEdges = np.meshgrid(list(range(imWidth)), list(range(imHeight)), sparse=False, indexing='xy')

        xCenter=self.xCenters
        yCenter=self.yCenters

        numberOfSpots=len(xCenter)
        spotMaskCache=np.empty(numberOfSpots, dtype=np.ndarray)
        if not ionWeighting:
            ionWeighting=np.empty(len(self.ions))
            ionWeighting.fill(1.)
        for round in range(optimizationrounds):
            totalscore=0
            minscore=-1
            maxscore=-1
            for i in range(numberOfSpots):
                    best=-1
                    bestX=xCenter[i]
                    bestY=yCenter[i]
                    for newX in (list(range(-halfboxsize,halfboxsize+1))+xCenter[i]):
                        for newY in (list(range(-halfboxsize,halfboxsize+1))+yCenter[i]):
                            if newX<0 or newX>=imWidth or newY<0 or newY>=imHeight:
                                if(raiseExceptions):
                                    raise IndexError("a location outside of the image was tried for a spot")
                                else:
                                    if(verbose):
                                        print("a location outside of the image was tried for spot #",i,"(",alphaRowString(self.spotLocations[i]),"), but ignored")
                                    continue
                            currentSpot=oneSpotMask(xEdges,yEdges,newX,newY,integrationRadius)
                            assert (len(currentSpot)>0)
                            if avoidOverlaps:
                                if pixelwiseOverlapAvoidance:
                                    if doesThisOverlap_pixelwise(spotMaskCache,currentSpot,i,numberOfSpots):
                                        continue
                                elif doesThisOverlap_distancewise(newX,newY,xCenter,yCenter,i,overlapDistance_squared):
                                    continue

                            #because of the way the spot is defined, it's not always the same number of pixels,
                            #so we devide by the size of the spot to get the /average/ intensity
                            result=sum(sumPixels(currentSpot,imStack2)*ionWeighting)/len(currentSpot)
                            spotMaskCache[i]=currentSpot
                            if result>best:
                                best=result
                                bestX=newX
                                bestY=newY

                    if(best>minimumScore):
                        xCenter[i]=bestX
                        yCenter[i]=bestY
                    else:
                        if raiseExceptions or best<0: #if the score is <0 something bad must be going on
                            raise SpotOptimizationException()
                        elif(verbose):
                            print("Best score of spot # %d is %d but need > %d. Location stays as it was before."%(i,int(best), minimumScore))
                    cyclenumber = numberOfSpots*round+i
                    if(progressbar):
                        progressbar.value=100*cyclenumber/(numberOfSpots*optimizationrounds)
                    if(verbose): #to get the stats for this round
                        totalscore+=best
                        if(minscore==-1):
                            minscore=best
                        minscore=min(minscore,best)
                        maxscore=max(maxscore,best)
                        if(cyclenumber%100==99 and not progressbar):
                            print("{:d}% done with the optimization process".format(int(100*cyclenumber/(numberOfSpots*optimizationrounds))))
                            sys.stdout.flush()
            print("done with optimization round %d of %s"%(round+1,optimizationrounds))
            if(verbose):
                print("total score:",totalscore,"\t average spot score:",totalscore/numberOfSpots)
                print("low spot score:",minscore,"\t high spot score:",maxscore)
            sys.stdout.flush()

        self.xCenters=xCenter
        self.yCenters=yCenter
        print("optimization routine completed. new spot x and y positions saved.")
        sys.stdout.flush()


    def optimizeSpots_with_dialogs(self):

        params = get_default_params()

        arrayed_analysis_radius = params['arrayed_analysis_radius']
        arrayed_analysis_minScore = params['arrayed_analysis_minScore']

        linebreak=ipywidgets.HTML("<br>")
        displayBox=ipywidgets.VBox()
        integrationRadiusBox=ipywidgets.BoundedFloatText(value=arrayed_analysis_radius)
        displayBox.children+=(ipywidgets.HBox(children=(ipywidgets.HTML("Integration radius. (recommended: use the radius of your spots)"),integrationRadiusBox)),)
        roundsBox=ipywidgets.BoundedIntText(value=3)
        displayBox.children+=(ipywidgets.HBox(children=(ipywidgets.HTML("How many rounds of optimization should be performed?&nbsp&nbsp"),roundsBox)),)
        halfboxsizeBox=ipywidgets.BoundedIntText(value=2)
        displayBox.children+=(ipywidgets.HBox(children=(ipywidgets.HTML("How far away from the current location should the algorithm search every round? It searches this many pixels, up, down, left and right.&nbsp"),halfboxsizeBox)),)

        overlapBox=ipywidgets.Checkbox(value=True)
        displayBox.children+=(ipywidgets.HBox(children=(ipywidgets.HTML("Prevent neighboring spots from overlapping?"),overlapBox)),)
        ionWeightBoxes=[]
        for i in self.ions:
            newbox=ipywidgets.BoundedFloatText(value=1,max=1)
            ionWeightBoxes.append(newbox)
            displayBox.children+=(ipywidgets.HBox(children=(ipywidgets.HTML("Weighting for ion '{:f}'".format(i)),newbox)),)

        calcButton=ipywidgets.Button(description="Calculate scores for current spot locations")
        calcResults=ipywidgets.HTML()
        displayBox.children+=(linebreak,calcButton,calcResults,linebreak)

        minScoreBox=ipywidgets.BoundedFloatText(value=arrayed_analysis_minScore,max=1000000)
        displayBox.children+=(ipywidgets.HBox(children=(ipywidgets.HTML("Minimum score necessary to move spot."),minScoreBox,)),
                             ipywidgets.HTML("(if every location on your grid is occupied by a spot, you safely can leave the minimum score at 0. Setting a minimum score will prevent spot locations from converging on artifacts if there is no real spot there)<br>"))

        optimizeButton=ipywidgets.Button(description="Optimize Spots!")

        progressbar=ipywidgets.FloatProgress()
        progressbar.visible=False
        displayBox.children+=(optimizeButton,progressbar)
        IPython.display.display(displayBox)

        def do_calculate(widget):
            self.get_xy_centers()

            results=[]
            ionweights=[]
            imWidth=self.imStack.shape[1]
            imHeight=self.imStack.shape[0]
            numberOfSpots=len(self.xCenters)
            for box in ionWeightBoxes:
                ionweights.append(box.value)
            xEdges, yEdges = np.meshgrid(list(range(imWidth)), list(range(imHeight)), sparse=False, indexing='xy')
            for i in range(numberOfSpots):
                currentSpot=oneSpotMask(xEdges,yEdges,self.xCenters[i],self.yCenters[i],integrationRadiusBox.value)
                result=sum(sumPixels(currentSpot,self.imStack)*ionweights)/len(currentSpot)
                results.append(result)
            calcResults.value="{:d} Spots calculated.<br>Low spot score: {:f}<br>High spot score: {:f}<br>Mean spot score: {:f}<br>Median spot score: {:f}".format(
                len(results),min(results),max(results),np.mean(results),np.median(results))

        def do_optimize(widget):
            arrayed_analysis_radius=integrationRadiusBox.value
            arrayed_analysis_minScore=minScoreBox.value

            params['arrayed_analysis_radius'] = arrayed_analysis_radius
            params['arrayed_analysis_minScore'] = arrayed_analysis_minScore

            update_default_params(params)

            ionweights=[]
            for box in ionWeightBoxes:
                ionweights.append(box.value)
            progressbar.visible=True
            self.optimizeSpots(halfboxsizeBox.value,
                               roundsBox.value,
                               arrayed_analysis_radius,
                               ionWeighting=ionweights,
                               avoidOverlaps=overlapBox.value,
                               progressbar=progressbar,
                               minimumScore=arrayed_analysis_minScore)

        calcButton.on_click(do_calculate)
        optimizeButton.on_click(do_optimize)


    def generateSpotList(self, integrationRadius = None):
        '''
        :param integrationRadius is used by one spot mask to select pixels that are less than this distance from the x,y center
        of each spot.
        '''

        #xCenters and yCenters are required here and elsewhere.
        self.get_xy_centers() #They must be calculated from either the rough or fine position handles

        params = get_default_params()
        #Answer two questions:
        #1) use  value from kwargs or stored value?
        #2) update stored value?
        if not integrationRadius:
            integrationRadius == params['arrayed_analysis_radius']
        elif integrationRadius != params['arrayed_analysis_radius']:
            params['arrayed_analysis_radius'] = integrationRadius
            update_default_params(params)

        xEdges, yEdges = np.meshgrid(list(range(self.imStack.shape[1])), list(range(self.imStack.shape[0])), sparse=False, indexing='xy')

        myPixels = []
        tallies = {}
        for x, y in zip(self.xCenters, self.yCenters):
            idx = oneSpotMask(xEdges, yEdges, x, y, integrationRadius)
            myPixels.append(idx)
            if len(idx) not in tallies:
                tallies[len(idx)] = 0
            tallies[len(idx)] += 1
        self.spotList = myPixels
        print("{:d} spots generated. number of spots with N pixels:{}".format(len(myPixels), tallies))
        return myPixels

    def generateMaskedImage(self,spotList=None):
        """
        Generate a mask image that indicates which pixels are included in the spotList
        You can view this image with matplotlib
        If you want to see the spots labeled, use the showMaskedImage() method.

        :param spotList: List of lists of pixels that defines the locations of the spots on the image
                            The default is the last-calculated spotlist for this image.
        :return: An image that can be viewed using matplotlib's imshow()
        """
        _spotList = spotList

        if not spotList:
            if not self.spotList:
                raise ValueError("Need to either pass a spot list in the method argument,"+
                                 "or have generated a spotList using generateSpotList at some point")
            _spotList = self.spotList

        mask = np.zeros(self.baseImage.shape)

        for spot in _spotList:
            for i in spot:
                mask[i[0], i[1]] = 1
        return mask


    def showMaskedImage(self,spotList=None,alphaRows=True):
        """
        Generates the Mask Image using generateMaskedImage(spotList=spotList) and displays it using matplotlib,
        nicely annotated with the identity of each spot
        :param alphaRows: If this is set to True, the image will use A,B,C... for the rows.
                          If it's set to False, it'll plot a numeric tuple
        """

        if spotList is None:
            #global arrayed_analysis_radius
            #%store -r arrayed_analysis_radius
            spots=self.generateSpotList(integrationRadius=get_default_params()['arrayed_analysis_radius'])


        maskedimg=self.generateMaskedImage(spotList=spotList)
        plt.figure(num = 'Masked Image')
        plt.imshow(maskedimg)
        #ap={"linewidth":0, "facecolor":"g", "width":2,"headwidth":2}#,"frac":0}#, "headlength":0}
        #ap={"arrowstyle":"->, head_width=.3", "facecolor":"g","edgecolor":"g","linewidth":2}
        ap={"arrowstyle":"-", "facecolor":"g","edgecolor":"g","linewidth":2}
        xshift = min(4,(max(self.xCenters)-min(self.xCenters))/self.Ncolumns/4.0)
        yshift = min(4,(max(self.yCenters)-min(self.yCenters))/self.Nrows/4.0)
        for i in range(len(self.xCenters)):
            txt=alphaRowString(self.spotLocations[i]) if alphaRows else str(self.spotLocations[i])
            plt.annotate(txt,(self.xCenters[i],self.yCenters[i]),xytext=(self.xCenters[i]-xshift,self.yCenters[i]-yshift),color="g",horizontalalignment='right', verticalalignment='bottom',arrowprops=ap)
        plt.show()


    def writeResultTable(self,fileName="",spotList=None,minPixelIntensity=0,alphaRows=False):
        """

        :param fileName: filename to write to. will automatically be appended with a .csv extension.
                            Default is will use current date and time
        :return:
        """

        if fileName:
            actualFileName="{}.csv".format(fileName)
        else:
            dt = datetime.datetime.now()
            actualFileName="openmsi_arrayed_analysis_results_{:d}-{:d}-{:d}_{:d}h{:d}.csv".format(dt.year,dt.month,dt.day,dt.hour,dt.minute)


        fileHandler=open(actualFileName,'w')

        _spotList=spotList

        if not spotList:
            if not self.spotList:
                raise ValueError("Need to either pass a spot list in the method argument,"+
                                 "or have generated a spotList using generateSpotList at some point")
            _spotList=self.spotList

        fileHandler.write('index,file,row,column,row-centroid,col-centroid,')
        for i in self.ions:
            fileHandler.write('%5.4f Sum,' % i)
            fileHandler.write('%5.4f Max,' % i)
            fileHandler.write('%5.4f Mean,' % i)
            fileHandler.write('%5.4f Median,' % i)
            fileHandler.write('%5.4f NumPixels,' % i)
        fileHandler.write('\n')

        for i,myPixel in enumerate(_spotList): #how many spots

            fileHandler.write('%d,%s,%s,%s,%f,%f,' % ( i, self.filename,
                                                             chr(ord('A')+self.spotLocations[i][0]-1) if alphaRows else str(self.spotLocations[i][0]),
                                                             self.spotLocations[i][1], np.mean(myPixel[:,0]), np.mean(myPixel[:,1]) ) )
            for j,ion in enumerate(self.ions): #how many ions
                values = []
                for coord in myPixel: #how many pixels per spot
                    if self.imStack[coord[0],coord[1],j] > minPixelIntensity:
                        #print self.imStack[coord[0],coord[1],i]
                        #print coord[0],coord[1],i
                        #accumulate a list of peak height or
                        #peak area values for each pixel
                        #assigned to each spot
                        values.append(self.imStack[coord[0],coord[1],j])
                if len(values) > 0:
                    fileHandler.write('%f,%f,%f,%f,%d,' % (np.sum(values),np.max(values),np.mean(values),np.median(values),len(values)))
                else:
                    fileHandler.write('%d,%d,%d,%d,%d,' % (0,0,0,0,len(values)))

            fileHandler.write('\n')
        fileHandler.close()
        IPython.display.display(IPython.display.FileLink(actualFileName,
                                 result_html_prefix="Click the link below to access the results file:<br>",
                                 result_html_suffix="""<br>Open it in Microsoft Excel or your favorite data analysis program.<br>
                                                You should now be done using this tool, but if you decide you want to
                                                further optimize your spot placement, make sure to re-run the
                                                notebook cells to update your results.
                                                <br><br>Thank you for using the OpenMSI Arrayed Analysis tool!"""))



    def resultsDataFrame(self,spotList=None,minPixelIntensity=0,multiIndex=True,alphaRows=False):
        """
        Generates a Pandas dataframe that summarizes the arrayed data.
        :param spotList: List of lists of pixels that defines the locations of the spots on the image
                            The default is the last-calculated spotlist for this image.
        :param minPixelIntensity:
                            Minimum intensity that a pixel needs to be higher than, to be included in the
                            calculations. Pixels at or below this theshold will not be included when calculating
                            any of the metrics like sum, min, max, mean, or median pixel intensity. Default is 0.
        :param multiIndex:
                            If true, creates a dataframe with a multiindex for the columns. If false, the
                            indexes for the columns will be 2-tuples (ion, metric).
        :param alphaRows:
                            If True, sets the indexes of the data frame to strings with an alphabetical row
                            identifier. alphaRows=False sets the indexes to 2-tuples (row,column).
        :return:            A Pandas dataframe with, for each ion, and each spot, the sum, min, max, mean, median
                            and number of pixels more intense than the minPixelIntensity.
        """

        _spotList=spotList

        if not spotList:
            if not self.spotList:
                raise ValueError("Need to either pass a spot list in the method argument,"+
                                 "or have generated a spotList using generateSpotList at some point")
            _spotList=self.spotList

        df= None

        rowIndexes=self.spotLocations
        if alphaRows:
            rowIndexes=[alphaRowString(sl) for sl in self.spotLocations]


        if multiIndex:
            df=pd.DataFrame(index=rowIndexes,
                dtype='float64',columns=pd.MultiIndex.from_product([self.ions,
                    ['sum','mean','median','min','max','num_pixels']],names=['ion','descriptor'],sortorder=0))#TURN INDEX INTO (ROW,COLUMN) EVENTUALLY!!!
        else:

            colnames=['row','column','horizontal_coordinate','vertical_coordinate']
            colnames+=[(i,x) for i in self.ions for x in ['sum','mean','median','min','max','num_pixels']]

            df=pd.DataFrame(index=rowIndexes,columns=colnames)

        for s,spot in enumerate(_spotList): #how many spots
            if not multiIndex:
                df.set_value(rowIndexes[s],'horizontal_coordinate',np.mean(spot[:,0]))
                df.set_value(rowIndexes[s],'vertical_coordinate',np.mean(spot[:,1]))
            for i,ion in enumerate(self.ions): #how many ions
                values = []
                for coord in spot: #how many pixels per spot
                    if self.imStack[coord[0],coord[1],i] > minPixelIntensity:
                        values.append(self.imStack[coord[0],coord[1],i])
                if len(values) > 0:
                    df.set_value(rowIndexes[s],(ion,'sum'),np.sum(values))
                    df.set_value(rowIndexes[s],(ion,'max'),np.max(values))
                    df.set_value(rowIndexes[s],(ion,'min'),np.min(values))
                    df.set_value(rowIndexes[s],(ion,'median'),np.median(values))
                    df.set_value(rowIndexes[s],(ion,'mean'),np.mean(values))
                    df.set_value(rowIndexes[s],(ion,'num_pixels'),len(values))

                else:
                    df.set_value(rowIndexes[s],(ion,'sum'),0)
                    df.set_value(rowIndexes[s],(ion,'num_pixels'),0)

        return df


class OpenMSIsession(object):
    """
    This object represents an OpenMSI session.
    """
    def __init__(self,username=""):
        """you won't want to call the constructor, use the 'login' function
        to create an OpenMSIsession object"""
        # self.requests_session = requests.Session()
        # self.username=username
        self.filename=None

    # def getFilelist(self):
        # payload = {'format':'JSON','mtype':'filelistView'}
        # url = 'https://openmsi.nersc.gov/qmetadata'
        # r = self.requests_session.get(url,params=payload)
        # r.raise_for_status()
        # fileList = json.loads(r.content.decode('utf-8'))
        # return list(fileList.keys())

    # def fileSelector(self):
    #     """
    #     :return: An ipython widget containing a file selector. If you simply have this method as the last
    #                 line of a notebook cell, you'll see it. otherwise you need to do IPython.display.display(fileSelector())
    #     """
    #     params = get_default_params()
    #     arrayed_analysis_default_filename = params['arrayed_analysis_default_filename']
    #     myFiles = self.getFilelist()
    #     myFiles.sort()
    #     myFiles = [path.join(path.basename(path.dirname(p)),path.basename(p)) for p in myFiles]

    #     fileSelector=ipywidgets.Select(options=myFiles,  height=300,width=600)
    #     if arrayed_analysis_default_filename in myFiles:
    #         fileSelector.value = arrayed_analysis_default_filename
    #     else:
    #         fileSelector.value=myFiles[0]

        # title=ipywidgets.HTML(value="Pick the file you want to load here") #IPN2: HTMLWidget
        # #IPython.display.display(title)
        # #IPython.display.display(fileSelector)
        # def _fileSelector_updated(widget=None):
        #     if(self.filename!=fileSelector.value):
        #         self.filename=fileSelector.value
        #         arrayed_analysis_default_filename = self.filename
        #         params['arrayed_analysis_default_filename'] = arrayed_analysis_default_filename
        #         update_default_params(params)
        # try:
        #     fileSelector.observe(_fileSelector_updated)
        # except AttributeError:
        #     fileSelector.on_trait_change(_fileSelector_updated)
        # _fileSelector_updated()
        # return ipywidgets.Box(children=(title,fileSelector))

    def getArrayedImage(self,ions,massRange,massRangePercent=False,filename=None,massRangeReductionStrategy=None,expIndex=0,dataIndex=0,verbose=True,remoteReduce=True):
        """
        Downloads defined ion slices from an OpenMSI image and returns a new ArrayedImage file
        :param ions: Ihe ion (m/z) slices you want to download. A list of floats
        :param massRange: Fetch ion data this much +/- the ions defined.
        :param massRangePercent: Should the number in massRange be interpreted as a percent of the ion?.
        :param filename: If this is not set, it'll use the filename selected in the file selector.
                if no filename is selected there, a ValueError exception will be raised
        :param massRangeReductionStrategy: The downloaded mass range needs to be reduced into
                                           a single number for each ion. People disagree on how
                                           to do this, so we allow a variety of strategies
                                           defined by classes that extend MassRangeReductionStrategy.
                                           The MassReductionStrategies available right now are
                                           - PeakArea: takes the sum of the entire mass range
                                           - PeakHeight: takes the maximum of the entire mass range
                                           - AreaNearPeak: finds the maximum of the mass range, and sums
                                                           a defined number of bins to the left and to
                                                           the right of it.
                                           You will need to instantiate one of these classes and pass it
                                           as an argument here. Default is a new PeakArea instance
        :param expIndex: Which OpenMSI experiment index to download
        :param dataIndex: Which OpenMSI data index to download
        :param verbose: If true, prints progress on which ion it's currently loading
        :param remoteReduce: Perform data reductions remotely on the server if possible (default=True). Set to
                             False to load all data and reduce localle (usually slower).
        :return: a new ArrayedImage file that contains the reduced data.
        """
        if massRangeReductionStrategy is None:
            massRangeReductionStrategy = PeakArea()

        #add path prefix to account for narrow file selector box in recent ipython widgets upgrade
        #2016-09-12
        #remove this once widget select box is wide enough to show full path

        originalSize = get_image_size(self.filename,expIndex,dataIndex)

        newImage=ArrayedImage(originalSize,ions,self.filename,expIndex,dataIndex,getMZ(None,self.filename,expIndex,dataIndex))
        #The new ArrayedImage returned has an empty imStack
        #To populate it, first we'll download the raw data and then reduce it into one slice for every ion
        reduceOnServer = remoteReduce and massRangeReductionStrategy.supportsRemoteReduce()
        for i,ion in enumerate(newImage.ions):
            startTime = time.time()
            realMassRange = massRange if not massRangePercent else massRange*ion*0.01
            if verbose:
                print ("loading ion {:d} of {:d}. m/z = {:f} +/- {:f}".format(i+1,len(newImage.ions),ion,realMassRange))
                sys.stdout.flush()
            
            newImage.imStack[:,:,i] = get_image(self.filename,ion-realMassRange,ion+realMassRange,expIndex,dataIndex)
            # newImage.imStack[:,:,i] = image.sum(axis=2)
            # data = np.asarray(json.loads(r.content.decode('utf-8')))
            # if reduceOnServer:
                # newImage.imStack[:,:,i] = data
            # else:
                # if verbose:
                    # print("Performing mass range reduction locally...")
                # newImage.imStack[:,:,i] = massRangeReductionStrategy.reduceImage(data)
            # if verbose:
                # print ("Time to load ion: " + str(time.time() - startTime) + " seconds")

        newImage.baseImage = np.sum(newImage.imStack,2)
        print("Image has been loaded.")
        print(newImage.baseImage.size)
        sys.stdout.flush()
        return newImage

    
    def imageLoader_with_dialogs(self):
        params = get_default_params()

        expIndex=ipywidgets.BoundedIntText(value=0)
        expIndexBox=ipywidgets.HBox(children=(ipywidgets.HTML("Set the Experiment Index you want to load:"),expIndex))
        dataIndex=ipywidgets.BoundedIntText(value=0)
        dataIndexBox=ipywidgets.HBox(children=(ipywidgets.HTML("Set the Data Index you want to load:"),dataIndex))


        ionSet=set(params['openmsi_default_ions'])
        ionList=ipywidgets.Select(options=[str(x) for x in sorted(ionSet)])
        addIonBox=ipywidgets.BoundedFloatText(description="Add an ion:",max=10000)
        addIonButton=ipywidgets.Button(description="Add Ion",tooltip="Add the ion in the above box to the list of ions")
        removeIonButton=ipywidgets.Button(description="Remove Ion",tooltip="Remove the selected ion to the list of ions")
        ionSelectionEditBox=ipywidgets.VBox(children=(addIonBox,addIonButton,removeIonButton))
        ionSelectionBox=ipywidgets.HBox(children=(ipywidgets.HTML("Select which ions you want to load:&nbsp"),ionList,ionSelectionEditBox))

        def addion(widget):
            ionSet.update({addIonBox.value})
            ionList.options=[]
            ionList.options=[str(x) for x in sorted(ionSet)]
            params['openmsi_default_ions'] = sorted(ionSet)
            update_default_params(params)

        def removeion(widget):
            ionSet.difference_update({float(ionList.value)})
            ionList.options=[]
            ionList.options=[str(x) for x in sorted(ionSet)]
            params['openmsi_default_ions'] = sorted(ionSet)
            update_default_params(params)

        addIonButton.on_click(addion)
        removeIonButton.on_click(removeion)

        rangeCheckBox=ipywidgets.RadioButtons(options=["absolute m/z values","% of m/z"])
        rangeNumber=ipywidgets.BoundedFloatText(description="+/- range",value=0.5)
        rangeBox=ipywidgets.HBox(children=(ipywidgets.HTML("Determine m/z +/- range to consider:&nbsp"),rangeCheckBox,rangeNumber))
        reductionCheckBox=ipywidgets.RadioButtons(options=["Sum of all data points in mass range (i.e., area under the curve)","Max data point in range (i.e. peak height)","n data points around the max"])
        Ndatapoints=ipywidgets.BoundedIntText(description="number of data points",value=2)
        #Ndatapoints.visible=False
        def obs(widget):
            try:
                Ndatapoints.layout.visibility=("visible" if reductionCheckBox.value=="n data points around the max" else "hidden")
            except AttributeError:
                Ndatapoints.visible=(reductionCheckBox.value=="n data points around the max")
        try:
            reductionCheckBox.observe(obs)
        except AttributeError:
            reductionCheckBox.on_trait_change(obs)

        obs(Ndatapoints)

        reductionBox=ipywidgets.HBox(children=(ipywidgets.HTML("Mass range reduction strategy:&nbsp"),reductionCheckBox,Ndatapoints))

        OKbutton=ipywidgets.Button(description="Load Image!")

        linebreak=ipywidgets.HTML("<br>")
        # fileSelector=self.fileSelector()

        IPython.display.display(ipywidgets.VBox(children=(expIndexBox,dataIndexBox,linebreak,ionSelectionBox,linebreak,rangeBox,linebreak,reductionBox,linebreak,OKbutton)))

        def do_load(widget):
            print("Loading image...")
            reductionStrategy = None
            if reductionCheckBox == "Sum of all data points in mass range (i.e., area under the curve)":
                reductionStrategy=PeakArea()
            elif "Max data point in range (i.e. peak height)":
                reductionStrategy=PeakHeight()
            elif "n data points around the max":
                reductionStrategy=AreaNearPeak(halfpeakwidth=Ndatapoints.value)
            else:
                raise AssertionError("this error should not be happening...")
            img=self.getArrayedImage(params['openmsi_default_ions'], massRange=rangeNumber.value,massRangePercent=(rangeCheckBox.value=="% of m/z"),expIndex=expIndex.value,dataIndex=dataIndex.value,massRangeReductionStrategy=reductionStrategy,verbose=True)
            self.img = img

        OKbutton.on_click(do_load)

    def getSpotSpectra(self,img,spotList=None,alphaRows=True,verbose=False):
        """
        Get an average mass spectrum for each of the spots in an image.
        :param img: An ArrayedImage. If it does not have spots defined yet, this function will call
                    generateSpotList(integrationRadius=get_default_params()['arrayed_analysis_radius']) on the image first.
        :param spotList: List of lists of pixels that defines the locations of the spots on the image
                            The default is the last-calculated spotlist for this image.
                            If you supply your own spot list, the column names will just be integers,
                            because the function can't be sure if the spots passed are the same spots
                            that are defined in the image.
        :param alphaRows:
                            If True, sets the column names of the data frame to strings with an alphabetical
                            identifier. alphaRows=False sets the column names to 2-tuples (row,column).
                            Default is True, ignored if spotList is defined.
        :param verbose:     If Ture, ouput which spot's spectrum just finished the loading process
        :return:     A dataframe with intensities at various m/z values.
                     Row indexes are m/z values and columns correspond to different spots
                     (Be aware this is different from how the resultsDataFrame is laid out!!)
        """

        _spotList=spotList
        colIndexes=None

        if not spotList:
            if not img.spotList:
                raise ValueError("Need to either pass a spot list in the method argument,"+
                                 "or have generated a spotList using generateSpotList at some point")
            _spotList=img.spotList
            colIndexes=img.spotLocations
        else:
            colIndexes=range(len(spotList))


        if alphaRows:
            colIndexes=[alphaRowString(sl) for sl in img.spotLocations]



        payload = {'file':img.filename,
          'expIndex':img.expIndex,'dataIndex':img.dataIndex,'qspectrum_viewerOption':'0',
          'qslice_viewerOption':'0',
          'col':0,'row':0,
          'findPeak':'0','format':'JSON'}
        url = 'https://openmsi.nersc.gov/qmz'
        r = self.requests_session.get(url,params=payload)
        r.raise_for_status()
        data = json.loads(r.text)
        mz = np.asarray(data[u'values_spectra'])

        dataframe = pd.DataFrame(index=mz, dtype='float64',columns=colIndexes)

        payload = {'file':img.filename,
                      'expIndex':img.expIndex,'dataIndex':img.dataIndex,'qspectrum_viewerOption':'0',
                  'qslice_viewerOption':'0','operations':'[{"reduction":"mean","axis":0,"min_dim":2}]',
                      'findPeak':'0','format':'JSON'}
        url = 'https://openmsi.nersc.gov/qspectrum'

        for i,coord in enumerate(_spotList):
            payload['col'] = '[' + ','.join([str(c[1]) for c in coord]) + ']'
            payload['row'] = '[' + ','.join([str(c[0]) for c in coord]) + ']'
            r = self.requests_session.get(url,params=payload)
            data = json.loads(r.text)
            dataframe.iloc[:,i]=data[u'spectrum']
            if(verbose):
                print("Finished loading spectrum {:d} out of {:d}".format(i+1,len(_spotList)))

        return dataframe


# def login(username=""):
#     """
#     Args:
#         username: If the username is left blank, the function will ask for a username
#     """
#     if username:
#         arrayed_analysis_default_username=username
#     else:
#         params = get_default_params()
#         arrayed_analysis_default_username = params['arrayed_analysis_default_username']
#         arrayed_analysis_default_username = input("NERSC username? leave blank for default (\"" + arrayed_analysis_default_username + "\") ") or arrayed_analysis_default_username
#         params['arrayed_analysis_default_username'] = arrayed_analysis_default_username
#         update_default_params(params)

#     password = getpass.getpass(prompt="Enter password for user \"" + arrayed_analysis_default_username + "\"")

#     print("Attempting to log in...")
#     sys.stdout.flush()
#     newOpenMSIsession=OpenMSIsession(arrayed_analysis_default_username)
#     authURL = 'https://openmsi.nersc.gov/client/login'
#     # Retrieve the CSRF token first
#     r= newOpenMSIsession.requests_session.get(authURL)  # sets
#     r.raise_for_status()
#     csrftoken = newOpenMSIsession.requests_session.cookies['csrftoken']
#     login_data = dict(username=arrayed_analysis_default_username, password=password, csrfmiddlewaretoken=csrftoken)
#     result = newOpenMSIsession.requests_session.post(authURL, data=login_data, headers=dict(Referer=authURL)).url[-5:]
#     IPython.display.clear_output()
#     if(result=="login"):
#         print("Password for user \"" + arrayed_analysis_default_username + "\" was likely wrong, re-run this cell to try again")
#     elif(result=="index"):
#         print("Login appears to be successful!")
#     else:
#         print("Not sure if login was successful, try continuing and see what happens")
#     sys.stdout.flush()
#     return newOpenMSIsession

def get_image(my_file='/Users/bpb/Downloads/20250131_ZD_PlateA.h5',min_mz=650,max_mz=700,
                    my_experiment=0,
                    my_data_index=0,
                    my_slice=None):
    f = omsi_file(my_file, 'r' )
    #Get the number of experiments
    # num_exp = f.get_num_experiments()
    # print(num_exp)
    #Get the first experiment. 
    #exp0  is an object of the type omsi_file_experiment For more information execute:
    #help( omsi_file_experiment )
    exp = f.get_experiment(my_experiment)
    # info = exp0.get_instrument_info()
    # print(info)
    # p = f.get_experiment_path(0)
    # print(p)
    d = exp.get_msidata(data_index=my_data_index)
    mzdata = exp.get_instrument_info().get_instrument_mz()    
    mzdata = mzdata[:]
    idx_lo = np.argmin(np.abs(mzdata-min_mz))
    idx_hi = np.argmin(np.abs(mzdata-max_mz))
    my_slice = d[:,:,idx_lo:idx_hi].sum(axis=2)
    f.close_file()
    return my_slice

def get_image_size(my_file='/Users/bpb/Downloads/20250131_ZD_PlateA.h5',
                my_experiment=0,
                my_data_index=0):
    f = omsi_file(my_file, 'r' )
    #Get the number of experiments
    # num_exp = f.get_num_experiments()
    # print(num_exp)
    #Get the first experiment. 
    #exp0  is an object of the type omsi_file_experiment For more information execute:
    #help( omsi_file_experiment )
    exp = f.get_experiment(my_experiment)
    # info = exp0.get_instrument_info()
    # print(info)
    # p = f.get_experiment_path(0)
    # print(p)
    d = exp.get_msidata(data_index=my_data_index)
    
    f.close_file()
    return d.shape

def getMZ(client,filename,expIndex,dataIndex):
    f = omsi_file(filename, 'r' )
    #Get the number of experiments
    # num_exp = f.get_num_experiments()
    # print(num_exp)
    #Get the first experiment. 
    #exp0  is an object of the type omsi_file_experiment For more information execute:
    #help( omsi_file_experiment )
    exp = f.get_experiment(expIndex)
    # info = exp0.get_instrument_info()
    # print(info)
    # p = f.get_experiment_path(0)
    # print(p)
    d = exp.get_msidata(data_index=dataIndex)
    mzdata = exp.get_instrument_info().get_instrument_mz()    
    mzdata = mzdata[:]
    f.close_file()
    return mzdata
    # payload = {'file':filename,
    #       'expIndex':expIndex,'dataIndex':dataIndex,'qspectrum_viewerOption':'0',
    #       'qslice_viewerOption':'0',
    #       'col':0,'row':0,
    #       'findPeak':'0','format':'JSON'}
    # url = 'https://openmsi.nersc.gov/qmz'
    # r = client.get(url,params=payload)
    # r.raise_for_status()
    # data = json.loads(r.content.decode('utf-8'))
    # return np.asarray(data[u'values_spectra'])

def oneSpotMask(xEdges,yEdges,x,y,integrationRadius):
    return np.argwhere(((x - xEdges)**2 + (y - yEdges)**2)**0.5 < integrationRadius)

def sumPixels(pixelMask,imageStack):
    values = []
    for j, coord in enumerate(pixelMask): #how many pixels per spot
        values.append(imageStack[coord[0],coord[1],:])
    return sum(values)
    #sum (values) returns a vector with one entry per ion,

def doesThisOverlap_pixelwise(spotMaskCache,spotMask,ignoreThisSpotNumber,numberOfSpots,verbose=False):
    for pixel in spotMask:
        for i in range(numberOfSpots):
            if (i != ignoreThisSpotNumber) and (spotMaskCache[i] is not None) and np.any(np.all(spotMaskCache[i]==pixel,1)):
                if (verbose):
                    print("yikes! spot #",ignoreThisSpotNumber,",",pixel,"is in spot #",i)
                return True
    return False

def doesThisOverlap_distancewise(newX,newY,xCenter,yCenter,ignoreThisSpotNumber,distance_squared,verbose=False):
    for i in range(len(xCenter)):
        if (i != ignoreThisSpotNumber) and ((newX-xCenter[i])**2+(newY-yCenter[i])**2<=distance_squared):
            if (verbose):
                print("yikes! spot #",ignoreThisSpotNumber,"at",newX,",",newY,"is",((newX-xCenter[i])**2+(newY-yCenter[i]))**0.5,"from",i)
            return True
    return False

class SpotOptimizationException(Exception):
    def __init__(self):
        Exception.__init__(self,("The optimization algorithm was unable to optimize a spot. " +
                    "This could be because there is no signal, because the ion weighting "+
                    "is all zeroes, the overlapDistance is too large in Distance mode, or "+
                    ", in Pixel Overlap mode, spots are overlapping so severely at the "+
                    "beginning of this routine that it could not find a new location no "+
                    "more than halfboxsize away that does /not/ overlap with another spot.\n"+
                    "Think of it as a spot being 'checkmate': There's nowhere it can go"))



class DraggablePoint(object):
    lock = None #only one can be animated at a time
    def __init__(self, point,annotation,all_annotations):
        self.point = point
        self.press = None
        self.background = None
        self.annotation=annotation
        self.all_annoations=all_annotations

    def connect(self):
        """connect to all the events we need"""
        self.cidpress = self.point.figure.canvas.mpl_connect('button_press_event', self.on_press)
        self.cidrelease = self.point.figure.canvas.mpl_connect('button_release_event', self.on_release)
        self.cidmotion = self.point.figure.canvas.mpl_connect('motion_notify_event', self.on_motion)

    def on_press(self,event):
        if event.inaxes != self.point.axes:
            return
        contains = self.point.contains(event)[0]
        if not contains: return
        self.press = self.point.center, event.xdata, event.ydata
        for a in self.all_annoations:
            a.set_visible(False)
        self.annotation.set_visible(True)


    def on_release(self, event):
        """on release we reset the press data"""
        self.press = None
        lock = None
        if DraggablePoint.lock is not self:
            return
        # turn off the rect animation property and reset the background
        self.point.set_animated(False)
        self.annotation.set_animated(False)
        self.background = None
        # redraw the full figure
        self.point.figure.canvas.draw()

    def on_motion(self, event):
        if self.press is None: return
        if event.inaxes != self.point.axes: return
        self.point.center, xpress, ypress = self.press
        dx = event.xdata - xpress
        dy = event.ydata - ypress
        self.point.center = (self.point.center[0]+dx, self.point.center[1]+dy)
        self.annotation.set_position(self.point.center)
        #self.point.set_facecolor('c')
        canvas = self.point.figure.canvas
        axes = self.point.axes

        # restore the background region
        canvas.restore_region(self.background)

        # redraw just the current rectangle
        axes.draw_artist(self.point)
#         axes.set_title(str(self.point.center))
        # blit just the redrawn area
        canvas.blit(axes.bbox)
        #self.point.figure.canvas.draw()

    def disconnect(self):
        """disconnect all the stored connection ids"""
        self.point.figure.canvas.mpl_disconnect(self.cidpress)
        self.point.figure.canvas.mpl_disconnect(self.cidrelease)
        self.point.figure.canvas.mpl_disconnect(self.cidmotion)


class DraggablePointForBarycentricInterpolation(object):
    # make an interactive plot, move the 4 vertices of the trapezoid around
    # as they are moved, redraw the interior points of our grid

    #based heavily on this example:
    # http://stackoverflow.com/questions/21654008/matplotlib-drag-overlapping-points-interactively
    lock = None #only one can be animated at a time
    def __init__(self, point,h1,ax, Nx, Ny,annotation,hexagonalOffset):
        self.point = point
        self.press = None
        self.background = None
        self.h1 = h1
        self.ax = ax
        self.Nx = Nx
        self.Ny = Ny
        self.annotation=annotation
        self.hexagonalOffset = hexagonalOffset

    def connect(self):
        """connect to all the events we need"""
        self.cidpress = self.point.figure.canvas.mpl_connect('button_press_event', self.on_press)
        self.cidrelease = self.point.figure.canvas.mpl_connect('button_release_event', self.on_release)
        self.cidmotion = self.point.figure.canvas.mpl_connect('motion_notify_event', self.on_motion)

    def on_press(self,event):
        if event.inaxes != self.point.axes: return
        if DraggablePointForBarycentricInterpolation.lock is not None: return
        contains, attrd = self.point.contains(event)
        if not contains: return
        self.press = (self.point.center), event.xdata, event.ydata
        DraggablePointForBarycentricInterpolation.lock = self

        # draw everything but the selected rectangle and store the pixel buffer
        canvas = self.point.figure.canvas
        axes = self.point.axes
        self.point.set_animated(True)
        canvas.draw()
        self.background = canvas.copy_from_bbox(self.point.axes.bbox)

        # now redraw just the rectangle
        axes.draw_artist(self.point)

        # and blit just the redrawn area
        canvas.blit(axes.bbox)


    def on_motion(self, event):
        if DraggablePointForBarycentricInterpolation.lock is not self:
            return
        if event.inaxes != self.point.axes: return
        self.point.center, xpress, ypress = self.press
        dx = event.xdata - xpress
        dy = event.ydata - ypress
        self.point.center = (self.point.center[0]+dx, self.point.center[1]+dy)
        self.annotation.set_position(self.point.center)

        canvas = self.point.figure.canvas
        axes = self.point.axes

        # restore the background region
        canvas.restore_region(self.background)

        # redraw just the current rectangle
        axes.draw_artist(self.point)
        # blit just the redrawn area
        canvas.blit(axes.bbox)

        p = []
        for d in self.ax.patches:
            p.append(d.center)
        p = np.asarray(p)

        xi,yi = barycentric_trapezoidial_interpolation(self.Nx,self.Ny,p,hexagonalOffset = self.hexagonalOffset)

        self.h1.set_xdata(xi)
        self.h1.set_ydata(yi)

        #self.point.figure.canvas.draw()

    def on_release(self, event):
        'on release we reset the press data'
        if DraggablePointForBarycentricInterpolation.lock is not self:
            return

        self.press = None
        DraggablePointForBarycentricInterpolation.lock = None

        # turn off the rect animation property and reset the background
        self.point.set_animated(False)
        self.background = None

        # redraw the full figure
        self.point.figure.canvas.draw()

    def disconnect(self):
        'disconnect all the stored connection ids'
        self.point.figure.canvas.mpl_disconnect(self.cidpress)
        self.point.figure.canvas.mpl_disconnect(self.cidrelease)
        self.point.figure.canvas.mpl_disconnect(self.cidmotion)


def barycentric_trapezoidial_interpolation(Nx,Ny,p,hexagonalOffset=0.5):
    '''
    define our function to calculate the position of points from Nx columns and Ny rows.
    The vertices are defined by p which is a size(4,2) array.
    each row of p are the coordinates or the vertices of our trapezoid
    the vertices have to be given in a specific order:
    [[1 1]
     [1 2]
     [2 1]
     [2 2]]
    an example plot using the barycentric interpolation to regrid data
    define number of rows and number of columns and the vertices, then make some plots

    Example:
    Nx = 20
    Ny = 15

    coords = [[0,0],[0,1],[1,0],[1,1]] #these are the [x,y] coords of your 4 draggable corners
    coords = np.asarray(coords)

    f, ax = plt.subplots(2, 2) # sharey=True, sharex=True)
    for i,a in enumerate(ax.flatten()):
        newCoords = coords[:]
        if i > 0:
            newCoords = newCoords + np.random.rand(4,2) / 5
        xi,yi = barycentric_trapezoidial_interpolation(Nx,Ny,newCoords)
        a.plot(xi,yi,'.',markersize=12)
    plt.show()
    '''
    x_basis = np.linspace(0,1,Nx)
    y_basis = np.linspace(0,1,Ny)

    px = [[p[0,0], p[2,0]],[p[1,0], p[3,0]]] #these are the [2,2] x-coordinates
    py = [[p[0,1], p[2,1]],[p[1,1], p[3,1]]] #these are the [2,2] y-coordinates
    fx = interpolate.interp2d([0,1], [0,1], px, kind='linear')
    xi = fx(x_basis[:],y_basis[:]).flatten()
    fy = interpolate.interp2d([0,1], [0,1], py, kind='linear')
    yi = fy(x_basis[:],y_basis[:]).flatten()
    d1 = (p[2,0] - p[0,0]) / Nx / 2.0
    d2 = (p[3,0] - p[1,0]) / Nx / 2.0
    offset = (d1 + d2) * hexagonalOffset
    #every other row will be shifted in diff(x) * hexagonalOffset
    for i in range(0,len(xi)-Nx,Nx*2):
        for j in range(Nx):
            xi[i+j+Nx] += offset
    return xi,yi

def alphaRowString(tuple):
    return "{}{:02d}".format(chr(ord('A')+tuple[0]-1),tuple[1])

def init_default_params(arrayed_analysis_default_username = '', openmsi_default_ions = [979.4,1079.35,1141.35,1241.25],
    arrayed_analysis_columns = 24, arrayed_analysis_rows = 16, arrayed_analysis_offset = 0,
    arrayed_analysis_radius = 2, arrayed_analysis_minScore = 0, arrayed_analysis_default_filename = 'bpb/20120913_nimzyme.h5'):
    '''
    Creates a pickle file containing default settings used throughout the workflow
    '''
    a = inspect.getargspec(init_default_params)
    kwargin = dict(zip(a.args,a.defaults))
    with open('ommat_parameters.pkl','wb') as fid:
        pickle.dump(kwargin,fid)
    return kwargin

def update_default_params(params):
    '''
    Saves the parameters file
    '''
    with open('ommat_parameters.pkl','wb') as fid:
        pickle.dump(params,fid)

def get_default_params():
    '''
    Reads parameters from the parameters file.  Creates a new parameters file if one does not exist.
    '''
    try:
        with open('ommat_parameters.pkl','rb') as fid:
            params = pickle.load(fid)
    except:
        print('initializing default parameters')
        params = init_default_params()
    return params
