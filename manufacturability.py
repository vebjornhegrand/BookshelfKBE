# manufacturability.py – Manufacturability analysis module
"""
Analyzes designs for manufacturability constraints and warnings.
Uses materials.py for structural calculations.
"""

from typing import List, Dict, Any
from materials import calculate_load_capacity


# ---------- Constants ----------

# Material density (kg/m³)
MATERIAL_DENSITY = {
    'solid_wood': 600,
    'plywood': 550,
    'mdf': 750,
    'melamine_pb': 680,
}

# Standard limits
MAX_PANEL_WEIGHT_KG = 25.0
MAX_ASSEMBLY_WEIGHT_KG = 50.0
MAX_ASSEMBLY_WEIGHT_EQUIPMENT_KG = 100.0
STANDARD_SHIPPING_LENGTH = 2400.0
STANDARD_SHIPPING_WIDTH = 1200.0
STANDARD_SHIPPING_HEIGHT = 600.0
STANDARD_SHEET_LENGTH = 2440.0
STANDARD_SHEET_WIDTH = 1220.0


# ---------- Individual Check Functions ----------

def check_panel_size_limits(W: float, D: float, H: float, t: float, 
                            n_shelves: int, n_dividers: int, 
                            add_top: bool) -> List[str]:
    """
    Warning 11: Panel Size vs Sheet Size
    Check if any panel exceeds standard sheet dimensions
    """
    warnings = []
    
    # Side panels (H × D)
    if H > STANDARD_SHEET_LENGTH:
        warnings.append(
            f"Side panel height {H:.0f}mm exceeds standard sheet length {STANDARD_SHEET_LENGTH:.0f}mm → "
            f"requires splicing or special order material"
        )
    
    if D > STANDARD_SHEET_WIDTH:
        warnings.append(
            f"Panel depth {D:.0f}mm exceeds standard sheet width {STANDARD_SHEET_WIDTH:.0f}mm → "
            f"requires splicing or special order material"
        )
    
    # Horizontal panels
    if W > STANDARD_SHEET_LENGTH:
        warnings.append(
            f"Bookshelf width {W:.0f}mm exceeds standard sheet length {STANDARD_SHEET_LENGTH:.0f}mm → "
            f"bottom/top panels require splicing"
        )
    
    # Dividers
    if n_dividers > 0:
        divider_height = H - t - (t if add_top else 0.0)
        if divider_height > STANDARD_SHEET_LENGTH:
            warnings.append(
                f"Divider height {divider_height:.0f}mm exceeds standard sheet length {STANDARD_SHEET_LENGTH:.0f}mm → "
                f"dividers require splicing"
            )
    
    return warnings


def calculate_weight(W: float, D: float, H: float, t: float,
                    n_shelves: int, n_dividers: int, add_top: bool,
                    material: str) -> Dict[str, float]:
    """
    Calculate component and total weights
    
    Returns:
        Dictionary with panel weights and totals
    """
    density = MATERIAL_DENSITY.get(material.lower(), 650)
    
    def panel_weight(length_mm, width_mm, thick_mm):
        """Calculate weight of a panel"""
        volume_m3 = (length_mm * width_mm * thick_mm) / 1_000_000_000.0
        return volume_m3 * density
    
    weights = {}
    
    # Side panels
    side_weight = panel_weight(D, H, t)
    weights['side_panel'] = side_weight
    weights['sides_total'] = 2 * side_weight
    
    # Bottom panel
    bottom_weight = panel_weight(W - 2*t, D, t)
    weights['bottom_panel'] = bottom_weight
    
    # Top panel
    if add_top:
        top_weight = panel_weight(W - 2*t, D, t)
        weights['top_panel'] = top_weight
    else:
        weights['top_panel'] = 0.0
    
    # Shelves (per bay)
    if n_dividers > 0:
        bay_width = (W - 2*t) / (n_dividers + 1)
        shelf_weight = panel_weight(bay_width, D, t)
    else:
        shelf_weight = panel_weight(W - 2*t, D, t)
    
    weights['shelf_panel'] = shelf_weight
    weights['shelves_total'] = n_shelves * shelf_weight * (n_dividers + 1)
    
    # Dividers
    if n_dividers > 0:
        divider_height = H - t - (t if add_top else 0.0)
        divider_weight = panel_weight(t, D, divider_height)
        weights['divider_panel'] = divider_weight
        weights['dividers_total'] = n_dividers * divider_weight
    else:
        weights['divider_panel'] = 0.0
        weights['dividers_total'] = 0.0
    
    # Hardware
    weights['hardware'] = 0.5  # kg (approximate)
    
    # Total
    weights['total'] = (
        weights['sides_total'] +
        weights['bottom_panel'] +
        weights['top_panel'] +
        weights['shelves_total'] +
        weights['dividers_total'] +
        weights['hardware']
    )
    
    # Heaviest single panel
    weights['heaviest_panel'] = max(
        side_weight,
        bottom_weight,
        weights['top_panel'],
        shelf_weight if n_shelves > 0 else 0,
        weights['divider_panel']
    )
    
    return weights


def check_weight_limits(weights: Dict[str, float]) -> List[str]:
    """
    Warning 17: Weight
    Check if weights exceed handling/assembly limits
    """
    warnings = []
    
    heaviest = weights['heaviest_panel']
    total = weights['total']
    
    # Single panel handling
    if heaviest > MAX_PANEL_WEIGHT_KG:
        warnings.append(
            f"Heaviest panel weighs {heaviest:.1f}kg (exceeds {MAX_PANEL_WEIGHT_KG:.0f}kg single-person limit) → "
            f"requires two people to handle individual panels"
        )
    
    # Assembly weight
    if total > MAX_ASSEMBLY_WEIGHT_EQUIPMENT_KG:
        warnings.append(
            f"Total assembly weight {total:.1f}kg (exceeds {MAX_ASSEMBLY_WEIGHT_EQUIPMENT_KG:.0f}kg) → "
            f"requires lifting equipment or mechanical assistance"
        )
    elif total > MAX_ASSEMBLY_WEIGHT_KG:
        warnings.append(
            f"Total assembly weight {total:.1f}kg (exceeds {MAX_ASSEMBLY_WEIGHT_KG:.0f}kg single-person limit) → "
            f"requires two people for assembly"
        )
    
    return warnings


def check_shipping_dimensions(W: float, D: float, H: float) -> List[str]:
    """
    Warning 18: Shipping Dimensions
    Check if assembled dimensions exceed standard shipping limits
    """
    warnings = []
    
    over_limit = []
    if W > STANDARD_SHIPPING_LENGTH:
        over_limit.append(f"width {W:.0f}mm > {STANDARD_SHIPPING_LENGTH:.0f}mm")
    if D > STANDARD_SHIPPING_WIDTH:
        over_limit.append(f"depth {D:.0f}mm > {STANDARD_SHIPPING_WIDTH:.0f}mm")
    if H > STANDARD_SHIPPING_HEIGHT:
        over_limit.append(f"height {H:.0f}mm > {STANDARD_SHIPPING_HEIGHT:.0f}mm")
    
    if over_limit:
        warnings.append(
            f"Assembled dimensions exceed standard shipping limits ({', '.join(over_limit)}) → "
            f"requires freight shipping, cannot ship via standard parcel carriers"
        )
    
    return warnings


def check_over_engineering(W: float, D: float, H: float, t: float,
                          n_dividers: int, material: str, 
                          target_load_kg: float, cost: Dict[str, float]) -> List[str]:
    """
    Warning 21: Over-Engineering
    Check if design is over-engineered relative to load requirements
    Uses the SAME calculation as GA optimizer for consistency.
    """
    warnings = []
    
    clear_width = W - 2 * t
    num_bays = n_dividers + 1
    bay_width = clear_width / num_bays
    
    # Use unified calculation from materials module
    estimated_capacity = calculate_load_capacity(
        bay_width_mm=bay_width,
        depth_mm=D,
        thickness_mm=t,
        material=material
    )
    
    # Check over-engineering
    over_engineering_factor = estimated_capacity / max(target_load_kg, 10.0)
    
    if over_engineering_factor > 3.0:
        # Calculate recommended thickness using quadratic relationship
        # From capacity ∝ thickness², we get: t_new = t_old * sqrt(target/capacity)
        recommended_thickness = t * (target_load_kg / estimated_capacity) ** 0.5
        recommended_thickness = max(12.0, round(recommended_thickness))
        
        volume_reduction = 1.0 - (recommended_thickness / t)
        potential_savings = cost.get('material', 0) * volume_reduction
        
        warnings.append(
            f"Design is over-engineered: estimated capacity {estimated_capacity:.0f}kg/bay is "
            f"{over_engineering_factor:.1f}× target load {target_load_kg:.0f}kg/bay → "
            f"consider reducing thickness from {t:.0f}mm to ~{recommended_thickness:.0f}mm "
            f"to save ~${potential_savings:.2f} in material costs"
        )
    
    # Check bay width
    if n_dividers > 0 and bay_width < 400:
        warnings.append(
            f"Bay width {bay_width:.0f}mm is quite narrow with {n_dividers} dividers → "
            f"consider reducing dividers to save material and hardware costs "
            f"(estimated savings: ~${cost.get('material', 0) * 0.15:.2f})"
        )
    
    return warnings


# ---------- Main Analysis Function ----------

def analyze(data: Dict[str, Any], cost: Dict[str, float]) -> List[str]:
    """
    Generate all manufacturability warnings for a design.
    Works with plain data structures (no FreeCAD dependencies).
    
    Args:
        data: Dictionary with design parameters
            Required keys: W, D, H, t, add_top, n_shelves, n_dividers
            Optional keys: material, target_load_kg
        cost: Cost breakdown dictionary from costing.estimate()
        
    Returns:
        List of warning strings
    """
    warnings = []
    
    # Extract parameters with defaults
    W = data.get('W', 800.0)
    D = data.get('D', 300.0)
    H = data.get('H', 2000.0)
    t = data.get('t', 18.0)
    add_top = data.get('add_top', True)
    n_shelves = data.get('n_shelves', 0)
    n_dividers = data.get('n_dividers', 0)
    material = data.get('material', 'melamine_pb')
    target_load = data.get('target_load_kg', 50.0)
    
    # Run all checks
    warnings.extend(check_panel_size_limits(W, D, H, t, n_shelves, n_dividers, add_top))
    
    weights = calculate_weight(W, D, H, t, n_shelves, n_dividers, add_top, material)
    warnings.extend(check_weight_limits(weights))
    
    warnings.extend(check_shipping_dimensions(W, D, H))
    
    warnings.extend(check_over_engineering(W, D, H, t, n_dividers, material, target_load, cost))
    
    return warnings


def generate_all_warnings(inputs: Dict[str, Any], cost: Dict[str, float]) -> List[str]:
    """
    Legacy function for backward compatibility.
    Alias for analyze().
    """
    return analyze(inputs, cost)