# web_app.py - Enhanced Flask web application with KB integration and 3D visualization

from flask import Flask, render_template, request, jsonify, send_file
from flask_cors import CORS
import json
import uuid
import os
import sys
import tempfile
from datetime import datetime
import logging
import platform
import time
from typing import List, Dict, Any

# Setup logging first
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import all our modules
from model import build_model
from kb_manager import FusekiKBManager, KBDesign, KBComponent, initialize_kb_with_samples
from ga_optimizer import GeneticOptimizer, GAConfig
from costing import estimate
from materials import get_material

# Try to import FreeCAD modules (optional)
FREECAD_AVAILABLE = False
FREECAD_APP = None
FREECAD_LAST_ERROR = "FreeCAD not yet loaded"
make_bookshelf = None
run_joints = None
extract_geometry_for_threejs = None


def try_load_freecad(force: bool = False) -> bool:
    """Attempt to load FreeCAD and fc_adapter modules."""
    global FREECAD_AVAILABLE, make_bookshelf, run_joints, extract_geometry_for_threejs
    if FREECAD_AVAILABLE and not force:
        return True
    
    def _attempt_paths(paths):
        for path in paths:
            if not os.path.exists(path):
                continue
            if path not in sys.path:
                sys.path.insert(0, path)
            try:
                import FreeCAD as App  # noqa: F401
                from fc_adapter import make_bookshelf as mk_bs, run_joints as rj, extract_geometry_for_threejs as eg
                globals()['FREECAD_APP'] = App
                globals()['make_bookshelf'] = mk_bs
                globals()['run_joints'] = rj
                globals()['extract_geometry_for_threejs'] = eg
                globals()['FREECAD_AVAILABLE'] = True
                globals()['FREECAD_LAST_ERROR'] = "Loaded successfully"
                logger.info(f"FreeCAD loaded from {path}")
                return True
            except (ImportError, Exception) as e:
                globals()['FREECAD_LAST_ERROR'] = f"Failed from {path}: {e}"
                logger.debug(f"FreeCAD import failed from {path}: {e}")
        return False
    
    try:
        if platform.system() == 'Darwin':
            mac_paths = [
                '/Applications/FreeCAD.app/Contents/Resources/lib',
                '/Applications/FreeCAD.app/Contents/lib',
                '/opt/homebrew/lib/freecad/lib',
                '/usr/local/lib/freecad/lib'
            ]
            if _attempt_paths(mac_paths):
                return True
        linux_paths = ['/usr/lib/freecad-python3/lib']
        if _attempt_paths(linux_paths):
            return True
    except Exception as e:
        logger.warning(f"FreeCAD load attempt failed: {e}")
        FREECAD_AVAILABLE = False
        globals()['FREECAD_LAST_ERROR'] = str(e)
        return False
    
    FREECAD_AVAILABLE = False
    globals()['FREECAD_LAST_ERROR'] = "No valid FreeCAD installation found"
    logger.warning("FreeCAD not available - 3D visualization will not work. FreeCAD is required.")
    return False


# Attempt to load FreeCAD once at startup
try_load_freecad()

app = Flask(__name__)
CORS(app)

# Initialize Knowledge Base
kb_manager = None
try:
    kb_manager = initialize_kb_with_samples()
    if kb_manager:
        logger.info("Knowledge Base initialized successfully")
except Exception as e:
    logger.warning(f"Could not initialize KB: {e}")


def build_component_requests_from_model(model,
                                        material: str) -> List[Dict[str, Any]]:
    """Derive component requests (panels, shelves, dividers) from a Model."""
    requests: List[Dict[str, Any]] = []
    thickness = model.t
    depth = model.D

    # Side panels (2)
    requests.append({
        "component_type": "side_panel",
        "width": thickness,
        "height": model.H,
        "depth": depth,
        "thickness": thickness,
        "material": material,
        "quantity": 2,
        "description": "Side Panel",
        "joint_pattern": "camlock_grid",
        "tolerance_mm": 3.0
    })

    # Bottom panel (always required)
    requests.append({
        "component_type": "top_bottom_panel",
        "width": model.W,
        "height": thickness,
        "depth": depth,
        "thickness": thickness,
        "material": material,
        "quantity": 1,
        "description": "Bottom Panel",
        "joint_pattern": "camlock_grid"
    })

    # Top panel
    if model.add_top:
        requests.append({
            "component_type": "top_bottom_panel",
            "width": model.W,
            "height": thickness,
            "depth": depth,
            "thickness": thickness,
            "material": material,
            "quantity": 1,
            "description": "Top Panel",
            "joint_pattern": "camlock_grid"
        })

    # Shelves
    shelf_count = len(model.shelves)
    if shelf_count > 0:
        requests.append({
            "component_type": "shelf_board",
            "width": max(model.clear_width, 1),
            "height": thickness,
            "depth": depth,
            "thickness": thickness,
            "material": material,
            "quantity": shelf_count,
            "description": "Adjustable Shelf",
            "joint_pattern": "shelf_pin_grid",
            "tolerance_mm": 5.0
        })

    # Dividers
    divider_count = len(model.dividers)
    if divider_count > 0:
        requests.append({
            "component_type": "divider",
            "width": thickness,
            "height": model.H,
            "depth": depth,
            "thickness": thickness,
            "material": material,
            "quantity": divider_count,
            "description": "Vertical Divider",
            "joint_pattern": "camlock_grid",
            "tolerance_mm": 3.0
        })

    return requests


@app.route('/')
def index():
    """Main configurator page"""
    return render_template('configurator.html')


@app.route('/api/search_designs', methods=['POST'])
def search_designs():
    """Search for similar designs in KB"""
    if not kb_manager:
        return jsonify({'error': 'Knowledge Base not available'}), 503
    
    data = request.json
    width = float(data.get('width', 800))
    height = float(data.get('height', 2000))
    depth = float(data.get('depth', 300))
    tolerance = float(data.get('tolerance', 0.15))
    
    designs = kb_manager.search_similar_designs(width, height, depth, tolerance)
    
    return jsonify({
        'success': True,
        'designs': designs,
        'count': len(designs)
    })


@app.route('/api/optimize_design', methods=['POST'])
def optimize_design():
    """
    Optimize design using Genetic Algorithm with fixed customer dimensions.
    First checks KB for existing designs, then uses GA to generate/optimize if needed.
    """
    requirements = request.json
    
    # Extract customer-specified dimensions
    customer_dims = {}
    
    if 'width' in requirements:
        customer_dims['width'] = requirements['width']
    elif 'min_width' in requirements and 'max_width' in requirements:
        customer_dims['width'] = (requirements['min_width'] + requirements['max_width']) / 2
    else:
        customer_dims['width'] = 800
    
    if 'height' in requirements:
        customer_dims['height'] = requirements['height']
    elif 'min_height' in requirements and 'max_height' in requirements:
        customer_dims['height'] = (requirements['min_height'] + requirements['max_height']) / 2
    else:
        customer_dims['height'] = 1800
    
    if 'depth' in requirements:
        customer_dims['depth'] = requirements['depth']
    elif 'min_depth' in requirements and 'max_depth' in requirements:
        customer_dims['depth'] = (requirements['min_depth'] + requirements['max_depth']) / 2
    else:
        customer_dims['depth'] = 300
    
    if 'num_shelves' in requirements:
        customer_dims['num_shelves'] = requirements['num_shelves']
    elif 'min_shelves' in requirements and 'max_shelves' in requirements:
        customer_dims['num_shelves'] = (requirements['min_shelves'] + requirements['max_shelves']) // 2
    else:
        customer_dims['num_shelves'] = 4
    
    customer_dims['add_top'] = requirements.get('add_top', True)
    requirements.update(customer_dims)
    
    # STEP 1: Check KB for existing similar designs (as per assignment requirement)
    kb_seed_designs = []
    if kb_manager:
        try:
            similar_designs = kb_manager.search_similar_designs(
                customer_dims['width'],
                customer_dims['height'],
                customer_dims['depth'],
                tolerance=0.15  # 15% tolerance
            )
            kb_seed_designs = similar_designs[:5]  # Use top 5 for seeding
            logger.info(f"Found {len(kb_seed_designs)} similar designs in KB for seeding")
        except Exception as e:
            logger.warning(f"KB search failed: {e}, proceeding with GA only")
    
    # STEP 2: Configure GA with better exploration parameters
    config = GAConfig(
        population_size=30,  # Larger population for more diversity
        generations=15,  # More generations for better optimization
        mutation_rate=0.30,  # Higher mutation rate for exploration
        crossover_rate=0.8,  # Higher crossover rate
        elite_count=3  # Keep more elite solutions (note: simplified GA uses elite_count, not elite_size)
    )
    
    # STEP 3: Run optimization with KB seeding
    optimizer = GeneticOptimizer(config)
    optimized_model = optimizer.optimize(requirements, kb_seed_designs=kb_seed_designs)
    report = optimizer.get_optimization_report()
    
    # Calculate cost for optimized design
    # Use user's joint preferences from requirements
    joint_method = requirements.get('joint_method', 'camlock_dowels')
    shelf_pins_mode = requirements.get('shelf_pins_mode', 'modular_grid')
    material_name = requirements.get('material', 'melamine_pb')
    
    cost_breakdown = estimate(
        optimized_model,
        material=get_material(material_name),
        method=joint_method,
        shelf_pins_mode=shelf_pins_mode
    )

    # STEP 4: Determine component availability / missing components
    component_plan = {
        'kb_available': kb_manager is not None,
        'reused': [],
        'missing': []
    }
    component_ids_for_design: List[str] = []
    new_components_created: List[str] = []

    if kb_manager:
        component_requests = build_component_requests_from_model(
            optimized_model,
            requirements.get('material', 'melamine_pb')
        )
        allocations = kb_manager.allocate_components(component_requests)
        for alloc in allocations:
            if alloc['status'] == 'reused':
                component_plan['reused'].append(alloc)
            else:
                component_plan['missing'].append(alloc)
                pending_component = KBComponent(
                    component_id=alloc['component_id'],
                    component_type=alloc['component_type'],
                    width=alloc['width'],
                    height=alloc['height'],
                    depth=alloc['depth'],
                    thickness=alloc['thickness'],
                    material=alloc['material'],
                    joint_pattern=alloc.get('joint_pattern') or joint_method,
                    stock_quantity=0,
                    status="pending_fabrication"
                )
                new_components_created.append(pending_component.component_id)
                kb_manager.store_component(pending_component)
            component_ids_for_design.append(alloc['component_id'])
    else:
        component_plan['note'] = 'Knowledge Base unavailable – component availability skipped'
    
    # Store in KB if available
    design_id = f"GA-{uuid.uuid4().hex[:8]}"
    if kb_manager:
        kb_design = KBDesign(
            design_id=design_id,
            width=optimized_model.W,
            height=optimized_model.H,
            depth=optimized_model.D,
            thickness=optimized_model.t,
            add_top=optimized_model.add_top,
            material=requirements.get('material', 'melamine_pb'),
            shelf_positions=optimized_model.get_shelf_z_positions(),
            divider_positions=optimized_model.get_divider_x_positions(),
            total_cost=cost_breakdown['cost']['total'],
            max_load=requirements.get('target_load', 50.0),
            generated_by="GA_OPTIMIZED",
            created_date=datetime.now().isoformat(),
            components_used=component_ids_for_design
        )
        kb_manager.store_design(kb_design)
    
    # Convert to JSON-serializable format
    design_data = {
        'design_id': design_id,
        'width': optimized_model.W,
        'height': optimized_model.H,
        'depth': optimized_model.D,
        'thickness': optimized_model.t,
        'add_top': optimized_model.add_top,
        'shelves': optimized_model.get_shelf_z_positions(),
        'dividers': optimized_model.get_divider_x_positions(),
        'cost': cost_breakdown['cost']['total'],
        'optimization_report': report,
        'component_plan': component_plan
    }
    
    return jsonify({
        'success': True,
        'design': design_data,
        'cost_breakdown': cost_breakdown,
        'component_plan': component_plan,
        'new_components_created': new_components_created
    })


@app.route('/api/generate_3d_data', methods=['POST'])
def generate_3d_data():
    """Generate 3D geometry data for Three.js visualization using FreeCAD"""
    global FREECAD_AVAILABLE
    if not FREECAD_AVAILABLE:
        reloaded = try_load_freecad(force=True)
        if reloaded:
            logger.info("FreeCAD reloaded successfully after retry")
    if not FREECAD_AVAILABLE or not make_bookshelf or not run_joints:
        return jsonify({
            'success': False,
            'error': 'FreeCAD is not available. Please ensure FreeCAD is installed and accessible.',
            'detail': FREECAD_LAST_ERROR,
            'geometry': None
        }), 503
    
    data = request.json
    
    # Build model from configuration
    model = build_model(data)
    
    # Use FreeCAD (required - no fallback)
    try:
        # Create a new FreeCAD document for this request
        doc_name = f"Bookshelf_{uuid.uuid4().hex[:8]}"
        doc = App.newDocument(doc_name)
        
        # Create bookshelf geometry in FreeCAD
        bs = make_bookshelf(model)
        
        # Ensure bookshelf has a valid shape before joints
        doc.recompute()
        if not hasattr(bs, 'Shape') or bs.Shape.isNull():
            logger.warning("Bookshelf shape is null, forcing recompute")
            bs.recompute()
            doc.recompute()
        
        # Verify shape exists and has Proxy (required for joints)
        if not hasattr(bs, 'Shape') or bs.Shape.isNull():
            raise RuntimeError("Bookshelf shape is still null after recompute")
        
        if not hasattr(bs, 'Proxy'):
            raise RuntimeError("Bookshelf does not have Proxy (not a FeaturePython object)")
        
        num_solids = len(bs.Shape.Solids) if hasattr(bs.Shape, 'Solids') else 0
        logger.info(f"Bookshelf created: {bs.Name}, {num_solids} solids, has Proxy: {hasattr(bs, 'Proxy')}")
        
        # Configure and run joints (this will cut holes)
        try:
            joints = run_joints(bs)
            if not joints:
                logger.error("Failed to create joints object - run_joints returned None")
                # Try to get FreeCAD console messages
                try:
                    console_msgs = App.Console.GetStatus("Log", "Msg")
                    console_errors = App.Console.GetStatus("Log", "Err")
                    if console_errors:
                        logger.error(f"FreeCAD Console Errors: {console_errors}")
                    if console_msgs:
                        logger.info(f"FreeCAD Console Messages: {console_msgs}")
                except:
                    pass
                raise RuntimeError("Joints object not created")
        except Exception as e:
            logger.error(f"Exception while creating joints object: {e}")
            import traceback
            logger.error(traceback.format_exc())
            raise RuntimeError(f"Joints object creation failed: {e}")
        
        # Configure joints to ALWAYS perform cuts (required for assignment)
        joints.PerformCuts = True
        
        # Get joint method from user input (default to camlock_dowels)
        joint_method = data.get('joint_method', 'camlock_dowels')
        if joint_method not in ['glue_dowels', 'camlock_dowels']:
            joint_method = 'camlock_dowels'  # Default if invalid
        joints.Method = joint_method
        
        # Get shelf pins mode from user input (default to modular_grid)
        shelf_pins_mode = data.get('shelf_pins_mode', 'modular_grid')
        if shelf_pins_mode not in ['none', 'fixed_at_shelves', 'modular_grid']:
            shelf_pins_mode = 'modular_grid'  # Default if invalid
        joints.ShelfPinsMode = shelf_pins_mode
        
        joints.RefineResult = True  # Enable result refinement
        
        # Log the configuration
        logger.info(f"Joints configuration: PerformCuts=True, Method={joint_method}, ShelfPinsMode={shelf_pins_mode}")
        
        # Keep joints in the same document (don't create new document)
        if hasattr(joints, 'CreateNewDocument'):
            joints.CreateNewDocument = False
            logger.info("Set CreateNewDocument to False")
        
        # Ensure BookshelfName is set (joints.execute() uses this)
        if hasattr(joints, 'BookshelfName'):
            joints.BookshelfName = bs.Name
            logger.info(f"Set BookshelfName to '{bs.Name}'")
        
        # Verify bookshelf can be found by name
        test_bs = doc.getObject(bs.Name)
        if not test_bs:
            raise RuntimeError(f"Cannot find bookshelf '{bs.Name}' in document")
        if not hasattr(test_bs, 'Proxy'):
            raise RuntimeError(f"Bookshelf '{bs.Name}' does not have Proxy")
        
        # Ensure ActiveDocument is set correctly BEFORE executing joints
        App.setActiveDocument(doc_name)
        current_doc = App.ActiveDocument
        if current_doc.Name != doc_name:
            raise RuntimeError(f"ActiveDocument mismatch: expected {doc_name}, got {current_doc.Name}")
        
        logger.info(f"ActiveDocument set to: {App.ActiveDocument.Name}")
        
        # Force execution - joints.execute() needs to be called explicitly
        if hasattr(joints, 'Proxy') and hasattr(joints.Proxy, 'execute'):
            try:
                logger.info("Executing joints to create Bookshelf_With_Joints...")
                logger.info(f"  BookshelfName: '{joints.BookshelfName}'")
                logger.info(f"  PerformCuts: {joints.PerformCuts}")
                logger.info(f"  Method: {joints.Method}")
                logger.info(f"  ShelfPinsMode: {joints.ShelfPinsMode}")
                logger.info(f"  CreateNewDocument: {getattr(joints, 'CreateNewDocument', 'N/A')}")
                logger.info(f"  RefineResult: {getattr(joints, 'RefineResult', 'N/A')}")
                
                # Verify bookshelf exists and has shape before executing
                test_bs = doc.getObject(joints.BookshelfName)
                if not test_bs:
                    raise RuntimeError(f"Bookshelf '{joints.BookshelfName}' not found in document")
                if not hasattr(test_bs, 'Shape') or test_bs.Shape.isNull():
                    logger.warning("Bookshelf shape is null, forcing recompute before joints")
                    test_bs.recompute()
                    doc.recompute()
                    time.sleep(0.2)
                
                # Ensure all properties are set before execution
                joints.touch()  # Mark object as modified
                doc.recompute()
                
                # Execute joints - this creates Bookshelf_With_Joints
                logger.info("Calling joints.Proxy.execute()...")
                joints.Proxy.execute(joints)
                
                # Recompute after execution
                doc.recompute()
                
                # Check if Bookshelf_With_Joints was created
                final_obj = doc.getObject("Bookshelf_With_Joints")
                if final_obj:
                    if hasattr(final_obj, 'Shape') and not final_obj.Shape.isNull():
                        num_solids = len(final_obj.Shape.Solids) if hasattr(final_obj.Shape, 'Solids') else 0
                        logger.info(f"✓ Bookshelf_With_Joints created successfully with {num_solids} solids")
                    else:
                        logger.warning("Bookshelf_With_Joints exists but has no shape")
                else:
                    logger.error("Bookshelf_With_Joints was NOT created after execute()")
                    logger.error("Available objects in document:")
                    for obj in doc.Objects:
                        logger.error(f"  - {obj.Name} (Type: {obj.TypeId})")

                    # Check again
                    final_obj = doc.getObject("Bookshelf_With_Joints")
                    if not final_obj:
                        logger.warning("Available objects in document:")
                        for obj in doc.Objects:
                            logger.warning(f"  - {obj.Name} (Type: {obj.TypeId})")
                            if hasattr(obj, 'Shape') and not obj.Shape.isNull():
                                try:
                                    num_solids = len(obj.Shape.Solids) if hasattr(obj.Shape, 'Solids') else 0
                                    logger.warning(f"    Shape has {num_solids} solids")
                                except:
                                    logger.warning(f"    Shape exists but cannot count solids")
            except Exception as e:
                logger.error(f"Error during joints execution: {e}")
                import traceback
                logger.error(traceback.format_exc())
        else:
            logger.error("Joints object does not have Proxy.execute method")
            raise RuntimeError("Joints Proxy not properly initialized")
        
        # Extract geometry from FreeCAD (includes joints/holes)
        try:
            geometry_data = extract_geometry_for_threejs(doc)
        except RuntimeError as e:
            error_msg = f"Geometry extraction failed: {str(e)}"
            logger.error(error_msg)
            App.closeDocument(doc_name)
            return jsonify({
                'success': False,
                'error': error_msg,
                'geometry': None
            }), 500
        
        # Verify we have mesh data (required)
        has_mesh = (geometry_data.get('mesh_data') and 
                   geometry_data.get('mesh_data').get('vertices') and 
                   len(geometry_data.get('mesh_data').get('vertices')) > 0)
        
        if not has_mesh:
            error_msg = "Geometry extraction returned no mesh data. Bookshelf_With_Joints tessellation failed."
            logger.error(error_msg)
            App.closeDocument(doc_name)
            return jsonify({
                'success': False,
                'error': error_msg,
                'geometry': None
            }), 500
        
        num_vertices = len(geometry_data.get('mesh_data').get('vertices'))
        num_faces = len(geometry_data.get('mesh_data').get('faces'))
        logger.info(f"✓ Extracted geometry successfully: {num_vertices} vertices, {num_faces} faces")
        
        # Verify Bookshelf_With_Joints was used
        final_obj = doc.getObject("Bookshelf_With_Joints")
        if final_obj and hasattr(final_obj, 'Shape') and not final_obj.Shape.isNull():
            logger.info(f"✓ Using Bookshelf_With_Joints for geometry extraction (with joints)")
            if hasattr(final_obj.Shape, 'Solids'):
                logger.info(f"  Shape has {len(final_obj.Shape.Solids)} solids")
        else:
            # This should not happen if extract_geometry_for_threejs worked, but check anyway
            error_msg = "Bookshelf_With_Joints not found after extraction - this should not happen"
            logger.error(error_msg)
            App.closeDocument(doc_name)
            return jsonify({
                'success': False,
                'error': error_msg,
                'geometry': None
            }), 500
        
        # Clean up the temporary document
        App.closeDocument(doc_name)
        
        return jsonify({
            'success': True,
            'geometry': geometry_data,
            'source': 'freecad'
        })
        
    except Exception as e:
        logger.error(f"FreeCAD geometry generation failed: {e}")
        import traceback
        logger.error(traceback.format_exc())
        # No fallback - FreeCAD is required
        return jsonify({
            'success': False,
            'error': f'FreeCAD geometry generation failed: {str(e)}. FreeCAD is required for 3D visualization.',
            'geometry': None
        }), 500


@app.route('/api/workflow_status')
def workflow_status():
    """Get system status and available features"""
    status = {
        'kb_available': kb_manager is not None,
        'freecad_available': FREECAD_AVAILABLE,
        'ga_available': True,
        'features': []
    }
    
    if kb_manager:
        status['features'].append('Knowledge Base Search')
        status['features'].append('Design Storage')
        status['features'].append('Order Tracking')
        status['features'].append('Component Inventory')
    
    if FREECAD_AVAILABLE:
        status['features'].append('CAD Export')
    
    status['features'].extend([
        'Genetic Algorithm Optimization',
        '3D Visualization',
        'Cost Estimation',
        'Manufacturability Analysis'
    ])
    
    return jsonify(status)


@app.route('/api/record_order', methods=['POST'])
def record_order():
    """Record a customer order"""
    if not kb_manager:
        return jsonify({'error': 'Knowledge Base not available'}), 503
    
    data = request.json
    customer_name = data.get('customer_name')
    design_id = data.get('design_id')
    quantity = int(data.get('quantity', 1))
    
    if not customer_name or not design_id:
        return jsonify({'error': 'Missing customer_name or design_id'}), 400
    
    try:
        customer_id = kb_manager.record_order(customer_name, design_id, quantity)
        return jsonify({
            'success': True,
            'customer_id': customer_id,
            'design_id': design_id,
            'quantity': quantity
        })
    except Exception as e:
        logger.error(f"Error recording order: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/get_design/<design_id>')
def get_design(design_id):
    """Get design details by ID"""
    if not kb_manager:
        return jsonify({'error': 'Knowledge Base not available'}), 503
    
    try:
        design = kb_manager.get_design_details(design_id)
        if not design:
            return jsonify({'error': 'Design not found'}), 404
        
        # Convert KBDesign to dict
        design_data = {
            'design_id': design.design_id,
            'width': design.width,
            'height': design.height,
            'depth': design.depth,
            'thickness': design.thickness,
            'add_top': design.add_top,
            'shelves': design.shelf_positions,
            'dividers': design.divider_positions,
            'cost': design.total_cost,
            'material': design.material,
            'max_load': design.max_load,
            'generated_by': design.generated_by,
            'popularity': design.popularity_score
        }
        
        return jsonify({
            'success': True,
            'design': design_data
        })
    except Exception as e:
        logger.error(f"Error getting design: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/popular_designs')
def popular_designs():
    """Get most popular designs"""
    if not kb_manager:
        return jsonify({'error': 'Knowledge Base not available'}), 503
    
    try:
        limit = int(request.args.get('limit', 5))
        designs = kb_manager.get_popular_designs(limit)
        
        return jsonify({
            'success': True,
            'designs': designs
        })
    except Exception as e:
        logger.error(f"Error getting popular designs: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/components')
def component_inventory():
    """List available components from the KB inventory."""
    if not kb_manager:
        return jsonify({'error': 'Knowledge Base not available'}), 503
    
    try:
        component_type = request.args.get('type')
        components = kb_manager.list_components(component_type)
        return jsonify({
            'success': True,
            'components': components
        })
    except Exception as e:
        logger.error(f"Error listing components: {e}")
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    app.run(debug=True, port=5001)
