import numpy as np
from scipy import interpolate
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import getpass
import json, requests

def authenticateUser(client,username):
    password = getpass.getpass()
    authURL = 'https://openmsi.nersc.gov/openmsi/client/login/'
    # Retrieve the CSRF token first
    client.get(authURL)  # sets cookie
    csrftoken = client.cookies['csrftoken']
    login_data = dict(username=username, password=password, csrfmiddlewaretoken=csrftoken, next='/')
    r = client.post(authURL, data=login_data, headers=dict(Referer=authURL))
    return client
    
def getFilelist(client):
    payload = {'format':'JSON','mtype':'filelistView'}
    url = 'https://openmsi.nersc.gov/openmsi/qmetadata'
    r = client.get(url,params=payload)
    fileList = json.loads(r.content)
    return fileList.keys()

def getMZ(client,filename,expIndex,dataIndex):
    payload = {'file':filename,
          'expIndex':expIndex,'dataIndex':dataIndex,'qspectrum_viewerOption':'0',
          'qslice_viewerOption':'0',
          'col':0,'row':0,
          'findPeak':'0','format':'JSON'}
    url = 'https://openmsi.nersc.gov/openmsi/qmz'
    r = client.get(url,params=payload)
    data = json.loads(r.content)
    return np.asarray(data[u'values_spectra'])


def fineTunePosition(bkImage,xRough,yRough,markerRadius):
    fig = plt.figure()
    fig.set_facecolor('white')
    ax = fig.add_subplot(111)
    plt.imshow(bkImage,cmap='gray')
#     ax.set_xlim(np.min(xRough)-1,np.max(xRough)+1)
#     ax.set_ylim(np.min(yRough)-1,np.max(yRough)+1)
    # print max(yRough)
    # print np.max(yRough)
    # ax.set_xlim(min(xRough)-10,max(xRough)+10)
    # ax.set_ylim(min(yRough)+10,max(yRough)+10)
    ax.set_aspect('equal')
    # circles = [patches.Circle((0.32, 0.3), 0.03, fc='r', alpha=0.5),
    #                patches.Circle((0.3,0.3), 0.03, fc='g', alpha=0.5)]


    drs = []
    circles = []
    L = len(xRough)
    for i in range(L):
        circles.append(patches.Circle((xRough[i],yRough[i]), markerRadius, fc='b', alpha=0.5, ))

    for circ in circles:
        ax.add_patch(circ)
        dr = DraggablePoint(circ)
        dr.connect()
        drs.append(dr)

    plt.show()
    xFine = []
    yFine = []
    for c in circles:
        xFine.append(c.center[0])
        yFine.append(c.center[1])
    return xFine,yFine

class DraggablePoint:
    lock = None #only one can be animated at a time
    def __init__(self, point):
        self.point = point
        self.press = None
        self.background = None

    def connect(self):
        'connect to all the events we need'
        self.cidpress = self.point.figure.canvas.mpl_connect('button_press_event', self.on_press)
        self.cidrelease = self.point.figure.canvas.mpl_connect('button_release_event', self.on_release)
        self.cidmotion = self.point.figure.canvas.mpl_connect('motion_notify_event', self.on_motion)

    def on_press(self,event):
        if event.inaxes != self.point.axes:
            return
        contains = self.point.contains(event)[0]
        if not contains: return
        self.press = self.point.center, event.xdata, event.ydata


    def on_release(self, event):
        'on release we reset the press data'
        self.press = None
        lock = None
        if DraggablePoint.lock is not self:
            return
        # turn off the rect animation property and reset the background
        self.point.set_animated(False)
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
        self.point.set_facecolor('r')
        self.point.figure.canvas.draw()

    def disconnect(self):
        'disconnect all the stored connection ids'
        self.point.figure.canvas.mpl_disconnect(self.cidpress)
        self.point.figure.canvas.mpl_disconnect(self.cidrelease)
        self.point.figure.canvas.mpl_disconnect(self.cidmotion)



def roughPosition(bkImage,Nx,Ny,dragRadius,pointMarkerSize):
    fig = plt.figure()
    fig.set_facecolor('white')
    ax = fig.add_subplot(111)
    plt.imshow(bkImage,cmap='gray')

#     ax.set_xlim(2,7)
#     ax.set_ylim(0,3)
    ax.set_aspect('equal')
    xPos = [0,bkImage.shape[1]]
    xPos = [0,bkImage.shape[0]]
    circles = []
    circles.append(patches.Circle((0,0), dragRadius, fc='r', alpha=0.5, ))
    circles.append(patches.Circle((0,bkImage.shape[0]), dragRadius, fc='r', alpha=0.5, ))
    circles.append(patches.Circle((bkImage.shape[1],0), dragRadius, fc='r', alpha=0.5, ))
    circles.append(patches.Circle((bkImage.shape[1],bkImage.shape[0]), dragRadius, fc='r', alpha=0.5, ))
    
#     for i in range(2):
#         for j in range(2):
#             circles.append(patches.Circle((3*(i+1),j+1), 0.14, fc='r', alpha=0.5, ))


    p = []
    for d in circles:
        p.append(d.center)
    p = np.asarray(p)

    xi,yi = barycentric_trapezoidial_interpolation(Nx,Ny,p)

    h1, = ax.plot(xi,yi,'.',markersize=pointMarkerSize)

    drs = []
    for circ in circles:
        ax.add_patch(circ)
        dr = DraggablePointForBarycentricInterpolation(circ,h1,ax, Nx, Ny)
        dr.connect()
        drs.append(dr)

    plt.show()
    return h1.get_xdata(), h1.get_ydata()

class DraggablePointForBarycentricInterpolation:
    # make an interactive plot, move the 4 vertices of the trapezoid around
    # as they are moved, redraw the interior points of our grid
    
    #based heavily on this example:
    # http://stackoverflow.com/questions/21654008/matplotlib-drag-overlapping-points-interactively
    lock = None #only one can be animated at a time
    def __init__(self, point,h1,ax, Nx, Ny):
        self.point = point
        self.press = None
        self.background = None
        self.h1 = h1
        self.ax = ax
        self.Nx = Nx
        self.Ny = Ny
        
    def connect(self):
        'connect to all the events we need'
        self.cidpress = self.point.figure.canvas.mpl_connect('button_press_event', self.on_press)
        self.cidrelease = self.point.figure.canvas.mpl_connect('button_release_event', self.on_release)
        self.cidmotion = self.point.figure.canvas.mpl_connect('motion_notify_event', self.on_motion)

    def on_press(self,event):
        if event.inaxes != self.point.axes:
            return
        contains = self.point.contains(event)[0]
        if not contains: return
        self.press = self.point.center, event.xdata, event.ydata

    def on_release(self, event):
        'on release we reset the press data'
        self.press = None
        lock = None
        if DraggablePointForBarycentricInterpolation.lock is not self:
            return
        # turn off the rect animation property and reset the background
        self.point.set_animated(False)
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
#         print self.ax.patches[0]
        p = []
        for d in self.ax.patches:
            p.append(d.center)
        p = np.asarray(p)

        xi,yi = barycentric_trapezoidial_interpolation(self.Nx,self.Ny,p)
  
        self.h1.set_xdata(xi)
        self.h1.set_ydata(yi)

        self.point.figure.canvas.draw()

    def disconnect(self):
        'disconnect all the stored connection ids'
        self.point.figure.canvas.mpl_disconnect(self.cidpress)
        self.point.figure.canvas.mpl_disconnect(self.cidrelease)
        self.point.figure.canvas.mpl_disconnect(self.cidmotion)


def barycentric_trapezoidial_interpolation(Nx,Ny,p):
	# define our function to calculate the position of points from Nx columns and Ny rows.  
	# The vertices are defined by p which is a size(4,2) array.
	# each row of p are the coordinates or the vertices of our trapezoid
	# the vertices have to be given in a specific order:
	# [[1 1]
	#  [1 2]
	#  [2 1]
	#  [2 2]]
	# an example plot using the barycentric interpolation to regrid data
# define number of rows and number of columns and the vertices, then make some plots

	# Example:
	# Nx = 20
	# Ny = 15

	# coords = [[0,0],[0,1],[1,0],[1,1]] #these are the [x,y] coords of your 4 draggable corners
	# coords = np.asarray(coords)

	# f, ax = plt.subplots(2, 2) # sharey=True, sharex=True)
	# for i,a in enumerate(ax.flatten()):
	#     newCoords = coords[:]
	#     if i > 0:
	#         newCoords = newCoords + np.random.rand(4,2) / 5        
	#     xi,yi = openmsi.barycentric_trapezoidial_interpolation(Nx,Ny,newCoords)
	#     a.plot(xi,yi,'.',markersize=12)
	# plt.show()

    x_basis = np.linspace(0,1,Nx)
    y_basis = np.linspace(0,1,Ny)
    px = [[p[0,0], p[2,0]],[p[1,0], p[3,0]]] #these are the [2,2] x-coordinates
    py = [[p[0,1], p[2,1]],[p[1,1], p[3,1]]] #these are the [2,2] x-coordinates
    fx = interpolate.interp2d([1,0], [1,0], px, kind='linear')
    xi = fx(x_basis[:],y_basis[:]).flatten()
    fy = interpolate.interp2d([1,0], [1,0], py, kind='linear')
    yi = fy(x_basis[:],y_basis[:]).flatten()
    return xi,yi

