#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu Mar 29 18:20:38 2018

@author: Sebastijan Mrak <smrak@bu.edu>
"""

import h5py
from numpy import where, isin, nan, arange, ones, isnan, isfinite, array, mean, unique
from datetime import datetime 
from pyGnss import gnssUtils as gu
import os

import matplotlib.pyplot as plt
import cartopy.crs as ccrs
from cartomap import geogmap as gm

def getNeighbours(image,i,j):
    """
    Return an array of <=9 neighbour pixel of an image with a center at (i,j)
    """
    nbg = []
    for k in arange(i-1, i+2):
        for l in arange(j-1, j+2):
            try:
                nbg.append(image[k,l])
            except Exception as e:
                pass
    return array(nbg)

def fillPixels(im, N=1):
    """
    Fill in the dead pixels. If a dead pixel has a least 4 finite neighbour
    pixel, than replace the center pixel with a mean valuse of the neighbours
    """
    for n in range(N):
        for i in arange(0,im.shape[0]):
            for j in arange(0,im.shape[1]):
                # Check if th epixel is dead, i.e. empty
                if isnan(im[i,j]):
                    # Get its neighbours as a np array
                    nbg = getNeighbours(im,i,j)
                    # If there are at leas 4 neighbours, replace the value with a mean
                    if sum(isfinite(nbg)) >= 4:
                        ix = where(isfinite(nbg))[0]
                        avg = mean(nbg[ix])
                        im[i,j] = avg
    return im

def returnGlobalTEC(date='', datafolder='', timelim=[]):
    if isinstance(date,str) and date != '':
        try:
            yy = date[2:4]
            mm = date[5:7]
            dd = date[-2:]
        except:
            raise ('Date has to be given in a format YYYY-MM-DD')
            
    if datafolder == '' or datafolder is None:
        datafolder = 'C:\\Users\\smrak\\Google Drive\\BU\\Projects\\steve\\data\\gps\\'
    
    # Open the data
    try:
        if os.path.isdir(datafolder):
            fnstruct = 'gps'+yy+mm+dd+'g.002.hdf5'
            fn = datafolder + fnstruct
        elif os.path.isfile(datafolder):
            fn = datafolder
        else:
            raise('Something went wrong. datafolder format is not recognized')
            
        f = h5py.File(fn, 'r')
        obstimes = f['Data/Table Layout']['ut1_unix']
        xgrid = arange(-180,180)
        ygrid = arange(-90,90)
    except Exception as e:
        raise (e)
    
    # Time resolution
    if timelim is None or len(timelim) == 0:
        iterate = obstimes
    elif len(timelim) > 0 and isinstance(timelim[0],datetime):
        tlim = gu.datetime2posix(timelim)
        IDT = (obstimes>=tlim[0]) & (obstimes<=tlim[1])
        iterate = unique(obstimes[IDT])
    else:
        raise('timelim argument has to be a dateime.datetime object, with \
              with a length 2 (start,stop)')
        
    # Make an empty array to read in the data
    imstack = nan * ones((iterate.shape[0],xgrid.shape[0],ygrid.shape[0]))
    
    for i,t in enumerate(iterate):
        print ('Reading in image {}/{}'.format(i+1, iterate.shape[0]))
        im = nan * ones((xgrid.shape[0],ygrid.shape[0]))
        data_t = f['Data/Table Layout']['ut2_unix']
        idt = abs(data_t - t).argmin()
        idT = isin(data_t,data_t[idt])
        
        data_lon = f['Data/Table Layout']['glon'][idT]
        data_lat = f['Data/Table Layout']['gdlat'][idT]
        data_tec = f['Data/Table Layout']['tec'][idT]
        
        for k in range(data_tec.shape[0]):
            idx = where(xgrid == data_lon[k])
            idy = where(ygrid == data_lat[k])
            im[idx,idy] = data_tec[k]
        imstack[i,:,:] = im
    dt = array([datetime.utcfromtimestamp(t) for t in iterate])
    
    out = {'time':dt, 'xgrid': xgrid, 'ygrid': ygrid, 'tecim': imstack}
    return out

def readFromHDF(h5fn, tformat='datetime'):
    try:
        f = h5py.File(h5fn,'r')
        t = f['GPSTEC/time'].value
        if str(tformat) == 'datetime':
            t = array([datetime.utcfromtimestamp(ts) for ts in t])
        lon = f['GPSTEC/lon'].value
        lat = f['GPSTEC/lat'].value
        images = f['GPSTEC/im'].value
        # Close file
        f.close()
        
        return {'time': t, 'xgrid': lon, 'ygrid': lat, 'tecim': images}
    except Exception as e:
        if 'f' in locals():
            f.close()
        raise(e)
    

def save2HDF(t,lon,lat,images,h5fn):
    if isinstance(t[0],datetime):
        t = gu.datetime2posix(t)
    try:
        f = h5py.File(h5fn,'w')
        d = f.create_group('GPSTEC')
        d.attrs[u'converted'] = datetime.now().strftime('%Y-%m-%d %H:%M')
        h5time = d.create_dataset('time', data=t)
        h5time.attrs[u'time format'] = 'time format in POSIX time'
        d.create_dataset('lon', data=lon)
        d.create_dataset('lat', data=lat)
        h5img = d.create_dataset('im', data=images, compression='gzip', compression_opts=9)
        h5img.chunks
        # Close file
        f.close()
    except Exception as e:
        if 'f' in locals():
            f.close()
        raise(e)

def plotTECmap(x,y,z,title='',cmap='viridis',clim=[0,15],
               figsize=(10,6),latlim=[0,70],lonlim=[-150,-60],
               projection='stereo',background_color='gray',
               grid_color='w',border_color='#006600',
               meridians = [-180,-150,-120,-90,-60,-40,-20],
               parallels = [0,20,30,40,50,60,70,80],
               colorbar=True,cbar_label='TEC [TECu]',
               tight=False, savefn=False,DPI=100,
               nightshade=False, ns_dt=None, ns_alpha=0.1):
    # Make map
    fig = gm.plotCartoMap(figsize=figsize,projection=projection,latlim=latlim,lonlim=lonlim,
                      parallels=parallels,meridians=meridians,title=title,
                      background_color=background_color,grid_color=grid_color,
                      grid_linewidth=1,border_color=border_color,figure=True,
                      nightshade=nightshade, ns_dt=ns_dt, ns_alpha=ns_alpha)
    
    plt.pcolormesh(x,y,z.T, cmap=cmap, transform=ccrs.PlateCarree())
    plt.clim(clim)
    if colorbar:
        cbar = plt.colorbar()
        cbar.set_label(cbar_label)
    if tight:
        plt.tight_layout()
    # Save
    if savefn is not None and isinstance(savefn,str):
        try:
            plt.savefig(savefn,dpi=DPI)
            plt.close(fig)
        except Exception as e:
            raise(e)
    else:
        plt.show()
    return fig