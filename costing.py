# costing.py – Cost estimation module
"""
Decoupled cost estimator with no FreeCAD dependencies.
Uses materials.py for material specifications.
"""

from __future__ import annotations
from dataclasses import dataclass, asdict
from math import ceil
from typing import Dict, Any, List

# Import unified material specifications
from materials import MaterialSpec, get_material
from model import Model


@dataclass
class HardwareSpec:
    """Hardware unit costs"""
    dowel_cost: float = 0.04
    cam_set_cost: float = 0.55
    shelf_pin_cost: float = 0.06


@dataclass
class ProcessRates:
    """Machine and labor rates"""
    setup_time_min: float = 8.0
    drilling_time_per_hole_s: float = 2.5
    hourly_machine_rate: float = 45.0
    assembly_time_per_dowel_min: float = 0.2
    assembly_time_per_cam_min: float = 0.4
    hourly_labor_rate: float = 35.0


# ---------- Default Constants ----------

DEFAULT_MAT = get_material('melamine_pb')  # Use default material
DEFAULT_HW = HardwareSpec()
DEFAULT_RT = ProcessRates()


# ---------- Helper Functions ----------

def _panel_area_m2(W: float, D: float, H: float, t: float, 
                   n_shelves: int, n_dividers: int, add_top: bool) -> float:
    """
    Calculate total panel area in square meters.
    UPDATED: More accurate calculation that scales with volume.
    """
    A = 0.0
    A += 2 * (H * D)                    # sides
    A += (W * D)                        # bottom
    if add_top:
        A += (W * D)                    # top
    A += n_dividers * (H * D)           # dividers (approximate full height)
    A += n_shelves * ((W - 2*t) * D)   # shelves (approximate full width)
    return A / 1_000_000.0


def _panel_volume_m3(W: float, D: float, H: float, t: float,
                     n_shelves: int, n_dividers: int, 
                     add_top: bool, shelf_z_positions: List[float]) -> float:
    """
    Calculate total material volume in cubic meters.
    This scales cost with actual material used (volume-based pricing).
    """
    volume = 0.0
    
    # Side panels: 2 * (H * D * t)
    volume += 2 * (H * D * t)
    
    # Bottom panel: (W * D * t)
    volume += (W * D * t)
    
    # Top panel (if present): (W * D * t)
    if add_top:
        volume += (W * D * t)
    
    # Dividers: n_dividers * (H * D * t)
    volume += n_dividers * (H * D * t)
    
    # Shelves: n_shelves * (bay_width * D * t)
    # Calculate bay width (approximate)
    if n_dividers > 0:
        bay_width = (W - 2*t) / (n_dividers + 1)
    else:
        bay_width = W - 2*t
    volume += n_shelves * (bay_width * D * t)
    
    return volume / 1e9  # Convert mm³ to m³


def _sheet_count(total_area_m2: float, mat: MaterialSpec) -> int:
    """Calculate number of sheets needed"""
    sheet_area = (mat.sheet_len_mm * mat.sheet_wid_mm) / 1_000_000.0
    usable = sheet_area * (1.0 - mat.waste_factor)
    return max(1, ceil(total_area_m2 / max(usable, 1e-6)))


def _lane_count(front_off: float, back_off: float, D: float) -> int:
    """Calculate number of drilling lanes based on front/back offsets"""
    n = 0
    if front_off > 0:
        n += 1
    if back_off > 0 and abs(D - back_off - front_off) > 1e-6:
        n += 1
    return n


def _shelfpin_levels(mode: str, H: float, t: float, add_top: bool,
                     pitch: float, bottom_margin: float, top_margin: float,
                     fixed_levels: List[float]) -> List[float]:
    """Calculate shelf pin hole z-levels based on mode"""
    if mode == "fixed_at_shelves":
        return sorted(set(round(z, 3) for z in fixed_levels))
    
    if mode == "modular_grid":
        z0 = t + max(0.0, bottom_margin)
        z1 = H - (t if add_top else 0.0) - max(0.0, top_margin)
        p = max(5.0, pitch)
        out = []
        z = z0
        while z <= z1 + 1e-6:
            out.append(round(z, 3))
            z += p
        # Add fixed shelf levels to modular grid
        for zf in fixed_levels:
            out.append(round(zf, 3))
        return sorted(set(out))
    
    return []


# ---------- Main Estimation Function ----------

def estimate(model: Model,
             material: MaterialSpec = None,
             hardware: HardwareSpec = DEFAULT_HW,
             rates: ProcessRates = DEFAULT_RT,
             method: str = "camlock_dowels",
             shelf_pins_mode: str = "modular_grid",
             row_front_offset: float = 37.0,
             row_back_offset: float = 37.0,
             grid_pitch_z: float = 32.0,
             grid_bottom_margin: float = 64.0,
             grid_top_margin: float = 96.0) -> Dict[str, Any]:
    """
    Estimate cost directly from a domain Model (no FreeCAD dependencies).
    
    Args:
        model: Domain Model with all design parameters
        material: Material specifications (optional, will use default)
        hardware: Hardware costs
        rates: Process rates
        method: Joint method ("glue_dowels" or "camlock_dowels")
        shelf_pins_mode: Shelf pin layout mode
        row_front_offset, row_back_offset, grid_*: drilling pattern parameters
        
    Returns:
        Dictionary with detailed cost breakdown
    """
    # Get material spec if not provided
    if material is None:
        material = get_material('melamine_pb')
    
    W = model.W
    D = model.D
    H = model.H
    t = model.t
    add_top = model.add_top
    shelf_z_positions = model.get_shelf_z_positions()
    n_shelves = len(shelf_z_positions)
    n_dividers = len(model.dividers)
    sp_mode = shelf_pins_mode
    
    # 1) Material cost (volume-based for better scaling)
    # Calculate both area (for sheet count) and volume (for material cost scaling)
    area_m2 = _panel_area_m2(W, D, H, t, n_shelves, n_dividers, add_top)
    sheets = _sheet_count(area_m2, material)
    
    material_cost = sheets * material.price_per_sheet
    
    # 2) Joints & holes
    lanes_edge = _lane_count(row_front_offset, row_back_offset, D)
    lanes_div = lanes_edge
    
    # Carcass holes (bottom/top to sides)
    holes_carcass = 4 * lanes_edge * (1 + (1 if add_top else 0))
    
    # Divider holes (dividers to bottom/top)
    holes_div = n_dividers * 4 * lanes_div * (1 + (1 if add_top else 0))
    
    if method == "glue_dowels":
        dowel_holes = holes_carcass + holes_div
        cam_sets = 0
    else:  # camlock_dowels
        # Carcass uses cam-locks, dividers use dowels
        cam_sets = lanes_edge * (1 + (1 if add_top else 0)) * 2  # L/R per lane
        dowel_holes = holes_div  # dividers remain dowels
    
    # 3) Shelf pins
    z_list = _shelfpin_levels(sp_mode, H, t, add_top, 
                             grid_pitch_z, grid_bottom_margin, 
                             grid_top_margin, shelf_z_positions)
    
    lanes_sp = _lane_count(row_front_offset, row_back_offset, D)
    sp_holes_sides = len(z_list) * lanes_sp * 2  # 2 sides
    sp_holes_divs = len(z_list) * lanes_sp * (n_dividers * 2)  # both faces per divider
    sp_holes_total = sp_holes_sides + sp_holes_divs
    
    # 4) Machine time (drilling only)
    drill_holes_total = dowel_holes + sp_holes_total
    drill_min = (drill_holes_total * rates.drilling_time_per_hole_s) / 60.0
    machine_min = rates.setup_time_min + drill_min
    machine_cost = (machine_min / 60.0) * rates.hourly_machine_rate
    
    # 5) Hardware + assembly
    dowel_count = max(0, dowel_holes // 2)  # two blind holes per dowel
    shelf_pin_count_est = max(0, min(n_shelves * 4, sp_holes_total)) if sp_holes_total > 0 else 0
    
    hardware_cost = (
        dowel_count * hardware.dowel_cost +
        cam_sets * hardware.cam_set_cost +
        shelf_pin_count_est * hardware.shelf_pin_cost
    )
    
    assembly_min = (
        dowel_count * rates.assembly_time_per_dowel_min +
        cam_sets * rates.assembly_time_per_cam_min
    )
    assembly_cost = (assembly_min / 60.0) * rates.hourly_labor_rate
    
    total = material_cost + machine_cost + hardware_cost + assembly_cost
    
    return {
        "inputs": {
            "W": W, "D": D, "H": H, "t": t, "add_top": add_top,
            "n_shelves": n_shelves, "n_dividers": n_dividers,
            "method": method, "shelf_pins_mode": sp_mode
        },
        "materials": asdict(material),
        "hardware": asdict(hardware),
        "rates": asdict(rates),
        "panel_area_m2": round(area_m2, 3),
        "sheet_count": sheets,
        "counts": {
            "dowel_holes": int(dowel_holes),
            "cam_sets": int(cam_sets),
            "shelfpin_holes": int(sp_holes_total),
            "shelf_pins_est": int(shelf_pin_count_est),
            "drill_holes_total": int(drill_holes_total),
        },
        "time_min": {
            "setup": rates.setup_time_min,
            "drilling": round(drill_min, 1),
            "machine_total": round(machine_min, 1),
            "assembly": round(assembly_min, 1),
        },
        "cost": {
            "material": round(material_cost, 2),
            "machine": round(machine_cost, 2),
            "hardware": round(hardware_cost, 2),
            "assembly": round(assembly_cost, 2),
            "total": round(total, 2),
        },
    }





def print_breakdown(res: Dict[str, Any]) -> None:
    """Print cost breakdown in readable format"""
    c = res["cost"]
    t = res["time_min"]
    n = res["counts"]
    
    print(f"""
==== COST ESTIMATE ====
Material:     ${c['material']:8.2f}  ({res['sheet_count']} sheets)
Machine:      ${c['machine']:8.2f}  (setup {t['setup']:.1f} min + drill {t['drilling']:.1f} min)
Hardware:     ${c['hardware']:8.2f}  (dowels ~{n['dowel_holes']//2}, cams {n['cam_sets']}, pins ~{n['shelf_pins_est']})
Assembly:     ${c['assembly']:8.2f}  ({t['assembly']:.1f} min)

TOTAL:        ${c['total']:8.2f}

Panel area: {res['panel_area_m2']:.2f} m² | Drill holes: {n['drill_holes_total']}
""")