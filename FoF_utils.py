import ctypes
import numpy as np
import time
import h5py
import copy
import os

## flag for debug statements
DEBUG=0

def splitFlattenedArray(flat_arr,masterListIndices):
    return np.split(flat_arr,masterListIndices[1:-1])

############### SNe Functions ############### 
class SupernovaCluster(ctypes.Structure):
    pass

SupernovaCluster._fields_ = [
                ("xs", ctypes.POINTER(ctypes.c_float)),
                ("ys", ctypes.POINTER(ctypes.c_float)),
                ("zs", ctypes.POINTER(ctypes.c_float)),
                ("ids",ctypes.POINTER(ctypes.c_float)),
                ("launchTimes", ctypes.POINTER(ctypes.c_float)),
                ("coolingTimes", ctypes.POINTER(ctypes.c_float)),
                ("linkingLengths", ctypes.POINTER(ctypes.c_float)),
                ("numNGB",ctypes.c_int),
                ("cluster_id",ctypes.c_int),
                ("NextCluster",ctypes.POINTER(SupernovaCluster))
            ]

def findSNeFoFClustering(xs,ys,zs,ids,launchTimes,coolingTimes,linkingLengths,**kwargs):
    NSNe = len(xs)
    return extractSNeLinkedListValues(
        *getSNeLinkedListHead(NSNe,xs,ys,zs,ids,launchTimes,coolingTimes,linkingLengths,**kwargs))

def getSNeLinkedListHead(
    NSNe,
    xs,ys,zs,ids,
    launchTimes,coolingTimes,linkingLengths,
    repo_subdir = "python",
):
    
    ## create a new c struct
    head = SupernovaCluster()    

    ## find that shared object library 
    exec_call = os.path.join(os.environ['HOME'], repo_subdir, "CFoF/fof_sne.so")
    c_obj = ctypes.CDLL(exec_call)

    h_out_cast=ctypes.c_int
    H_OUT=h_out_cast()

    ## copy the arrays because otherwise the original will get shuffled by the c routine
    ## need to cast to float as well!
    xs,ys,zs,ids = (
        copy.copy(xs).astype('f'),
        copy.copy(ys).astype('f'),
        copy.copy(zs).astype('f'),
        copy.copy(ids).astype('f')
    )
        
    launchTimes=copy.copy(launchTimes).astype('f')
    coolingTimes=copy.copy(coolingTimes).astype('f')
    linkingLengths=copy.copy(linkingLengths).astype('f')

    if DEBUG:
        xs=xs[:10]
        ys=ys[:10]
        zs=zs[:10]
        ids=ids[:10]
        launchTimes=launchTimes[:10]
        coolingTimes=coolingTimes[:10]
        linkingLengths=linkingLengths[:10]
        NSNe = 10

        print("ids",ids[:10],type(ids[0]))
        print("xs",xs[:10],type(xs[0]))
        print("cooling times",coolingTimes,type(coolingTimes[0]))
        print("launch times",launchTimes,type(launchTimes[0]))
        print("linking lengths",linkingLengths,type(linkingLengths))

    print("Executing c code")
    init_time=time.time()

    numClusters = c_obj.FoFSNeNGB(
        ctypes.c_int(NSNe),
        xs.ctypes.data_as(ctypes.POINTER(ctypes.c_float)),
        ys.ctypes.data_as(ctypes.POINTER(ctypes.c_float)),
        zs.ctypes.data_as(ctypes.POINTER(ctypes.c_float)),

        launchTimes.ctypes.data_as(ctypes.POINTER(ctypes.c_float)),
        coolingTimes.ctypes.data_as(ctypes.POINTER(ctypes.c_float)),
        linkingLengths.ctypes.data_as(ctypes.POINTER(ctypes.c_float)),

        ids.ctypes.data_as(ctypes.POINTER(ctypes.c_float)),

        ctypes.byref(head),
        ctypes.byref(H_OUT))

    print(numClusters,'groups found')
    print(time.time()-init_time,'s elapsed')
    ## skip the empty head node
    head = head.NextCluster.contents
    ## make sure to delete the copies made
    del xs,ys,zs,ids,launchTimes,coolingTimes,linkingLengths
    return numClusters,head


def extractSNeLinkedListValues(numClusters,head):    
    ## initialize arrays
    numNGBs=[]
    masterListIndices=[0]
    clusterIDs=[]
    keys = np.array(head._fields_)
    ## assumes that the final 3 in this list are numNGB,cluster_id,NextCluster (which they are, since I define _fields_ above)
    valss = [[] for i in range(len(keys)-3)]
    
    ## loop through links of the linked list and add their values to a single flattened array
    for i in range(numClusters):
        extractSNeClusterObjValues(head,keys,valss,numNGBs,masterListIndices,clusterIDs)
        ## iterate the linked list
        try:
            if i < (numClusters-1):
                head = head.NextCluster.contents
        except:
            print(i,numClusters)
            raise
            

    ## unpack the flattened arrays
    flat_xss,flat_yss,flat_zss,flat_idss,flat_ltss,flat_ctss,flat_llss=valss
         
    ##split the flattened arrays
    xss = splitFlattenedArray(flat_xss,masterListIndices)
    yss = splitFlattenedArray(flat_yss,masterListIndices)
    zss = splitFlattenedArray(flat_zss,masterListIndices)
    idss = splitFlattenedArray(flat_idss,masterListIndices)
    ltss = splitFlattenedArray(flat_ltss,masterListIndices)
    ctss = splitFlattenedArray(flat_ctss,masterListIndices)
    llss = splitFlattenedArray(flat_llss,masterListIndices)
    valss = [
        xss,yss,zss,
        idss,
        ltss,ctss,
        llss,
        np.array(numNGBs),np.array(clusterIDs),
        masterListIndices]
    return valss
         
def extractSNeClusterObjValues(head,keys,valss,numNGBs,masterListIndices,clusterIDs):
    for i,(key,val) in enumerate(keys):
        if key == 'numNGB':
            numNGBs+=[head.numNGB]
            masterListIndices+=[masterListIndices[-1]+head.numNGB]
        elif key == 'cluster_id':
            clusterIDs+=[head.cluster_id]
        elif key =='NextCluster':
            pass
        else:
            if DEBUG:
                print(key,'--',np.ctypeslib.as_array(getattr(head,key),shape=(head.numNGB,)))
            valss[i]=np.append(valss[i],[np.ctypeslib.as_array(getattr(head,key),shape=(head.numNGB,))])
            

def testSNe():
    Ntest = 10
    xs = ys = zs = np.ones(Ntest)
    ids = np.array(range(Ntest))
    launchTimes = np.ones(Ntest)
    coolingTimes = np.ones(Ntest)*2.0
    linkingLengths = np.array([.114]*Ntest)
    print("SNe test:",)
    print("-----------------------------------")
    print(findSNeFoFClustering(xs,ys,zs,ids,launchTimes,coolingTimes,linkingLengths))
    print("-----------------------------------")

############### GMC Functions ############### 
class GMCClump(ctypes.Structure):
    pass

GMCClump._fields_ = [
                ("xs", ctypes.POINTER(ctypes.c_float)),
                ("ys", ctypes.POINTER(ctypes.c_float)),
                ("zs", ctypes.POINTER(ctypes.c_float)),
                ("vxs", ctypes.POINTER(ctypes.c_float)),
                ("vys", ctypes.POINTER(ctypes.c_float)),
                ("vzs", ctypes.POINTER(ctypes.c_float)),
                ("masses", ctypes.POINTER(ctypes.c_float)),
                ("sfrs", ctypes.POINTER(ctypes.c_float)),
                ("nH", ctypes.POINTER(ctypes.c_float)),
                ("ids",ctypes.POINTER(ctypes.c_float)),
                ("numNGB",ctypes.c_int),
                ("cluster_id",ctypes.c_int),
                ("NextCluster",ctypes.POINTER(GMCClump))
            ]

def findGMCFoFClustering(
    linkingLength,
    xs,ys,zs,
    vxs,vys,vzs,
    masses,sfrs,nH,
    ids):
    NGMC = len(xs)
    return extractGMCLinkedListValues(
        linkingLength,
        *getGMCLinkedListHead(
            NGMC,
            linkingLength,
            xs,ys,zs,
            vxs,vys,vzs,
            masses,sfrs,nH,
            ids))

def getGMCLinkedListHead(
    NGMC,
    linkingLength,
    xs,ys,zs,
    vxs,vys,vzs,
    masses,sfrs,nH,
    ids):
    
    ## create a new c struct
    head = GMCClump()    

    ## find that shared object library 
    exec_call = os.path.join(os.environ['HOME'],"python/CFoF/fof_sne.so")
    c_obj = ctypes.CDLL(exec_call)

    h_out_cast=ctypes.c_int
    H_OUT=h_out_cast()

    ## copy the arrays because otherwise the original will get shuffled by the c routine
    ## need to cast to float as well!
    xs,ys,zs,vxs,vys,vzs,masses,sfrs,nH,ids = (
        copy.copy(xs).astype('f'),
        copy.copy(ys).astype('f'),
        copy.copy(zs).astype('f'),
        copy.copy(vxs).astype('f'),
        copy.copy(vys).astype('f'),
        copy.copy(vzs).astype('f'),
        copy.copy(masses).astype('f'),
        copy.copy(sfrs).astype('f'),
        copy.copy(nH).astype('f'),
        copy.copy(ids).astype('f')
    )
        
    if DEBUG:
        pass

    print("Executing c code")
    init_time=time.time()

    numClusters = c_obj.FoFGMCNGB(
        ctypes.c_int(NGMC),
        ctypes.c_float(linkingLength),
        xs.ctypes.data_as(ctypes.POINTER(ctypes.c_float)),
        ys.ctypes.data_as(ctypes.POINTER(ctypes.c_float)),
        zs.ctypes.data_as(ctypes.POINTER(ctypes.c_float)),
        vxs.ctypes.data_as(ctypes.POINTER(ctypes.c_float)),
        vys.ctypes.data_as(ctypes.POINTER(ctypes.c_float)),
        vzs.ctypes.data_as(ctypes.POINTER(ctypes.c_float)),
        masses.ctypes.data_as(ctypes.POINTER(ctypes.c_float)),
        sfrs.ctypes.data_as(ctypes.POINTER(ctypes.c_float)),
        nH.ctypes.data_as(ctypes.POINTER(ctypes.c_float)),
        ids.ctypes.data_as(ctypes.POINTER(ctypes.c_float)),

        ctypes.byref(head),
        ctypes.byref(H_OUT))

    print(numClusters,'groups found')
    print(time.time()-init_time,'s elapsed')
    ## skip the empty head node
    head = head.NextCluster.contents
    ## make sure to delete the copies made
    del xs,ys,zs,vxs,vys,vzs,masses,sfrs,nH,ids
    return numClusters,head


def extractGMCLinkedListValues(linkingLength,numClusters,head):    
    ## initialize arrays
    numNGBs=[]
    masterListIndices=[0]
    clusterIDs=[]
    keys = np.array(head._fields_)
    ## assumes that the final 3 in this list are numNGB,cluster_id,NextCluster (which they are, since I define _fields_ above)
    valss = [[] for i in range(len(keys)-3)]
    
    ## loop through links of the linked list and add their values to a single flattened array
    for i in range(numClusters):
        extractGMCClusterObjValues(head,keys,valss,numNGBs,masterListIndices,clusterIDs)
        ## iterate the linked list
        try:
            if i < (numClusters-1):
                head = head.NextCluster.contents
        except:
            print(i,numClusters)
            raise
            
    ## unflatten the flattened arrays
    unflat_valss = [linkingLength]
    for flat_vals in valss:
        unflat_valss+=[splitFlattenedArray(flat_vals,masterListIndices)]
         
    ##split the flattened arrays
    unflat_valss += [
        np.array(numNGBs),np.array(clusterIDs),
        masterListIndices]
    return unflat_valss
         
def extractGMCClusterObjValues(head,keys,valss,numNGBs,masterListIndices,clusterIDs):
    for i,(key,val) in enumerate(keys):
        if key == 'numNGB':
            numNGBs+=[head.numNGB]
            masterListIndices+=[masterListIndices[-1]+head.numNGB]
        elif key == 'cluster_id':
            clusterIDs+=[head.cluster_id]
        elif key =='NextCluster':
            pass
        else:
            valss[i]=np.append(valss[i],[np.ctypeslib.as_array(getattr(head,key),shape=(head.numNGB,))])

def testGMC():
    Ntest = 10
    xs = ys = zs = np.ones(Ntest)
    vxs = vys = vzs = np.ones(Ntest)
    masses = sfrs = nH = np.ones(Ntest)
    ids = np.array(range(Ntest))
    linkingLength = 1
    print("GMC test:",)
    print("-----------------------------------")
    print(findGMCFoFClustering(
        linkingLength,
        xs,ys,zs,
        vxs,vys,vzs,
        masses,sfrs,nH,
        ids))
    print("-----------------------------------")

def main():
    testSNe()
    testGMC()




if __name__ == '__main__':
    main()
