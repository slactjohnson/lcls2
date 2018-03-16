# Import the Python-level symbols of numpy
import numpy as np

# Import the C-level symbols of numpy
cimport numpy as cnp

from libc.stdlib cimport free
from cpython cimport PyObject, Py_INCREF

# Numpy must be initialized. When using numpy from C or Cython you must
# _always_ do that, or you will have segfaults
cnp.import_array()

from libcpp.vector cimport vector
cimport libc.stdint as si

cdef extern from "xtcdata/xtc/DescData.hh" namespace "XtcData":
    cdef cppclass AlgVersion:
        AlgVersion(cnp.uint8_t major, cnp.uint8_t minor, cnp.uint8_t micro) except+
        unsigned major()

    cdef cppclass Alg:
        Alg(const char* alg, cnp.uint8_t major, cnp.uint8_t minor, cnp.uint8_t micro)
        const char* name()

    cdef cppclass Name:
        enum DataType: UINT8, UINT16, UINT32, UINT64, INT8, INT16, INT32, INT64, FLOAT, DOUBLE
        Name(const char* name, DataType type, int rank)
        const char* name()
        DataType    type()
        cnp.uint32_t    rank()

cdef class PyAlgVer:
    cdef AlgVersion* cptr
    def __cinit__(self):
        self.cptr = new AlgVersion(9,8,7)

    def __dealloc__(self):
        del self.cptr

    def major(self):
        return self.cptr.major()

cdef class PyAlg:
    cdef Alg* cptr
    def __cinit__(self):
        self.cptr = new Alg("hsd",4,5,6)

    def __dealloc__(self):
        del self.cptr

    def name(self):
        return self.cptr.name()

cdef class PyName:
    cdef Name* cptr

    def __cinit__(self, int type, int version):
        self.cptr = new Name(b"foo",<Name.DataType>type,version)

    def __dealloc__(self):
        del self.cptr

    def type(self):
        return self.cptr.type()

    #def name(self):
    #    return <unicode>self.cptr.name()
