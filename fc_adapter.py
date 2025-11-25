# fc_adapter.py – improved FreeCAD adapter with proper property usage

import FreeCAD as App
import Part
import sys
import os
from typing import List, Optional

# Import Model from domain layer
from model import Model

# Ensure current directory is in Python path for importing joints module
_current_dir = os.path.dirname(os.path.abspath(__file__))
if _current_dir not in sys.path:
    sys.path.insert(0, _current_dir)


def _make_box(w, d, h, x=0.0, y=0.0, z=0.0):
    """Create a box shape at specified position"""
    b = Part.makeBox(float(w), float(d), float(h))
    b.translate(App.Vector(float(x), float(y), float(z)))
    return b


class BookshelfFeature:
    """
    FreeCAD FeaturePython proxy for bookshelf geometry.
    Uses Model as the source of truth, with FreeCAD Properties for backward compatibility.
    """
    
    def __init__(self, obj, model: Optional[Model] = None):
        """Initialize the FeaturePython object with Model as source of truth"""
        obj.Proxy = self
        
        # Store Model reference (source of truth)
        self._model = model
        
        # Core dimensions - kept for backward compatibility (joints.py reads these)
        self._add_property(obj, "App::PropertyFloat", "Width", "Dimensions", 
                          "Overall width (mm)", 800.0)
        self._add_property(obj, "App::PropertyFloat", "Depth", "Dimensions",
                          "Overall depth (mm)", 300.0)
        self._add_property(obj, "App::PropertyFloat", "Height", "Dimensions",
                          "Overall height (mm)", 2000.0)
        self._add_property(obj, "App::PropertyFloat", "Thickness", "Dimensions",
                          "Material thickness (mm)", 18.0)
        self._add_property(obj, "App::PropertyBool", "AddTopPanel", "Dimensions",
                          "Include top panel", True)
        
        # Shelves - store z-positions as a list (for backward compatibility)
        self._add_property(obj, "App::PropertyFloatList", "ShelfZPositions", "Design",
                          "Z coordinates of shelves (mm)")
        
        # Dividers - store x-positions as a list (for backward compatibility)
        self._add_property(obj, "App::PropertyFloatList", "DividerXPositions", "Design",
                          "X coordinates of divider centers (mm)")
        
        # Computed properties (read-only)
        self._add_property(obj, "App::PropertyInteger", "NumBays", "Computed",
                          "Number of bays (dividers + 1)", 1)
        self._add_property(obj, "App::PropertyFloat", "BayWidth", "Computed",
                          "Width of each bay (mm)", 0.0)
        self._add_property(obj, "App::PropertyFloat", "ClearWidth", "Computed",
                          "Interior width (mm)", 0.0)
        self._add_property(obj, "App::PropertyFloat", "ClearHeight", "Computed",
                          "Interior height (mm)", 0.0)
        
        # Make computed properties read-only
        for prop in ["NumBays", "BayWidth", "ClearWidth", "ClearHeight"]:
            obj.setEditorMode(prop, 1)  # Read-only
        
        # Sync FreeCAD properties from Model if provided
        if model is not None:
            self._sync_properties_from_model(obj, model)
    
    def _sync_properties_from_model(self, obj, model: Model):
        """Sync FreeCAD Properties from Model (for backward compatibility)"""
        obj.Width = float(model.W)
        obj.Depth = float(model.D)
        obj.Height = float(model.H)
        obj.Thickness = float(model.t)
        obj.AddTopPanel = bool(model.add_top)
        obj.ShelfZPositions = model.get_shelf_z_positions()
        obj.DividerXPositions = model.get_divider_x_positions()
    
    def get_model(self) -> Optional[Model]:
        """Get the Model object (source of truth)"""
        return self._model
    
    def set_model(self, obj, model: Model):
        """Update the Model and sync FreeCAD Properties"""
        self._model = model
        self._sync_properties_from_model(obj, model)
    
    def _add_property(self, obj, ptype, name, group, doc, default=None):
        """Add property if it doesn't exist"""
        if not hasattr(obj, name):
            obj.addProperty(ptype, name, group, doc)
            if default is not None:
                setattr(obj, name, default)
    
    def execute(self, obj):
        """Rebuild geometry when parameters change"""
        try:
            # Use Model as source of truth if available, otherwise fall back to FreeCAD properties
            if self._model is not None:
                model = self._model
                # Sync FreeCAD properties from Model (for backward compatibility)
                self._sync_properties_from_model(obj, model)
            else:
                # Fallback: create Model from FreeCAD properties (backward compatibility)
                from model import Shelf, Divider
                model = Model(
                    W=float(obj.Width),
                    D=float(obj.Depth),
                    H=float(obj.Height),
                    t=float(obj.Thickness),
                    add_top=bool(obj.AddTopPanel),
                    shelves=[Shelf(z=z) for z in obj.ShelfZPositions],
                    dividers=[Divider(x_center=x) for x in obj.DividerXPositions]
                )
                self._model = model
            
            # Update computed properties (for backward compatibility)
            obj.ClearWidth = model.clear_width
            obj.ClearHeight = model.clear_height
            obj.NumBays = model.num_bays
            obj.BayWidth = model.bay_width
            
            # Build geometry using Model
            obj.Shape = self._build_geometry(model)
        except Exception as e:
            App.Console.PrintError(f"[BookshelfFeature] Failed to build geometry: {e}\n")
            import traceback
            App.Console.PrintError(traceback.format_exc() + "\n")
    
    def _build_geometry(self, model: Model) -> Part.Compound:
        """Build the complete bookshelf geometry from Model"""
        W = model.W
        D = model.D
        H = model.H
        t = model.t
        add_top = model.add_top
        
        shelf_z_positions = model.get_shelf_z_positions()
        divider_x_positions = model.get_divider_x_positions()
        
        solids = []
        
        # --- Side panels ---
        solids.append(_make_box(t, D, H, x=0.0, y=0.0, z=0.0))  # Left
        solids.append(_make_box(t, D, H, x=W-t, y=0.0, z=0.0))  # Right
        
        # --- Bottom panel (full width) ---
        solids.append(_make_box(W-2*t, D, t, x=t, y=0.0, z=0.0))
        
        # --- Top panel (full width) ---
        if add_top:
            solids.append(_make_box(W-2*t, D, t, x=t, y=0.0, z=H-t))
        
        # --- Dividers ---
        if divider_x_positions:
            clear_h = model.clear_height
            z0 = t
            for x_center in divider_x_positions:
                x_left = x_center - 0.5 * t
                solids.append(_make_box(t, D, clear_h, x=x_left, y=0.0, z=z0))
        
        # --- Shelves (split per bay to avoid clipping through dividers) ---
        num_bays = model.num_bays
        
        for z in shelf_z_positions:
            if z > 0.0 and z < H:
                for bay_idx in range(num_bays):
                    # Calculate bay boundaries
                    if bay_idx == 0:
                        # First bay: left side to first divider
                        x_left = t
                        x_right = divider_x_positions[0] - 0.5*t if divider_x_positions else W - t
                    elif bay_idx == num_bays - 1:
                        # Last bay: last divider to right side
                        x_left = divider_x_positions[-1] + 0.5*t
                        x_right = W - t
                    else:
                        # Middle bays: between two dividers
                        x_left = divider_x_positions[bay_idx-1] + 0.5*t
                        x_right = divider_x_positions[bay_idx] - 0.5*t
                    
                    shelf_w = x_right - x_left
                    if shelf_w > 0:
                        solids.append(_make_box(shelf_w, D, t, x=x_left, y=0.0, z=z))
        
        return Part.Compound(solids)


class BookshelfViewProvider:
    """View provider for bookshelf"""
    
    def __init__(self, vobj):
        vobj.Proxy = self
    
    def getDisplayModes(self, vobj):
        return ["Shaded", "Wireframe"]
    
    def getDefaultDisplayMode(self):
        return "Shaded"
    
    def setDisplayMode(self, mode):
        return mode
    
    def onDelete(self, vobj, subelements):
        return True


def make_bookshelf(m: Model) -> App.DocumentObject:
    """
    Build a bookshelf from a Model object.
    Uses Model as the source of truth - no duplication.
    
    Args:
        m: Model object from model.py (source of truth)
        
    Returns:
        FreeCAD Bookshelf FeaturePython object
    """
    doc = App.ActiveDocument or App.newDocument("Bookshelf_A2")
    
    # Create or get the Bookshelf object
    bs = doc.getObject("Bookshelf")
    if bs is None or bs.TypeId != "Part::FeaturePython":
        if bs is not None:
            doc.removeObject(bs.Name)
        bs = doc.addObject("Part::FeaturePython", "Bookshelf")
        # Pass Model to BookshelfFeature (source of truth)
        BookshelfFeature(bs, model=m)
        
        # Add view provider if GUI is available
        if hasattr(bs, 'ViewObject') and bs.ViewObject is not None:
            BookshelfViewProvider(bs.ViewObject)
    else:
        # Update existing BookshelfFeature with new Model
        if hasattr(bs, 'Proxy') and isinstance(bs.Proxy, BookshelfFeature):
            bs.Proxy.set_model(bs, m)
        else:
            # Recreate if Proxy is wrong type
            BookshelfFeature(bs, model=m)
    
    # Trigger geometry rebuild (will use Model from Proxy)
    doc.recompute()
    
    return bs


def run_joints(bs) -> App.DocumentObject:
    """
    Create/ensure the Joints FeaturePython and link it to the Bookshelf.
    
    Args:
        bs: Bookshelf FeaturePython object
        
    Returns:
        Joints FeaturePython object
    """
    print(f"[fc_adapter] run_joints called for bookshelf: {bs.Name if bs else 'None'}")
    doc = App.ActiveDocument
    if not doc:
        print("[fc_adapter] ERROR: No active document")
        return None
    print(f"[fc_adapter] Active document: {doc.Name}")
    j = doc.getObject("Joints")
    print(f"[fc_adapter] Existing Joints object: {j.Name if j else 'None'}")
    
    if j is None:
        j = doc.addObject("Part::FeaturePython", "Joints")
        
        # Import joints module
        # Try multiple import strategies since FreeCAD's Python path might be different
        joints_module = None
        import_error = None
        
        # Strategy 1: Direct import (should work if joints.py is in sys.path)
        try:
            print(f"[fc_adapter] Attempting to import joints module...")
            print(f"[fc_adapter] Current directory: {_current_dir}")
            print(f"[fc_adapter] sys.path includes: {[p for p in sys.path if 'bookshelf' in p.lower() or 'downloads' in p.lower()][:3]}")
            import joints
            joints_module = joints
            print("[fc_adapter] ✓ Successfully imported joints module (direct import)")
            App.Console.PrintMessage("[fc_adapter] Successfully imported joints module (direct import)\n")
        except ImportError as e1:
            import_error = e1
            print(f"[fc_adapter] ✗ Direct import failed: {e1}")
            App.Console.PrintWarning(f"[fc_adapter] Direct import failed: {e1}\n")
            
            # Strategy 2: Try importing with explicit path
            try:
                import importlib.util
                joints_path = os.path.join(_current_dir, "joints.py")
                if os.path.exists(joints_path):
                    spec = importlib.util.spec_from_file_location("joints", joints_path)
                    joints_loaded = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(joints_loaded)
                    joints_module = joints_loaded
                    App.Console.PrintMessage(f"[fc_adapter] Successfully imported joints module (from file: {joints_path})\n")
            except Exception as e2:
                App.Console.PrintWarning(f"[fc_adapter] File-based import also failed: {e2}\n")
        
        if joints_module is None:
            print(f"[fc_adapter] ✗ Cannot import joints module. Last error: {import_error}")
            print(f"[fc_adapter] Current sys.path (first 5): {sys.path[:5]}")
            print(f"[fc_adapter] Current directory: {_current_dir}")
            print(f"[fc_adapter] joints.py exists: {os.path.exists(os.path.join(_current_dir, 'joints.py'))}")
            App.Console.PrintError(f"[fc_adapter] Cannot import joints module. Last error: {import_error}\n")
            App.Console.PrintError(f"[fc_adapter] Current sys.path: {sys.path[:3]}...\n")
            App.Console.PrintError(f"[fc_adapter] Current directory: {_current_dir}\n")
            return None
        
        try:
            print(f"[fc_adapter] Initializing JointsFP on object: {j.Name}")
            joints_module.JointsFP(j)
            print(f"[fc_adapter] ✓ JointsFP initialized successfully")
            
            # Only set up ViewProvider if ViewObject is available
            if hasattr(j, 'ViewObject') and j.ViewObject is not None:
                try:
                    joints_module.JointsVP(j.ViewObject)
                except Exception as ve:
                    App.Console.PrintWarning(f"[fc_adapter] Could not set ViewProvider: {ve}\n")
        except Exception as e:
            print(f"[fc_adapter] ✗ Error initializing joints: {e}")
            import traceback
            print(f"[fc_adapter] Traceback:\n{traceback.format_exc()}")
            App.Console.PrintError(f"[fc_adapter] Error initializing joints: {e}\n")
            App.Console.PrintError(f"[fc_adapter] Traceback: {traceback.format_exc()}\n")
            return None
    
    # Link to bookshelf
    if not hasattr(j, "Bookshelf"):
        try:
            j.addProperty("App::PropertyLink", "Bookshelf", "Input",
                          "Source bookshelf Part::Feature to join")
        except Exception:
            pass
    
    if not hasattr(j, "BookshelfName"):
        try:
            j.addProperty("App::PropertyString", "BookshelfName", "Input",
                          "Name of the Bookshelf object (legacy)")
        except Exception:
            pass
    
    # Set the link
    try:
        print(f"[fc_adapter] Setting Bookshelf link to: {bs.Name}")
        j.Bookshelf = bs
        print(f"[fc_adapter] ✓ Set Bookshelf link successfully")
        App.Console.PrintMessage(f"[fc_adapter] Set Bookshelf link to {bs.Name}\n")
    except Exception as e1:
        print(f"[fc_adapter] Bookshelf property failed: {e1}, trying BookshelfName...")
        try:
            j.BookshelfName = bs.Name
            print(f"[fc_adapter] ✓ Set BookshelfName successfully")
            App.Console.PrintMessage(f"[fc_adapter] Set BookshelfName to {bs.Name}\n")
        except Exception as e2:
            print(f"[fc_adapter] ✗ Both Bookshelf and BookshelfName failed")
            print(f"[fc_adapter] Error 1 (Bookshelf): {e1}")
            print(f"[fc_adapter] Error 2 (BookshelfName): {e2}")
            App.Console.PrintError(f"[fc_adapter] Could not set Bookshelf link on Joints.\n")
            App.Console.PrintError(f"[fc_adapter] Error 1 (Bookshelf property): {e1}\n")
            App.Console.PrintError(f"[fc_adapter] Error 2 (BookshelfName property): {e2}\n")
            return None
    
    # Set default joint parameters
    try:
        j.Method = "camlock_dowels"
        print(f"[fc_adapter] ✓ Set Method to camlock_dowels")
    except Exception as e:
        print(f"[fc_adapter] Warning: Could not set Method: {e}")
        pass
    
    try:
        j.ShelfPinsMode = "modular_grid"
        print(f"[fc_adapter] ✓ Set ShelfPinsMode to modular_grid")
    except Exception as e:
        print(f"[fc_adapter] Warning: Could not set ShelfPinsMode: {e}")
        pass
    
    print(f"[fc_adapter] ✓ run_joints completed successfully, returning joints object: {j.Name}")
    return j


def extract_bookshelf_data(bs) -> dict:
    """
    Extract data from a FreeCAD Bookshelf object into a plain dictionary.
    This isolates FreeCAD-specific code from other modules.
    
    Args:
        bs: FreeCAD Bookshelf FeaturePython object
        
    Returns:
        Dictionary with bookshelf data
    """
    try:
        return {
            'W': float(bs.Width),
            'D': float(bs.Depth),
            'H': float(bs.Height),
            't': float(bs.Thickness),
            'add_top': bool(bs.AddTopPanel),
            'shelf_z_positions': list(bs.ShelfZPositions) if hasattr(bs, 'ShelfZPositions') else [],
            'divider_x_positions': list(bs.DividerXPositions) if hasattr(bs, 'DividerXPositions') else [],
            'n_shelves': len(bs.ShelfZPositions) if hasattr(bs, 'ShelfZPositions') else 0,
            'n_dividers': len(bs.DividerXPositions) if hasattr(bs, 'DividerXPositions') else 0,
            'num_bays': int(bs.NumBays) if hasattr(bs, 'NumBays') else 1,
            'bay_width': float(bs.BayWidth) if hasattr(bs, 'BayWidth') else 0.0,
        }
    except Exception as e:
        App.Console.PrintError(f"[fc_adapter] Error extracting bookshelf data: {e}\n")
        return {}


def extract_joints_data(joints) -> dict:
    """
    Extract data from a FreeCAD Joints object into a plain dictionary.
    
    Args:
        joints: FreeCAD Joints FeaturePython object
        
    Returns:
        Dictionary with joints data
    """
    try:
        return {
            'method': str(joints.Method) if hasattr(joints, 'Method') else 'glue_dowels',
            'shelf_pins_mode': str(joints.ShelfPinsMode) if hasattr(joints, 'ShelfPinsMode') else 'none',
            'row_front_offset': float(joints.RowFrontOffset) if hasattr(joints, 'RowFrontOffset') else 37.0,
            'row_back_offset': float(joints.RowBackOffset) if hasattr(joints, 'RowBackOffset') else 37.0,
            'grid_pitch_z': float(joints.GridPitchZ) if hasattr(joints, 'GridPitchZ') else 32.0,
            'grid_bottom_margin': float(joints.GridBottomMargin) if hasattr(joints, 'GridBottomMargin') else 64.0,
            'grid_top_margin': float(joints.GridTopMargin) if hasattr(joints, 'GridTopMargin') else 96.0,
        }
    except Exception as e:
        App.Console.PrintError(f"[fc_adapter] Error extracting joints data: {e}\n")
        return {}


def extract_geometry_for_threejs(doc=None) -> dict:
    """
    Extract geometry from FreeCAD document and convert to Three.js format.
    REQUIRES Bookshelf_With_Joints object - no fallbacks.
    
    Args:
        doc: FreeCAD document (defaults to ActiveDocument)
        
    Returns:
        Dictionary with geometry data for Three.js visualization
        
    Raises:
        RuntimeError: If Bookshelf_With_Joints is not found or geometry extraction fails
    """
    if doc is None:
        doc = App.ActiveDocument
    
    if not doc:
        raise RuntimeError("No FreeCAD document available")
    
    # REQUIRE Bookshelf_With_Joints - no fallback
    final_obj = doc.getObject("Bookshelf_With_Joints")
    if not final_obj:
        # Check what objects exist for debugging
        available_objects = [obj.Name for obj in doc.Objects]
        error_msg = (
            f"Bookshelf_With_Joints object not found in document '{doc.Name}'. "
            f"Available objects: {available_objects}. "
            f"This means joints.execute() did not create the final object. "
            f"Check joints execution logs for errors."
        )
        App.Console.PrintError(f"[fc_adapter] {error_msg}\n")
        print(f"[fc_adapter] ERROR: {error_msg}")
        raise RuntimeError(error_msg)
    
    if not hasattr(final_obj, 'Shape'):
        error_msg = f"Bookshelf_With_Joints object '{final_obj.Name}' has no Shape attribute"
        App.Console.PrintError(f"[fc_adapter] {error_msg}\n")
        print(f"[fc_adapter] ERROR: {error_msg}")
        raise RuntimeError(error_msg)
    
    # Check if shape is valid - be lenient for compounds after boolean ops
    # Instead of strict isValid(), check if we can actually use it (has solids, can tessellate)
    shape = final_obj.Shape
    
    # Check for null shape
    if shape.isNull():
        error_msg = f"Bookshelf_With_Joints shape is null"
        App.Console.PrintError(f"[fc_adapter] {error_msg}\n")
        print(f"[fc_adapter] ERROR: {error_msg}")
        raise RuntimeError(error_msg)
    
    # Check if shape has solids (required for tessellation)
    if not hasattr(shape, 'Solids') or len(shape.Solids) == 0:
        error_msg = f"Bookshelf_With_Joints has no solids in Shape"
        App.Console.PrintError(f"[fc_adapter] {error_msg}\n")
        print(f"[fc_adapter] ERROR: {error_msg}")
        raise RuntimeError(error_msg)
    
    # Check individual solids for validity (more lenient than compound.isValid())
    invalid_solids = []
    try:
        for idx, solid in enumerate(shape.Solids):
            if solid.isNull():
                invalid_solids.append(f"Solid {idx} is null")
            elif not solid.isValid():
                # Log but don't fail - some solids might be invalid but still tessellatable
                invalid_solids.append(f"Solid {idx} failed isValid() check")
    except Exception as e:
        # If we can't check solids, that's a problem
        error_msg = f"Cannot check solids in Bookshelf_With_Joints: {e}"
        App.Console.PrintError(f"[fc_adapter] {error_msg}\n")
        print(f"[fc_adapter] ERROR: {error_msg}")
        raise RuntimeError(error_msg)
    
    if invalid_solids:
        # Warn but don't fail - try tessellation anyway
        warning_msg = f"Some solids have issues: {', '.join(invalid_solids[:3])}"
        if len(invalid_solids) > 3:
            warning_msg += f" (and {len(invalid_solids) - 3} more)"
        App.Console.PrintWarning(f"[fc_adapter] {warning_msg}\n")
        print(f"[fc_adapter] WARNING: {warning_msg}")
        print(f"[fc_adapter] Attempting tessellation anyway - will fail if tessellation fails")
    
    # Log what we found
    try:
        num_solids = len(shape.Solids)
        App.Console.PrintMessage(f"[fc_adapter] Extracting geometry from {final_obj.Name} with {num_solids} solids\n")
        print(f"[fc_adapter] Extracting from {final_obj.Name} with {num_solids} solids")
    except Exception as e:
        error_msg = f"Error checking Bookshelf_With_Joints shape: {e}"
        App.Console.PrintError(f"[fc_adapter] {error_msg}\n")
        print(f"[fc_adapter] ERROR: {error_msg}")
        raise RuntimeError(error_msg) from e
    
    try:
        # Get the bookshelf object for dimensions
        bs = doc.getObject("Bookshelf")
        if not bs:
            error_msg = "Bookshelf object not found (needed for dimensions)"
            App.Console.PrintError(f"[fc_adapter] {error_msg}\n")
            print(f"[fc_adapter] ERROR: {error_msg}")
            raise RuntimeError(error_msg)
        
        dimensions = {
            'width': float(bs.Width) if hasattr(bs, 'Width') else 0.0,
            'height': float(bs.Height) if hasattr(bs, 'Height') else 0.0,
            'depth': float(bs.Depth) if hasattr(bs, 'Depth') else 0.0,
            'thickness': float(bs.Thickness) if hasattr(bs, 'Thickness') else 0.0
        }
        
        # REQUIRED: Tessellate the shape to get mesh data - no fallback
        # This is the real test - if tessellation works, the shape is usable
        # (We've already validated the shape has solids above, so skip isValid() check)
        
        # Process each solid in the compound
        if hasattr(shape, 'Solids') and shape.Solids:
            solids = shape.Solids
        else:
            solids = [shape]
        
        print(f"[fc_adapter] Attempting to tessellate {len(solids)} solid(s)")
        App.Console.PrintMessage(f"[fc_adapter] Attempting to tessellate {len(solids)} solid(s)\n")
        
        vertices = []
        faces = []
        vertex_offset = 0
        tessellation_errors = []
        
        for idx, solid in enumerate(solids):
            solid_type = "unknown"
            try:
                solid_bb = solid.BoundBox
                bb_x = solid_bb.XLength
                bb_y = solid_bb.YLength
                bb_z = solid_bb.ZLength
                bb_min_x = solid_bb.XMin
                bb_min_z = solid_bb.ZMin
                
                W = dimensions['width']
                H = dimensions['height']
                t = dimensions['thickness']
                
                if abs(bb_x - t) < 1.0 and bb_y > 200 and bb_z > 200:
                    if bb_min_x < 1.0:
                        solid_type = "LEFT_SIDE"
                    elif bb_min_x > W - t - 1.0:
                        solid_type = "RIGHT_SIDE"
                    else:
                        solid_type = "DIVIDER"
                elif bb_z < 30 and bb_y > 200:
                    if bb_min_z < 1.0:
                        solid_type = "BOTTOM"
                    elif bb_min_z > H - t - 1.0:
                        solid_type = "TOP"
                    else:
                        solid_type = "SHELF"
                else:
                    solid_type = f"OTHER({bb_x:.0f}x{bb_y:.0f}x{bb_z:.0f})"
            except Exception:
                solid_type = "UNKNOWN"
            
            if not solid.isValid():
                warning_msg = f"Solid {idx} ({solid_type}) failed isValid() check, but attempting tessellation anyway"
                print(f"[fc_adapter] WARNING: {warning_msg}")
                App.Console.PrintWarning(f"[fc_adapter] {warning_msg}\n")
            
            try:
                print(f"[fc_adapter] Tessellating solid {idx} ({solid_type})...")
                solid_vertices, solid_faces = solid.tessellate(0.1)
            except Exception as e:
                error_msg = f"Error tessellating solid {idx}: {e}"
                print(f"[fc_adapter] ERROR: {error_msg}")
                App.Console.PrintError(f"[fc_adapter] {error_msg}\n")
                import traceback
                App.Console.PrintError(traceback.format_exc() + "\n")
                tessellation_errors.append((idx, str(e)))
                continue
            
            print(f"[fc_adapter] Solid {idx} ({solid_type}): {len(solid_vertices)} vertices, {len(solid_faces)} faces")
            App.Console.PrintMessage(
                f"[fc_adapter] Solid {idx} ({solid_type}): {len(solid_vertices)} vertices, {len(solid_faces)} faces\n"
            )
            
            if not solid_vertices:
                error_msg = f"Solid {idx} tessellation returned 0 vertices"
                print(f"[fc_adapter] ERROR: {error_msg}")
                App.Console.PrintError(f"[fc_adapter] {error_msg}\n")
                tessellation_errors.append((idx, "Zero vertices from tessellation"))
                continue
            
            for v in solid_vertices:
                vertices.append([float(v.x), float(v.z), float(v.y)])
            
            for face in solid_faces:
                if len(face) >= 3:
                    for i in range(1, len(face) - 1):
                        faces.append([
                            face[0] + vertex_offset,
                            face[i] + vertex_offset,
                            face[i + 1] + vertex_offset
                        ])
            
            vertex_offset += len(solid_vertices)
            print(f"[fc_adapter] ✓ Solid {idx} processed successfully. Total vertices so far: {len(vertices)}")
        
        print(f"[fc_adapter] Tessellation complete: {len(vertices)} vertices, {len(faces)} faces")
        App.Console.PrintMessage(
            f"[fc_adapter] Tessellation complete: {len(vertices)} vertices, {len(faces)} faces\n"
        )

        # FAIL if tessellation didn't work - no fallback
        if not vertices or len(vertices) == 0:
            error_details = []
            if tessellation_errors:
                error_details.append(f"Tessellation errors: {tessellation_errors}")
            error_details.append(f"Total solids processed: {len(solids)}")
            error_details.append(f"Valid solids: {len(solids) - len(tessellation_errors)}")
            
            error_msg = (
                f"Tessellation failed - no vertices extracted. "
                f"{'; '.join(error_details)}. "
                f"This means the geometry cannot be visualized. "
                f"Check FreeCAD console for detailed tessellation errors."
            )
            print(f"[fc_adapter] ERROR: {error_msg}")
            App.Console.PrintError(f"[fc_adapter] {error_msg}\n")
            raise RuntimeError(error_msg)
        
        if tessellation_errors:
            warning_msg = f"Some solids failed tessellation: {tessellation_errors}. Partial geometry may be incomplete."
            print(f"[fc_adapter] WARNING: {warning_msg}")
            App.Console.PrintWarning(f"[fc_adapter] {warning_msg}\n")
        
        # Return mesh data - REQUIRED, no fallback
        print(f"[fc_adapter] Returning mesh data: {len(vertices)} vertices, {len(faces)} faces")
        App.Console.PrintMessage(f"[fc_adapter] Returning mesh data: {len(vertices)} vertices, {len(faces)} faces\n")
        return {
            'panels': [],  # Always empty - no panel fallback
            'dimensions': dimensions,
            'mesh_data': {
                'vertices': vertices,
                'faces': faces
            }
        }
        
    except RuntimeError:
        # Re-raise RuntimeErrors as-is
        raise
    except Exception as e:
        error_msg = f"Unexpected error extracting geometry: {e}"
        App.Console.PrintError(f"[fc_adapter] {error_msg}\n")
        import traceback
        App.Console.PrintError(traceback.format_exc() + "\n")
        print(f"[fc_adapter] ERROR: {error_msg}")
        print(traceback.format_exc())
        raise RuntimeError(error_msg) from e
