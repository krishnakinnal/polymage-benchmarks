import ctypes
import numpy as np
import time
from cv2 import *
import sys
from numba import jit
from common import clock, draw_str, StatValue, image_clamp


"""Function to perform OpenCV Unsharp Masking"""
@jit("uint8[::](uint8[::],float64,float64)",cache=True,nogil=True)
def uscv(image,weight,threshold):
    weight=0.5
    mask=image
    blurred=GaussianBlur(image,(9,9),10.0)
    sharp=addWeighted(image,(1+weight),blurred,(-weight),0)
    return sharp

# load polymage shared libraries
libharris = ctypes.cdll.LoadLibrary("./harris.so")
libharris_naive = ctypes.cdll.LoadLibrary("./harris_naive.so")
libunsharp = ctypes.cdll.LoadLibrary("./unsharp.so")
libunsharp_naive = ctypes.cdll.LoadLibrary("./unsharp_naive.so")
libbilateral = ctypes.cdll.LoadLibrary("./bilateral.so")
libbilateral_naive = ctypes.cdll.LoadLibrary("./bilateral_naive.so")
liblaplacian = ctypes.cdll.LoadLibrary("./laplacian.so")
liblaplacian_naive = ctypes.cdll.LoadLibrary("./laplacian_naive.so")

harris = libharris.pipeline_harris
harris_naive = libharris_naive.pipeline_harris_naive

unsharp = libunsharp.pipeline_mask
unsharp_naive = libunsharp_naive.pipeline_mask_naive

bilateral = libbilateral.pipeline_bilateral
bilateral_naive = libbilateral_naive.pipeline_bilateral_naive

laplacian = liblaplacian.pipeline_laplacian
laplacian_naive = liblaplacian_naive.pipeline_laplacian_naive

cap = VideoCapture(sys.argv[1])

frames = 0
startTime = time.clock()

cv_mode = False
naive_mode = False

harris_mode = False
unsharp_mode = False
bilateral_mode = False
laplacian_mode = False

thresh = 0.001
weight = 3

levels = 4
alpha = 1.0/(levels-1)
beta = 1.0

"""Frame Delay Accumulators for each mode"""
sun=0.0
su=0.0
sln=0.0
sl=0.0
sbn=0.0
sb=0.0
shc=0.0
skuscv=0.0
shn=0.0
sho=0.0

"""Frame Count for each mode"""
fun=0
fu=0
fln=0
fl=0
fbn=0
fb=0
fhc=0
fkuscv=0
fho=0
fhn=0

libharris_naive.pool_init()
libharris.pool_init()

libunsharp_naive.pool_init()
libunsharp.pool_init()

liblaplacian_naive.pool_init()
liblaplacian.pool_init()

libbilateral_naive.pool_init()
libbilateral.pool_init()

namedWindow("Video",WINDOW_NORMAL)

while(cap.isOpened()):
    frames += 1
    ret, frame = cap.read()
    frameStart = clock()
    rows = frame.shape[0]
    cols = frame.shape[1]
    if harris_mode:
        if cv_mode:
            gray = cvtColor(frame, COLOR_BGR2GRAY)
            gray = np.float32(gray) / 4.0
            res = cornerHarris(gray, 3, 3, 0.04)
        else:
            res = np.empty((rows, cols), np.float32)
            if naive_mode:
                harris_naive(ctypes.c_int(cols-2), \
                             ctypes.c_int(rows-2), \
                             ctypes.c_void_p(frame.ctypes.data), \
                             ctypes.c_void_p(res.ctypes.data))
            else:
                harris(ctypes.c_int(cols-2), \
                       ctypes.c_int(rows-2), \
                       ctypes.c_void_p(frame.ctypes.data), \
                       ctypes.c_void_p(res.ctypes.data))

    elif unsharp_mode:
        if cv_mode:
            res=uscv(frame,weight,thresh)
        else:
            res = np.empty((rows-4, cols-4, 3), np.float32)
            if naive_mode:
                unsharp_naive(ctypes.c_int(cols - 4), \
                          ctypes.c_int(rows - 4), \
                          ctypes.c_float(thresh), \
                          ctypes.c_float(weight), \
                          ctypes.c_void_p(frame.ctypes.data), \
                          ctypes.c_void_p(res.ctypes.data))
            else:
                unsharp(ctypes.c_int(cols-4), \
                    ctypes.c_int(rows-4), \
                    ctypes.c_float(thresh), \
                    ctypes.c_float(weight), \
                    ctypes.c_void_p(frame.ctypes.data), \
                    ctypes.c_void_p(res.ctypes.data))

    elif laplacian_mode:
        total_pad = 92
        # result array
        res = np.empty((rows, cols, 3), np.uint8)

        if naive_mode:
            laplacian_naive(ctypes.c_int(cols+total_pad), \
                            ctypes.c_int(rows+total_pad), \
                            ctypes.c_float(alpha), \
                            ctypes.c_float(beta), \
                            ctypes.c_void_p(frame.ctypes.data), \
                            ctypes.c_void_p(res.ctypes.data))
        else:
            laplacian(ctypes.c_int(cols+total_pad), \
                      ctypes.c_int(rows+total_pad), \
                      ctypes.c_float(alpha), \
                      ctypes.c_float(beta), \
                      ctypes.c_void_p(frame.ctypes.data), \
                      ctypes.c_void_p(res.ctypes.data))

    elif bilateral_mode:
        res = np.empty((rows, cols), np.float32)
        if naive_mode:
            bilateral_naive(ctypes.c_int(cols+56), \
                            ctypes.c_int(rows+56), \
                            ctypes.c_void_p(frame.ctypes.data), \
                            ctypes.c_void_p(res.ctypes.data))
        else:
            bilateral(ctypes.c_int(cols+56), \
                      ctypes.c_int(rows+56), \
                      ctypes.c_void_p(frame.ctypes.data), \
                      ctypes.c_void_p(res.ctypes.data))


    else:
        res = frame

    frameEnd = clock()
    value=frameEnd*1000-frameStart*1000

    """Conditions to sum the values of frame delay accumulators and frame counters deoending on the mode"""
    if harris_mode:
        if cv_mode:
            shc+=value
            fhc+=1
        elif naive_mode:
            shn+=value
            fhn+=1
        else:
            sho+=value
            fho+=1
    elif unsharp_mode:
        if cv_mode:
            fkuscv+=1
            skuscv+=value
        elif naive_mode:
            sun+=value
            fun+=1
        else:
            su+=value
            fu+=1

    elif laplacian_mode:
        if cv_mode:
            sln+=value
            fln+=1
        else:
            sl+=value
            fl+=1

    elif bilateral_mode:
        if cv_mode:
            sbn+=value
            fbn+=1
        else:
            sb+=value
            fb+=1

    rectangle(res, (0, 0), (750, 150), (255, 255, 255), thickness=cv.CV_FILLED)
    draw_str(res, (40, 40),      "frame interval :  %.1f ms" % value)
    if cv_mode and harris_mode:
        draw_str(res, (40, 80),  "Pipeline        :  " + str("OpenCV"))
    elif cv_mode and unsharp_mode:
		draw_str(res, (40, 80),  "Pipeline        :  " + str("OpenCV"))
    elif bilateral_mode or harris_mode or unsharp_mode or laplacian_mode:
        if naive_mode:
            draw_str(res, (40, 80),  "Pipeline        :  " + str("PolyMage (Naive)"))
        else:
            draw_str(res, (40, 80),  "Pipeline        :  " + str("PolyMage (Opt)"))
    else:
        draw_str(res, (40, 80),  "Pipeline        :  ")

    if harris_mode:
        draw_str(res, (40, 120), "Benchmark    :  " + str("Harris Corner"))
    elif bilateral_mode:
        draw_str(res, (40, 120), "Benchmark    :  " + str("Bilateral Grid"))
    elif unsharp_mode:
        draw_str(res, (40, 120), "Benchmark    :  " + str("Unsharp Mask"))
    elif laplacian_mode:
        draw_str(res, (40, 120), "Benchmark    :  " + str("Local Laplacian"))
    else:
        draw_str(res, (40, 120), "Benchmark    :  ")

    imshow('Video', res)

    ch = 0xFF & waitKey(1)
    if ch == ord('q'):
        break
    if ch == ord(' '):
        cv_mode = not cv_mode
    if ch == ord('n'):
        naive_mode = not naive_mode
    if ch == ord('h'):
        harris_mode = not harris_mode
        bilateral_mode = False
        unsharp_mode = False
        laplacian_mode = False
    if ch == ord('u'):
        unsharp_mode = not unsharp_mode
        bilateral_mode = False
        harris_mode = False
        laplacian_mode = False
    if ch == ord('l'):
        laplacian_mode = not laplacian_mode
        unsharp_mode = False
        bilateral_mode = False
        harris_mode = False
    if ch == ord('b'):
        bilateral_mode = not bilateral_mode
        harris_mode = False
        unsharp_mode = False
        laplacian_mode = False


libharris_naive.pool_destroy()
libharris.pool_destroy()

libunsharp_naive.pool_destroy()
libunsharp.pool_destroy()

liblaplacian_naive.pool_destroy()
liblaplacian.pool_destroy()

libbilateral_naive.pool_destroy()
libbilateral.pool_destroy()

cap.release()
destroyAllWindows()



"""Printing the values of Average frame delay for each mode"""

if fhc!=0:
    print "Average frame delay for Harris (OpenCV) is - ",shc/fhc, "ms"
if fho!=0:
	print "Average frame delay for Harris (Opt) is - ",sho/fho, "ms"
if fhn!=0:
	print "Average frame delay for Harris (Naive) is - ",shn/fhn, "ms"
if fun!=0:
    print "Average frame delay for Unsharp Mask (Naive) is - ",sun/fun, "ms"
if fu!=0:
    print "Average frame delay for Unsharp Mask (Opt) is - ",su/fu, "ms"
if fbn!=0:
    print "Average frame delay for Bilateral Grid (Naive) is - ",sbn/fbn, "ms"
if fb!=0:
    print "Average frame delay for Bilateral Grid (Opt) is - ",sb/fb, "ms"
if fln!=0:
    print "Average frame delay for Local Laplacian (Naive) is - ",sln/fln, "ms"
if fl!=0:
    print "Average frame delay for Local Laplacian (Opt) is - ",sl/fl, "ms"
if fkuscv!=0:
    print "Average frame delay for Unsharp Mask (Python OpenCV) is - ",skuscv/fkuscv, "ms"
