""" Testing parrec module
"""

from os.path import join as pjoin, dirname
from glob import glob

import numpy as np
from numpy import array as npa

from ..parrec import (parse_PAR_header, PARRECHeader, PARRECError, vol_numbers,
                      vol_is_full)
from ..openers import Opener

from numpy.testing import (assert_almost_equal,
                           assert_array_equal)

from nose.tools import (assert_true, assert_false, assert_raises,
                        assert_equal, assert_not_equal)


DATA_PATH = pjoin(dirname(__file__), 'data')
EG_PAR = pjoin(DATA_PATH, 'phantom_EPI_asc_CLEAR_2_1.PAR')
EG_REC = pjoin(DATA_PATH, 'phantom_EPI_asc_CLEAR_2_1.REC')
with Opener(EG_PAR, 'rt') as _fobj:
    HDR_INFO, HDR_DEFS = parse_PAR_header(_fobj)
# Affine as we determined it mid-2014
AN_OLD_AFFINE = np.array(
    [[-3.64994708, 0.,   1.83564171, 123.66276611],
     [0.,         -3.75, 0.,          115.617    ],
     [0.86045705,  0.,   7.78655376, -27.91161211],
     [0.,          0.,   0.,           1.        ]])
# Affine from Philips-created NIfTI
PHILIPS_AFFINE = np.array(
    [[  -3.65  ,   -0.0016,    1.8356,  125.4881],
     [   0.0016,   -3.75  ,   -0.0004,  117.4916],
     [   0.8604,    0.0002,    7.7866,  -28.3411],
     [   0.    ,    0.    ,    0.    ,    1.    ]])

# Affines generated by parrec.py from test data in many orientations
# Data from http://psydata.ovgu.de/philips_achieva_testfiles/conversion2
PREVIOUS_AFFINES={
    "Phantom_EPI_3mm_cor_20APtrans_15RLrot_SENSE_15_1" :
    npa([[  -3.        ,    0.        ,    0.        ,  118.5       ],
         [   0.        ,   -0.77645714,   -3.18755523,   72.82738377],
         [   0.        ,   -2.89777748,    0.85410285,   97.80720486],
         [   0.        ,    0.        ,    0.        ,    1.        ]]),
    "Phantom_EPI_3mm_cor_SENSE_8_1" :
    npa([[  -3.  ,    0.  ,    0.  ,  118.5 ],
         [   0.  ,    0.  ,   -3.3 ,   64.35],
         [   0.  ,   -3.  ,    0.  ,  118.5 ],
         [   0.  ,    0.  ,    0.  ,    1.  ]]),
    "Phantom_EPI_3mm_sag_15AP_SENSE_13_1" :
    npa([[   0.        ,    0.77645714,    3.18755523,  -92.82738377],
         [  -3.        ,    0.        ,    0.        ,  118.5       ],
         [   0.        ,   -2.89777748,    0.85410285,   97.80720486],
         [   0.        ,    0.        ,    0.        ,    1.        ]]),
    "Phantom_EPI_3mm_sag_15FH_SENSE_12_1" :
    npa([[   0.77645714,    0.        ,    3.18755523,  -92.82738377],
         [  -2.89777748,    0.        ,    0.85410285,   97.80720486],
         [   0.        ,   -3.        ,    0.        ,  118.5       ],
         [   0.        ,    0.        ,    0.        ,    1.        ]]),
    "Phantom_EPI_3mm_sag_15RL_SENSE_11_1" :
    npa([[   0.        ,    0.        ,    3.3       ,  -64.35      ],
         [  -2.89777748,   -0.77645714,    0.        ,  145.13226726],
         [   0.77645714,   -2.89777748,    0.        ,   83.79215357],
         [   0.        ,    0.        ,    0.        ,    1.        ]]),
    "Phantom_EPI_3mm_sag_SENSE_7_1" :
    npa([[   0.  ,    0.  ,    3.3 ,  -64.35],
         [  -3.  ,    0.  ,    0.  ,  118.5 ],
         [   0.  ,   -3.  ,    0.  ,  118.5 ],
         [   0.  ,    0.  ,    0.  ,    1.  ]]),
    "Phantom_EPI_3mm_tra_-30AP_10RL_20FH_SENSE_14_1" :
    npa([[   0.  ,    0.  ,    3.3 ,  -74.35],
         [  -3.  ,    0.  ,    0.  ,  148.5 ],
         [   0.  ,   -3.  ,    0.  ,  138.5 ],
         [   0.  ,    0.  ,    0.  ,    1.  ]]),
    "Phantom_EPI_3mm_tra_15FH_SENSE_9_1" :
    npa([[   0.77645714,    0.        ,    3.18755523,  -92.82738377],
         [  -2.89777748,    0.        ,    0.85410285,   97.80720486],
         [   0.        ,   -3.        ,    0.        ,  118.5       ],
         [   0.        ,    0.        ,    0.        ,    1.        ]]),
    "Phantom_EPI_3mm_tra_15RL_SENSE_10_1" :
    npa([[   0.        ,    0.        ,    3.3       ,  -64.35      ],
         [  -2.89777748,   -0.77645714,    0.        ,  145.13226726],
         [   0.77645714,   -2.89777748,    0.        ,   83.79215357],
         [   0.        ,    0.        ,    0.        ,    1.        ]]),
    "Phantom_EPI_3mm_tra_SENSE_6_1" :
    npa([[  -3.  ,    0.  ,    0.  ,  118.5 ],
         [   0.  ,   -3.  ,    0.  ,  118.5 ],
         [   0.  ,    0.  ,    3.3 ,  -64.35],
         [   0.  ,    0.  ,    0.  ,    1.  ]]),
}

# Original values for b values in DTI.PAR, still in PSL orientation
DTI_PAR_BVECS = np.array([[-0.667,  -0.667,  -0.333],
                          [-0.333,   0.667,  -0.667],
                          [-0.667,   0.333,   0.667],
                          [-0.707,  -0.000,  -0.707],
                          [-0.707,   0.707,   0.000],
                          [-0.000,   0.707,   0.707],
                          [ 0.000,   0.000,   0.000],
                          [ 0.000,   0.000,   0.000]])

# DTI.PAR values for bvecs
DTI_PAR_BVALS = [1000] * 6 + [0, 1000]


def test_header():
    hdr = PARRECHeader(HDR_INFO, HDR_DEFS)
    assert_equal(hdr.get_data_shape(), (64, 64, 9, 3))
    assert_equal(hdr.get_data_dtype(), np.dtype(np.int16))
    assert_equal(hdr.get_zooms(), (3.75, 3.75, 8.0, 2.0))
    assert_equal(hdr.get_data_offset(), 0)
    si = np.array([np.unique(x) for x in hdr.get_data_scaling()]).ravel()
    assert_almost_equal(si, (1.2903541326522827, 0.0), 5)


def test_header_scaling():
    hdr = PARRECHeader(HDR_INFO, HDR_DEFS)
    def_scaling = [np.unique(x) for x in hdr.get_data_scaling()]
    fp_scaling = [np.unique(x) for x in hdr.get_data_scaling('fp')]
    dv_scaling = [np.unique(x) for x in hdr.get_data_scaling('dv')]
    # Check default is dv scaling
    assert_array_equal(def_scaling, dv_scaling)
    # And that it's almost the same as that from the converted nifti
    assert_almost_equal(dv_scaling, [[1.2903541326522827], [0.0]], 5)
    # Check that default for get_slope_inter is dv scaling
    for hdr in (hdr, PARRECHeader(HDR_INFO, HDR_DEFS)):
        scaling = [np.unique(x) for x in hdr.get_data_scaling()]
        assert_array_equal(scaling, dv_scaling)
    # Check we can change the default
    assert_false(np.all(fp_scaling == dv_scaling))


def test_orientation():
    hdr = PARRECHeader(HDR_INFO, HDR_DEFS)
    assert_array_equal(HDR_DEFS['slice orientation'], 1)
    assert_equal(hdr.get_slice_orientation(), 'transverse')
    hdr_defc = HDR_DEFS.copy()
    hdr = PARRECHeader(HDR_INFO, hdr_defc)
    hdr_defc['slice orientation'] = 2
    assert_equal(hdr.get_slice_orientation(), 'sagittal')
    hdr_defc['slice orientation'] = 3
    hdr = PARRECHeader(HDR_INFO, hdr_defc)
    assert_equal(hdr.get_slice_orientation(), 'coronal')


def test_data_offset():
    hdr = PARRECHeader(HDR_INFO, HDR_DEFS)
    assert_equal(hdr.get_data_offset(), 0)
    # Can set 0
    hdr.set_data_offset(0)
    # Can't set anything else
    assert_raises(PARRECError, hdr.set_data_offset, 1)


def test_affine():
    hdr = PARRECHeader(HDR_INFO, HDR_DEFS)
    default = hdr.get_affine()
    scanner = hdr.get_affine(origin='scanner')
    fov = hdr.get_affine(origin='fov')
    assert_array_equal(default, scanner)
    # rotation part is same
    assert_array_equal(scanner[:3, :3], fov[:3, :3])
    # offset not
    assert_false(np.all(scanner[:3, 3] == fov[:3, 3]))
    # Regression test against what we were getting before
    assert_almost_equal(default, AN_OLD_AFFINE)
    # Test against RZS of Philips affine
    assert_almost_equal(default[:3, :3], PHILIPS_AFFINE[:3, :3], 2)


def test_affine_regression():
    # Test against checked affines from previous runs
    # Checked against Michael's data using some GUI tools
    # Data at http://psydata.ovgu.de/philips_achieva_testfiles/conversion2
    for basename, exp_affine in PREVIOUS_AFFINES.items():
        fname = pjoin(DATA_PATH, basename + '.PAR')
        with open(fname, 'rt') as fobj:
            hdr = PARRECHeader.from_fileobj(fobj)
        assert_almost_equal(hdr.get_affine(), exp_affine)


def test_vol_number():
    # Test algorithm for calculating volume number
    assert_array_equal(vol_numbers([1, 3, 0]), [0, 0, 0])
    assert_array_equal(vol_numbers([1, 3, 0, 0]), [ 0, 0, 0, 1])
    assert_array_equal(vol_numbers([1, 3, 0, 0, 0]), [0, 0, 0, 1, 2])
    assert_array_equal(vol_numbers([1, 3, 0, 0, 4]), [0, 0, 0, 1, 0])
    assert_array_equal(vol_numbers([1, 3, 0, 3, 1, 0]),
                       [0, 0, 0, 1, 1, 1])
    assert_array_equal(vol_numbers([1, 3, 0, 3, 1, 0, 4]),
                       [0, 0, 0, 1, 1, 1, 0])
    assert_array_equal(vol_numbers([1, 3, 0, 3, 1, 0, 3, 1, 0]),
                       [0, 0, 0, 1, 1, 1, 2, 2, 2])


def test_vol_is_full():
    assert_array_equal(vol_is_full([3, 2, 1], 3), True)
    assert_array_equal(vol_is_full([3, 2, 1], 4), False)
    assert_array_equal(vol_is_full([4, 2, 1], 4), False)
    assert_array_equal(vol_is_full([3, 2, 4, 1], 4), True)
    assert_array_equal(vol_is_full([3, 2, 1], 3, 0), False)
    assert_array_equal(vol_is_full([3, 2, 0, 1], 3, 0), True)
    assert_raises(ValueError, vol_is_full, [2, 1, 0], 2)
    assert_raises(ValueError, vol_is_full, [3, 2, 1], 3, 2)
    assert_array_equal(vol_is_full([3, 2, 1, 2, 3, 1], 3),
                       [True] * 6)
    assert_array_equal(vol_is_full([3, 2, 1, 2, 3], 3),
                       [True, True, True, False, False])


def test_vol_calculations():
    # Test vol_is_full on sample data
    for par in glob(pjoin(DATA_PATH, '*.PAR')):
        with open(par, 'rt') as fobj:
            gen_info, slice_info = parse_PAR_header(fobj)
        slice_nos = slice_info['slice number']
        max_slice = gen_info['max_slices']
        assert_equal(set(slice_nos), set(range(1, max_slice + 1)))
        assert_array_equal(vol_is_full(slice_nos, max_slice), True)
        if par.endswith('NA.PAR'):
            continue # Cannot parse this one
        # Fourth dimension shows same number of volumes as vol_numbers
        hdr = PARRECHeader(gen_info, slice_info)
        shape = hdr.get_data_shape()
        d4 = 1 if len(shape) == 3 else shape[3]
        assert_equal(max(vol_numbers(slice_nos)), d4 - 1)


def test_diffusion_parameters():
    # Check getting diffusion parameters from diffusion example
    dti_par = pjoin(DATA_PATH, 'DTI.PAR')
    with open(dti_par, 'rt') as fobj:
        dti_hdr = PARRECHeader.from_fileobj(fobj)
    assert_equal(dti_hdr.get_data_shape(), (80, 80, 10, 8))
    assert_equal(dti_hdr.general_info['diffusion'], 1)
    bvals, bvecs = dti_hdr.get_bvals_bvecs()
    assert_almost_equal(bvals, DTI_PAR_BVALS)
    # DTI_PAR_BVECS gives bvecs copied from first slice each vol in DTI.PAR
    # Permute to match bvec directions to acquisition directions
    assert_almost_equal(bvecs, DTI_PAR_BVECS[:, [2, 0, 1]])
    # Check q vectors
    assert_almost_equal(dti_hdr.get_q_vectors(), bvals[:, None] * bvecs)
