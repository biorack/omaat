# from __future__ import print_function

import omaat_lib as omaat

def test_print():
	print('print is working')

def test_simplest_test():
	pass

def test_get_and_reduce_ion_images_peakarea():
	"""
	Tests the reduction strategies on a public image from the openmsi web service.
	"""
	openMSIsession=omaat.OpenMSIsession()
	openMSIsession.filename = 'bpb/20120913_nimzyme.h5'
	myIons = [800.0, 850.0, 950.0]
	img=openMSIsession.getArrayedImage(myIons,0.3,massRangeReductionStrategy=omaat.PeakArea())
	assert img.baseImage.size == 16371

def test_get_and_reduce_ion_images_peakheight():
	"""
	Tests the reduction strategies on a public image from the openmsi web service.
	"""
	openMSIsession=omaat.OpenMSIsession()
	openMSIsession.filename = 'bpb/20120913_nimzyme.h5'
	myIons = [800.0, 850.0, 950.0]
	img=openMSIsession.getArrayedImage(myIons,0.3,massRangeReductionStrategy=omaat.PeakHeight())
	assert img.baseImage.size == 16371

def test_get_and_reduce_ion_images_areanearpeak():
	"""
	Tests the reduction strategies on a public image from the openmsi web service.
	"""
	openMSIsession=omaat.OpenMSIsession()
	openMSIsession.filename = 'bpb/20120913_nimzyme.h5'
	myIons = [800.0, 850.0, 950.0]
	img=openMSIsession.getArrayedImage(myIons,0.3,massRangeReductionStrategy=omaat.AreaNearPeak())
	assert img.baseImage.size == 16371



# def test_fileselector():
#     if "openMSIsession" not in locals():
#         openMSIsession=omaat.OpenMSIsession()
#         openMSIsession.imageLoader_with_dialogs() #once loaded the image will be stored in the "img" variable