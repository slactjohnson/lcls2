#ifndef PSALG_GEOMETRYACCESS_H
#define PSALG_GEOMETRYACCESS_H

//------------------

//#include <string> // in GeometryObject.hh
//#include <vector> // in GeometryObject.hh
#include <map>
#include <sstream>  // stringstream
#include <stdint.h>  // uint8_t, uint16_t, uint32_t, etc.

#include "psalg/geometry/GeometryObject.hh"

#include "psalg/calib/NDArray.hh"

//------------------

namespace geometry {

/// @addtogroup geometry

/**
 *  @ingroup geometry
 *
 *  @brief Class supports universal detector geometry description.
 *
 *  This software was developed for the LCLS project.  If you use all or 
 *  part of it, please give an appropriate acknowledgment.
 *
 *  @see GeometryObject, CalibFileFinder, psalg/geometry/test/ex_geometry_access.cpp
 *
 *  @anchor interface
 *  @par<interface> Interface Description
 * 
 *  @li  Include
 *  @code
 *  #include "psalg/geometry/GeometryAccess.hh"
 *  #include "psalg/calib/NDArray.hh" // need it if image or constants are returned
 *  @endcode
 *
 *  @li Instatiation
 *  \n
 *  Code below instateates GeometryAccess object using path to the calibration "geometry" file and verbosity control bit-word:
 *  @code
 *  std::string path = /reg/d/psdm/<INS>/<experiment>/calib/<calib-type>/<det-src>/geometry/0-end.data"
 *  bitword_t print_bits = 0377; // or = 0 (by default) - to suppress printout from this object. 
 *  geometry::GeometryAccess geometry(path, print_bits);
 *  @endcode
 *  To find path automatically use CalibFileFinder.
 *
 *  @li Access methods
 *  @code
 *    // Access and print coordinate arrays:
 *        const pixel_coord_t* X;
 *        const pixel_coord_t* Y;
 *        const pixel_coord_t* Z;
 *        gsize_t   size;
 *        bool do_tilt=true;
 *        geometry.get_pixel_coords(X,Y,Z,size);
 *        cout << "size=" << size << '\n' << std::fixed << std::setprecision(1);  
 *        cout << "X: "; for(unsigned i=0; i<10; ++i) cout << std::setw(10) << X[i] << ", "; cout << "...\n"; 
 *        // or get coordinate arrays for specified geometry object:
 *        geometry.get_pixel_coords(X,Y,Z,size, "QUAD:V1", 1, do_tilt);
 *        // then use X, Y, Z, size
 *    
 *    // Access pixel X,Y coordinate [um] arrays projected toward origin on specified zplane, if zplane=0 then zplane is averaged Z:
 *        const pixel_coord_t Zplane=12345; //[um] or 0
 *        geometry.get_pixel_xy_at_z(X,Y,size,Zplane);
 *    
 *    // Access pixel areas:
 *        const pixel_area_t* A;
 *        gsize_t   size;
 *        geometry.get_pixel_areas(A,size);
 * 
 *    // Access pixel mask:
 *        const pixel_mask_t* mask;
 *        gsize_t   size;
 *        bitword_t   mbits=0377; // 1-edges; 2-wide central cols; 4-non-bound; 8-non-bound neighbours
 *        geometry.get_pixel_mask(A, size, std::string(), 0, mbits);
 * 
 *    // Access pixel size for entire detector:
 *        pixel_coord_t pix_scale_size = geometry.get_pixel_scale_size ();
 *        // or for specified geometry object, for example one quad of CSPAD
 *        pixel_coord_t pix_scale_size = geometry.get_pixel_scale_size("QUAD:V1", 1);
 *    
 *    // Access pixel indexes for image:
 *        const pixel_idx_t * iX;                                                                             
 *        const pixel_idx_t * iY;                                                                             
 *        gsize_t   isize;                                                                                
 *        // optional parameters for specified geometry  
 *        const std::string ioname = "QUAD:V1";                                                            
 *        const segindex_t ioindex = 1;                                                                      
 *        const pixel_coord_t pix_scale_size_um = 109.92;                                                         
 *        const int xy0_off_pix[] = {200,200};
 *        
 *        // this call returns index arrays iX, iY of size=isize for QUAD with offset 
 *        geometry.get_pixel_coord_indexes(iX, iY, isize, ioname, ioindex, pix_scale_size_um, xy0_off_pix, do_tilt);
 *        
 *        // this call returns index arrays for entire detector with auto generated minimal offset
 *        geometry.get_pixel_coord_indexes(iX, iY, isize);
 *        // then use iX, iY, isize, for example make image as follows.   
 *        
 *    // Access pixel iX, iY indexes for projected to specified z-plane coordinates:
 *        const pixel_coord_t Zplane=12345; //[um] or 0
 *        geometry.get_pixel_xy_inds_at_z(iX, iY, isize, Zplane);
 *
 *    // Make image from index, iX, iY, and intensity, W, arrays
 *        ndarray<geometry::GeometryAccess::image_t> img = 
 *                geometry::GeometryAccess::img_from_pixel_arrays(iX, iY, 0, isize);
 *    
 *    // Access and print comments from the calibration "geometry" file:
 *        std::map<int, std::string>& dict = geometry.get_dict_of_comments ();
 *        cout << "dict[0] = " << dict[0] << '\n';
 *  @endcode
 * 
 *  @li Print methods
 *  @code
 *    geometry.print_pixel_coords();
 *    geometry.print_pixel_coords("QUAD:V1", 1);
 *    geometry.print_list_of_geos();
 *    geometry.print_list_of_geos_children();
 *    geometry.print_comments_from_dict();
 *
 *    // or print info about specified geometry objects (see class GeometryObject):
 *    geometry.get_geo("QUAD:V1", 1)->print_geo();
 *    geometry.get_top_geo()->print_geo_children();
 *  @endcode
 * 
 *  @li Modify and save new geometry file methods
 *  @code
 *    geometry.set_geo_pars("QUAD:V1", x0, y0, z0, rot_z,...<entire-list-of-9-parameters>);
 *    geometry.move_geo("QUAD:V1", 1, 10, 20, 0);
 *    geometry.tilt_geo("QUAD:V1", 1, 0.01, 0, 0);
 *    geometry.save_pars_in_file("new-file-name.txt");
 *  @endcode
 *
 *  @author Mikhail S. Dubrovin
 */

using namespace psalg;

class GeometryAccess {
public:

  typedef psalg::types::shape_t shape_t;
  typedef GeometryObject::pGO pGO;

  typedef double image_t;

  /**
   *  @brief Class constructor accepts path to the calibration "geometry" file and verbosity control bit-word 
   *  
   *  @param[in] path  path to the calibration "geometry" file
   *  @param[in] pbits verbosity control bit-word; 
   *  \n         =0  print nothing, 
   *  \n         +1  info about loaded file, 
   *  \n         +2  list of geometry objects, 
   *  \n         +8  list of geometry objects with childrens, 
   *  \n         +16 info about setting relations between geometry objects, 
   *  \n         +32 info about pixel coordinate reconstruction
   */ 
  GeometryAccess(const std::string& path = "");

  /**
   * Constructor loads parameters from string stream
   */
  GeometryAccess(std::stringstream& ss);

  virtual ~GeometryAccess() ;

  /// Returns shared pointer to the geometry object specified by name and index 
  pGO get_geo(const std::string& oname, const segindex_t& oindex);

  /// Returns shared pointer to the top geometry object, for exampme CSPAD
  pGO get_top_geo();

  /// Returns pixel coordinate arrays X, Y, Z, of size for specified geometry object 
  /**
   *  @param[out] X - pointer to x pixel coordinate array
   *  @param[out] Y - pointer to y pixel coordinate array
   *  @param[out] Z - pointer to z pixel coordinate array
   *  @param[out] size - size of the pixel coordinate array (number of pixels)
   *  @param[in]  oname - object name
   *  @param[in]  oindex - object index
   *  @param[in]  do_tilt - on/off tilt angle correction
   *  @param[in]  do_eval - update all evaluated arrays
   */
  void  get_pixel_coords(const pixel_coord_t*& X, 
                         const pixel_coord_t*& Y, 
                         const pixel_coord_t*& Z, 
                         gsize_t& size,
			 const std::string& oname = std::string(), 
			 const segindex_t& oindex = 0,
                         const bool do_tilt=true,
                         const bool do_eval=false);

  NDArray<const pixel_coord_t>* get_pixel_coords(const AXIS axis=AXIS_X);

  /// Returns pixel coordinate arrays XatZ, YatZ, of size for specified Zplane and geometry object 
  /**
   *  @param[out] XatZ - pointer to x pixel coordinate array at specified Zplane
   *  @param[out] YatZ - pointer to y pixel coordinate array
   *  @param[out] size - size of the pixel coordinate array (number of pixels)
   *  @param[in]  Zplane - z-coordinate of the plane for projection
   *  @param[in]  oname - object name
   *  @param[in]  oindex - object index
   */
  void get_pixel_xy_at_z(const pixel_coord_t*& XatZ, 
                         const pixel_coord_t*& YatZ, 
                         gsize_t& size,
        		 const pixel_coord_t& Zplane = 0,
			 const std::string& oname = std::string(), 
			 const segindex_t& oindex = 0);

  NDArray<const pixel_coord_t>* get_pixel_coords_at_z(const pixel_coord_t Zplane=0, const AXIS axis=AXIS_X);

  /// Returns pixel areas array A, of size for specified geometry object 
  /**
   *  @param[out] A - pointer to pixel areas array
   *  @param[out] size - size of the pixel array (number of pixels)
   *  @param[in]  oname - object name
   *  @param[in]  oindex - object index
   */
  void  get_pixel_areas(const pixel_area_t*& A, 
                        gsize_t& size,
		        const std::string& oname = std::string(), 
		        const segindex_t& oindex = 0);

  NDArray<const pixel_area_t>* get_pixel_areas();

  /// Returns pixel mask array of size for specified geometry object 
  /**
   *  @param[out] mask - pointer to pixel mask array
   *  @param[out] size - size of the pixel array (number of pixels)
   *  @param[in]  oname - object name
   *  @param[in]  oindex - object index
   *  @param[in]  mbits - mask control bits; 
   *              +1-mask edges, 
   *              +2-two wide central columns, 
   *              +4-non-bounded, 
   *              +8-non-bounded neighbours.
   */
  void get_pixel_mask(const pixel_mask_t*& mask, 
                      gsize_t& size,
		      const std::string& oname = std::string(),
 		      const segindex_t& oindex = 0,
		      const bitword_t& mbits = 0377);

  NDArray<const pixel_mask_t>* get_pixel_mask(const unsigned& mbits=0377);

  /// Returns pixel scale size for specified geometry object through its children segment
  /**
   *  @param[in]  oname - object name
   *  @param[in]  oindex - object index
   */
  pixel_coord_t get_pixel_scale_size(const std::string& oname = std::string(), 
                                     const segindex_t& oindex = 0);

  /// Returns dictionary of comments
  //std::map<std::string, std::string>& get_dict_of_comments() {return m_dict_of_comments;}
  std::map<int, std::string>& get_dict_of_comments() {return m_dict_of_comments;}

  /// Prints the list of geometry objects
  void print_list_of_geos();

  /// Prints the list of geometry objects with children
  void print_list_of_geos_children();

  /// Prints comments loaded from input file and kept in the dictionary  
  void print_comments_from_dict();

  /// Prints beginning of pixel coordinate arrays for specified geometry object (top object by default)
  void print_pixel_coords(const std::string& oname= std::string(), 
			  const segindex_t& oindex = 0);

  /// Prints geometry info using all other print_* methods
  void print_geometry_info(const bitword_t& pbits=255);

  /// Returns pixel coordinate index arrays iX, iY of size for specified geometry object 
 /**
   *  @param[out] iX - pointer to x pixel index coordinate array
   *  @param[out] iY - pointer to y pixel index coordinate array
   *  @param[out] size - size of the pixel coordinate array (number of pixels)
   *  @param[in]  oname - object name (deafault - top object)
   *  @param[in]  oindex - object index (default = 0)
   *  @param[in]  pix_scale_size_um - ex.: 109.92 (default - search for the first segment pixel size)
   *  @param[in]  xy0_off_pix - array containing X and Y coordinates of the offset (default - use xmin, ymin)
   *  @param[in]  do_tilt - on/off tilt angle correction
   */
  void get_pixel_coord_indexes(const pixel_idx_t *& iX, 
                               const pixel_idx_t *& iY, 
			       gsize_t& size,
                               const std::string& oname = std::string(), 
			       const segindex_t& oindex = 0, 
                               const pixel_coord_t& pix_scale_size_um = 0, 
                               const int* xy0_off_pix = 0,
                               const bool do_tilt=true);

  NDArray<const pixel_idx_t>* get_pixel_coord_indexes(const AXIS axis=AXIS_X,
                                                      const pixel_coord_t pix_scale_size_um = 0,
                                                      const int* xy0_off_pix = 0);

  /// Returns pixel coordinate index arrays iX, iY of size for specified Zplane and geometry object 
 /**
   *  @param[out] iX - pointer to x pixel index coordinate array
   *  @param[out] iY - pointer to y pixel index coordinate array
   *  @param[out] size - size of the pixel coordinate array (number of pixels)
   *  @param[in]  Zplane - z-coordinate of the plane for projection (default=0 - evaluated as average z ovetr all pixels)
   *  @param[in]  oname - object name (deafault - top object)
   *  @param[in]  oindex - object index (default = 0)
   *  @param[in]  pix_scale_size_um - ex.: 109.92 (default - search for the first segment pixel size)
   *  @param[in]  xy0_off_pix - array containing X and Y coordinates of the offset (default - use xmin, ymin)
   */
  void get_pixel_xy_inds_at_z(const pixel_idx_t *& iX, 
                              const pixel_idx_t *& iY, 
			      gsize_t& size,
        		      const pixel_coord_t& Zplane = 0,
                              const std::string& oname = std::string(), 
			      const segindex_t& oindex = 0, 
                              const pixel_coord_t& pix_scale_size_um = 0, 
                              const int* xy0_off_pix = 0);

  NDArray<const pixel_idx_t>* get_pixel_inds_at_z(const pixel_coord_t Zplane = 0,
                                                  const AXIS axis=AXIS_X,
                                                  const pixel_coord_t pix_scale_size_um = 0,
                                                  const int* xy0_off_pix = 0);

  /// Static method returns image as NDArray<image_t> object
 /**
   *  @param[in] iX - pointer to x pixel index coordinate array
   *  @param[in] iY - pointer to y pixel index coordinate array
   *  @param[in]  W - pointer to the intensity (weights) array (default - set 1 for each pixel) 
   *  @param[in] size - size of the pixel coordinate array (number of pixels)
   */
  static NDArray<image_t>
  img_from_pixel_arrays(const pixel_idx_t*& iX, 
                        const pixel_idx_t*& iY, 
                        const double* W = 0,
                        const gsize_t& size = 0);

  /// Returns reference to data member NDArray<image_t> image object
  NDArray<image_t>&
  ref_img_from_pixel_arrays(const pixel_idx_t*& iX, 
                            const pixel_idx_t*& iY, 
                            const double* W = 0,
                            const gsize_t& size = 0);

  /// Loads calibration file
 /**
   *  @param[in] path - path to the file with calibration parameters of type "geometry"
   */

  //void load_pars_from_string(const std::string& s);

  void load_pars_from_stringstream(std::stringstream& ss);
  void load_pars_from_string(const std::string& s);
  void load_pars_from_file(const std::string& fname = std::string());

  /// Saves calibration file
 /**
   *  @param[in] path - path to the file with calibration parameters of type "geometry"
   */
  void save_pars_in_file(const std::string& path = std::string());

  /// Sets the m_pbits - printout control bitword
 /**
   *  @param[in] pbits - printout control bitword
   */
  void set_print_bits(bitword_t pbits=0) {m_pbits=pbits;}

  /// Sets self object geometry parameters
  void set_geo_pars(const std::string& oname = std::string(), 
		    const segindex_t& oindex = 0,
                    const pixel_coord_t& x0 = 0,
                    const pixel_coord_t& y0 = 0,
                    const pixel_coord_t& z0 = 0,
                    const angle_t& rot_z = 0,
                    const angle_t& rot_y = 0,
                    const angle_t& rot_x = 0,                  
                    const angle_t& tilt_z = 0,
                    const angle_t& tilt_y = 0,
                    const angle_t& tilt_x = 0 
		    );

  /// Adds offset for origin of the self object w.r.t. current position
  void move_geo(const std::string& oname = std::string(), 
		const segindex_t& oindex = 0,
                const pixel_coord_t& dx = 0,
                const pixel_coord_t& dy = 0,
                const pixel_coord_t& dz = 0
		);

  /// Adds tilts to the self object w.r.t. current orientation
  void tilt_geo(const std::string& oname = std::string(), 
		const segindex_t& oindex = 0,
                const pixel_coord_t& dt_x = 0,
                const pixel_coord_t& dt_y = 0,
                const pixel_coord_t& dt_z = 0 
		);

  static void file_to_stringstream(const std::string& fname, std::stringstream& ss);

  //protected:

private:

  /// path to the calibration "geometry" file
  std::string m_path;

  /// print bits
  bitword_t m_pbits;

  /// pointer to x pixel coordinate index array
  pixel_idx_t* p_iX;

  /// pointer to y pixel coordinate index array
  pixel_idx_t* p_iY;
 
  /// Pointer to image, which is created as a member data of GeometryAccess object
  NDArray<image_t>* p_image;

  /// pointer to array of x pixel coordinates centrally projected to specified z plane
  pixel_coord_t* p_XatZ;

  /// pointer to array of y pixel coordinates centrally projected to specified z plane
  pixel_coord_t* p_YatZ;
 
  /// vector/list of shared pointers to geometry objects
  std::vector<pGO> v_list_of_geos;

  /// map/dictionary of comments from calibration "geometry" file 
  //std::map<std::string, std::string> m_dict_of_comments;
  std::map<int, std::string> m_dict_of_comments;

  /// Adds comment to the dictionary
  void add_comment_to_dict(const std::string& line);

  /// Parses input data line, creates and returns geometry object
  pGO parse_line(const std::string& line);

  /// Returns shp to the parent of geobj. If parent is not found adds geobj as a top parent and returns 0.
  pGO find_parent(const pGO& geobj);

  /// Set relations between geometry objects in the list_of_geos
  void set_relations();

  /// Returns class name for MsgLogger
  static const std::string name() {return "geometry";}

  // Copy constructor and assignment are disabled by default
  GeometryAccess(const GeometryAccess&) = delete;
  GeometryAccess& operator = (const GeometryAccess&) = delete;

//-------------------
};

} // namespace geometry

#endif // PSALG_GEOMETRYACCESS_H
