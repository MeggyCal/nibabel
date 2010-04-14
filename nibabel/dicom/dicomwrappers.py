''' Classes to wrap DICOM objects and files

The wrappers encapsulate the capcbilities of the different DICOM
formats.

They also allow dictionary-like access to named fiields.

For calculated attributes, we return None where needed data is missing.
It seemed strange to raise an error during attribute processing, other
than an AttributeError - breaking the 'properties manifesto'.   So, any
procesing that needs to raise an error, should be in a method, rather
than in a property, or property-like thing. 
'''

import numpy as np

from . import csareader as csar
from .dwiparams import B2q
from ..core.geometry import nearest_pos_semi_def
from .utils import allopen
from ..core.onetime import setattr_on_read as one_time


class WrapperError(Exception):
    pass


def wrapper_from_file(file_like):
    import dicom
    fobj = allopen(file_like)
    dcm_data = dicom.read_file(fobj)
    return make_wrapper(dcm_data)


def make_wrapper(dcm_data):
    csa = csar.get_csa_header(dcm_data)
    if csa is None:
        return Wrapper(dcm_data)
    if not csar.is_mosaic(csa):
        return SiemensWrapper(dcm_data, csa)
    return MosaicWrapper(dcm_data, csa)


class Wrapper(object):
    ''' Class to wrap general DICOM files

    Methods:

    * get_affine()
    * get_data()
    * get_pixel_array()
    * __getitem__ : return attributes from `dcm_data` 
    * get() - as usual given __getitem__ above

    Attributes (or rather, things that at least look like attributes):

    * dcm_data : object
    * image_shape : tuple
    * image_orient_patient : (3,2) array
    * slice_normal : (3,) array
    * rotation_matrix : (3,3) array
    * voxel_sizes : tuple length 3
    * image_position : sequence length 3
    * slice_indicator : float
    '''
    is_mosaic = False
    b_matrix = None
    q_vector = None
    ice_dims = None
    
    def __init__(self, dcm_data=None):
        ''' Initialize wrapper

        Parameters
        ----------
        dcm_data : None or object, optional
           object should allow attribute access.  Usually this will be
           a ``dicom.dataset.Dataset`` object resulting from reading a
           DICOM file.   If None, we just make an empty dict. 
        '''
        if dcm_data is None:
            dcm_data = {}
        self.dcm_data = dcm_data

    @one_time
    def image_shape(self):
        shape = (self.get('Rows'), self.get('Columns'))
        if None in shape:
            return None
        return shape
    
    @one_time
    def image_orient_patient(self):
        iop = self.get('ImageOrientationPatient')
        if iop is None:
            return None
        return np.array(iop).reshape(2,3).T

    @one_time
    def slice_normal(self):
        iop = self.image_orient_patient
        if iop is None:
            return None
        return np.cross(*iop.T[:])

    @one_time
    def rotation_matrix(self):
        iop = self.image_orient_patient
        s_norm = self.slice_normal
        if None in (iop, s_norm):
            return None
        R = np.eye(3)
        R[:,:2] = iop
        R[:,2] = s_norm
        # check this is in fact a rotation matrix
        assert np.allclose(np.eye(3),
                           np.dot(R, R.T),
                           atol=1e-6)
        return R

    @one_time
    def voxel_sizes(self):
        pix_space = self.get('PixelSpacing')
        if pix_space is None:
            return None
        zs =  self.get('SpacingBetweenSlices')
        if zs is None:
            zs = 1
        return tuple(pix_space + [zs])

    @one_time
    def image_position(self):
        ''' Return position of first voxel in data block

        Parameters
        ----------
        None

        Returns
        -------
        img_pos : (3,) array
           position in mm of voxel (0,0) in image array
        '''
        return self.get('ImagePositionPatient')

    @one_time
    def slice_indicator(self):
        ''' A number that is higher for higher slices in Z

        Comparing this number between two adjacent slices should give a
        difference equal to the voxel size in Z. 
        
        See doc/theory/dicom_orientation for description
        '''
        ipp = self.image_position
        s_norm = self.slice_normal
        if None in (ipp, s_norm):
            return None
        return np.inner(ipp, s_norm)
                
    def __getitem__(self, key):
        ''' Return values from DICOM object'''
        try:
            return getattr(self.dcm_data, key)
        except AttributeError:
            raise KeyError('%s not defined in dcm_data' % key)

    def get(self, key, default=None):
        return getattr(self.dcm_data, key, default)

    def get_affine(self):
        ''' Return mapping between voxel and DICOM coordinate system
        
        Parameters
        ----------
        None

        Returns
        -------
        aff : (4,4) affine
           Affine giving transformation between voxels in data array and
           the DICOM patient coordinate system.
        '''
        orient = self.rotation_matrix
        vox = self.voxel_sizes
        ipp = self.image_position
        if None in (orient, vox, ipp):
            raise WrapperError('Not enough information for affine')
        aff = np.eye(4)
        aff[:3,:3] = orient * np.array(vox)
        aff[:3,3] = ipp
        return aff

    def get_pixel_array(self):
        ''' Return unscaled pixel array from DICOM '''
        try:
            return self['pixel_array']
        except KeyError:
            raise WrapperError('Cannot find data in DICOM')
    
    def get_data(self):
        ''' Get scaled image data from DICOMs

        Returns
        -------
        data : array
           array with data as scaled from any scaling in the DICOM
           fields. 
        '''
        return self._scale_data(self.get_pixel_array())

    def maybe_same_volume_as(self, other):
        ''' First pass at clustering into volumes check

        Parameters
        ----------
        other : object
           wrapper object

        Returns
        -------
        tf : bool
           True if `other` might be in the same volume as `self`, False
           otherwise. 
        '''
        def _get_matchers(hdr):
            return (
                hdr.get('SeriesNumber'),
                hdr.image_shape,
                hdr.get('ImageType'),
                hdr.get('SequenceName'),
                hdr.get('SeriesInstanceID'),
                hdr.get('EchoNumbers'))
        if not _get_matchers(self) == _get_matchers(other):
            return False
        iop1, iop2 = self.image_orient_patient, other.image_orient_patient
        if not none_matcher(iop1, iop1,
                            lambda x, y: np.allclose(iop1, iop2)):
            return False
        ice1, ice2 = self.ice_dims, other.ice_dims
        def _ice_matcher(ice1, ice2):
            inds = np.array([1,1,1,1,1,1,0,0,1])
            ice1 = np.array(ice1)
            ice2 = np.array(ice2)
            return np.all(ice1[inds] == ice2[inds])
        if not none_matcher(ice1, ice2, _ice_matcher):
            return False
        # instance numbers should _not_ match
        in1, in2 = self.get('InstanceNumber'), other.get('InstanceNumber')
        if none_matcher(in1, in2):
            return False
        # nor should z slice indicators
        if self.slice_indicator == other.slice_indicator:
            return False
        return True

    def _scale_data(self, data):
        scale = self.get('RescaleSlope', 1)
        offset = self.get('RescaleIntercept', 0)
        # a little optimization.  If we are applying either the scale or
        # the offset, we need to allow upcasting to float.
        if scale != 1:
            if offset == 0:
                return data * scale
            return data * scale + offset
        if offset != 0:
            return data + offset
        return data


class SiemensWrapper(Wrapper):
    ''' Wrapper for Siemens format DICOMs '''
    def __init__(self, dcm_data=None, csa_header=None):
        ''' Initialize Siemens wrapper

        The Siemens-specific information is in the `csa_header`, either
        passed in here, or read from the input `dcm_data`. 

        Parameters
        ----------
        dcm_data : None or object, optional
           object should allow attribute access.  If `csa_header` is
           None, it should also be possible to extract a CSA header from
           `dcm_data`. Usually this will be a ``dicom.dataset.Dataset``
           object resulting from reading a DICOM file.  If None, we just
           make an empty dict.
        csa_header : None or mapping, optional
           mapping giving values for Siemens CSA image sub-header.  
        '''
        if dcm_data is None:
            dcm_data = {}
        self.dcm_data = dcm_data
        if csa_header is None:
            csa_header = csar.get_csa_header(dcm_data)
            if csa_header is None:
                csa_header = {}
        self.csa_header = csa_header

    @one_time
    def slice_normal(self):
        slice_normal = csar.get_slice_normal(self.csa_header)
        if not slice_normal is None:
            return slice_normal
        iop = self.image_orient_patient
        if iop is None:
            return None
        return np.cross(*iop.T[:])

    @one_time
    def b_matrix(self):
        ''' Get DWI B matrix referring to voxel space

        Parameters
        ----------
        None
        
        Returns
        -------
        B : (3,3) array or None
           B matrix in *voxel* orientation space.  Returns None if this is
           not a Siemens header with the required information.  We return
           None if this is a b0 acquisition
        '''
        hdr = self.csa_header
        # read B matrix as recorded in CSA header.  This matrix refers to
        # the space of the DICOM patient coordinate space.
        B = csar.get_b_matrix(hdr)
        if B is None: # may be not diffusion or B0 image
            bval_requested = csar.get_b_value(hdr)
            if bval_requested is None:
                return None
            if bval_requested != 0:
                raise csar.CSAError('No B matrix and b value != 0')
            return np.zeros((3,3))
        # rotation from voxels to DICOM PCS, inverted to give the rotation
        # from DPCS to voxels.  Because this is an orthonormal matrix, its
        # transpose is its inverse
        R = self.rotation_matrix.T
        # because B results from V dot V.T, the rotation B is given by R dot
        # V dot V.T dot R.T == R dot B dot R.T
        B_vox = np.dot(R, np.dot(B, R.T))
        # fix presumed rounding errors in the B matrix by making it positive
        # semi-definite. 
        return nearest_pos_semi_def(B_vox)

    @one_time
    def q_vector(self):
        ''' Get DWI q vector referring to voxel space

        Parameters
        ----------
        None

        Returns
        -------
        q: (3,) array
           Estimated DWI q vector in *voxel* orientation space.  Returns
           None if this is not (detectably) a DWI
        '''
        B = self.b_matrix
        if B is None:
            return None
        return B2q(B)

    @one_time
    def ice_dims(self):
        ''' ICE dims from CSA header '''
        return csar.get_ice_dims(self.csa_header)


class MosaicWrapper(SiemensWrapper):
    ''' Class for Siemens Mosaic format data '''
    is_mosaic = True
    
    def __init__(self, dcm_data=None, csa_header=None, n_mosaic=None):
        ''' Initialize Siemens Mosaic wrapper

        The Siemens-specific information is in the `csa_header`, either
        passed in here, or read from the input `dcm_data`. 

        Parameters
        ----------
        dcm_data : None or object, optional
           object should allow attribute access.  If `csa_header` is
           None, it should also be possible for to extract a CSA header
           from `dcm_data`. Usually this will be a
           ``dicom.dataset.Dataset`` object resulting from reading a
           DICOM file.  If None, we just make an empty dict.
        csa_header : None or mapping, optional
           mapping giving values for Siemens CSA image sub-header.
        n_mosaic : None or int, optional
           number of images in mosaic.  If None, we try to get this
           number fron `csa_header`.  If this fails, we raise an error
        '''
        SiemensWrapper.__init__(self, dcm_data, csa_header)
        if n_mosaic is None:
            try:
                n_mosaic = csar.get_n_mosaic(self.csa_header)
            except KeyError:
                n_mosaic = None
            if n_mosaic is None or n_mosaic == 0:
                raise WrapperError('No valid mosaic number in CSA '
                                   'header; is this really '
                                   'Siemans mosiac data?')
        self.n_mosaic = n_mosaic
        self.mosaic_size = np.ceil(np.sqrt(n_mosaic))
        
    @one_time
    def image_shape(self):
        # reshape pixel slice array back from mosaic
        rows = self.get('Rows')
        cols = self.get('Columns')
        if None in (rows, cols):
            return None
        mosaic_size = self.mosaic_size
        return (rows / mosaic_size,
                cols / mosaic_size,
                self.n_mosaic)
                
    @one_time
    def image_position(self):
        ''' Return position of first voxel in data block

        Adjusts Siemans mosaic position vector for bug in mosaic format
        position.  See ``dicom_mosaic`` in doc/theory for details. 

        Parameters
        ----------
        None

        Returns
        -------
        img_pos : (3,) array
           position in mm of voxel (0,0,0) in Mosaic array
        '''
        ipp = self.get('ImagePositionPatient')
        o_rows, o_cols = (self.get('Rows'), self.get('Columns'))
        iop = self.image_orient_patient
        vox = self.voxel_sizes
        if None in (ipp, o_rows, o_cols, iop, vox):
            return None
        # size of mosaic array before rearranging to 3D
        md_xy = np.array([o_rows, o_cols])
        # size of slice X, Y in array after reshaping to 3D
        rd_xy = md_xy / self.mosaic_size
        # apply algorithm for undoing mosaic translation error - see
        # ``dicom_mosaic`` doc
        vox_trans_fixes = (md_xy - rd_xy) / 2
        M = iop * vox[:2]
        return ipp + np.dot(M, vox_trans_fixes[:,None]).ravel()
    
    def get_data(self):
        ''' Get scaled image data from DICOMs

        Resorts data block from mosaic to 3D

        Returns
        -------
        data : array
           array with data as scaled from any scaling in the DICOM
           fields. 
        '''
        shape = self.image_shape
        if shape is None:
            raise WrapperError('No valid information for image shape')
        n_rows, n_cols, n_mosaic = shape
        mosaic_size = self.mosaic_size
        data = self.get_pixel_array()
        v4=data.reshape(mosaic_size,n_rows,
                        mosaic_size,n_cols)
        v4p=np.rollaxis(v4,2,1)
        v3=v4p.reshape(mosaic_size*mosaic_size,n_rows,n_cols)
        # delete any padding slices
        v3 = v3[:n_mosaic]
        return self._scale_data(v3)


def none_matcher(val1, val2, match_func=lambda x, y: x == y):
    if (val1, val2) == (None, None):
        return True
    if None in (val1, val2):
        return False
    return match_func(val1, val2)
