# materials.py - Unified material properties and structural calculations
"""
Centralized module for material specifications and structural engineering formulas.
All structural calculations (deflection, stress, load capacity) are defined here.
"""

from dataclasses import dataclass
from typing import Dict


@dataclass
class MaterialSpec:
    """Complete material specification including structural and cost properties"""
    name: str
    # Sheet dimensions and pricing
    sheet_len_mm: float = 2440.0
    sheet_wid_mm: float = 1220.0
    thickness_mm: float = 18.0
    price_per_sheet: float = 48.0
    waste_factor: float = 0.12
    # Structural properties
    E: float = 3.0e9  # Young's modulus (Pa) - stiffness
    sigma_max: float = 15e6  # Maximum allowable stress (Pa) - yield strength
    density: float = 680  # kg/m³
    deflection_limit_ratio: float = 1/250  # L/250 for shelves


# Unified material database
MATERIALS: Dict[str, MaterialSpec] = {
    'melamine_pb': MaterialSpec(
        name="Melamine Particleboard",
        sheet_len_mm=2440.0,
        sheet_wid_mm=1220.0,
        thickness_mm=18.0,
        price_per_sheet=30.0,  # Updated: realistic 2024-2025 market price
        waste_factor=0.12,
        E=3.0e9,  # Pa - relatively low stiffness
        sigma_max=15e6,  # Pa - 15 MPa (realistic for particleboard)
        density=680,  # kg/m³
        deflection_limit_ratio=1/250
    ),
    'plywood': MaterialSpec(
        name="Plywood",
        sheet_len_mm=2440.0,
        sheet_wid_mm=1220.0,
        thickness_mm=18.0,
        price_per_sheet=42.0,  # Updated: cabinet-grade plywood market price
        waste_factor=0.12,
        E=8.0e9,  # Pa - higher stiffness
        sigma_max=30e6,  # Pa - 30 MPa (stronger than particleboard)
        density=600,  # kg/m³
        deflection_limit_ratio=1/250
    ),
    'mdf': MaterialSpec(
        name="MDF",
        sheet_len_mm=2440.0,
        sheet_wid_mm=1220.0,
        thickness_mm=18.0,
        price_per_sheet=26.0,  # Updated: realistic MDF market price
        waste_factor=0.12,
        E=3.5e9,  # Pa
        sigma_max=18e6,  # Pa - slightly stronger than particleboard
        density=750,  # kg/m³ - heavier
        deflection_limit_ratio=1/250
    ),
    'solid_wood': MaterialSpec(
        name="Solid Wood",
        sheet_len_mm=2440.0,
        sheet_wid_mm=1220.0,
        thickness_mm=18.0,
        price_per_sheet=60.0,  # Updated: edge-glued panel market price
        waste_factor=0.15,
        E=10.0e9,  # Pa - much stiffer
        sigma_max=40e6,  # Pa - strongest
        density=600,  # kg/m³
        deflection_limit_ratio=1/250
    )
}


def get_material(material_name: str) -> MaterialSpec:
    """Get material specification by name (case-insensitive)"""
    return MATERIALS.get(material_name.lower(), MATERIALS['melamine_pb'])


# ============================================================================
# STRUCTURAL ENGINEERING CALCULATIONS
# ============================================================================

def calculate_shelf_deflection(bay_width_mm: float, depth_mm: float, 
                               thickness_mm: float, load_kg: float,
                               material: str) -> float:
    """
    Calculate maximum deflection of a simply supported shelf under uniform load.
    
    Formula: δ = (5 * w * L⁴) / (384 * E * I)
    where:
        δ = maximum deflection (mm)
        w = distributed load (N/m)
        L = span length (m)
        E = Young's modulus (Pa)
        I = moment of inertia (m⁴)
    
    Returns:
        Maximum deflection in mm
    """
    if bay_width_mm <= 0 or depth_mm <= 0 or thickness_mm <= 0 or load_kg < 0:
        return 1e6  # Very high deflection for invalid inputs
    
    mat = get_material(material)
    
    L = bay_width_mm / 1000.0  # meters
    b = depth_mm / 1000.0  # meters (shelf depth)
    h = thickness_mm / 1000.0  # meters (shelf thickness)
    
    # Moment of inertia for rectangular cross-section
    I = (b * h**3) / 12.0  # m⁴
    
    # Distributed load: w = (load * g) / L
    w = (load_kg * 9.81) / L  # N/m
    
    # Maximum deflection
    delta = (5.0 * w * L**4) / (384.0 * mat.E * I)  # meters
    delta_mm = delta * 1000.0  # Convert to mm
    
    return min(delta_mm, 1000.0)  # Cap at 1000mm


def calculate_shelf_stress(bay_width_mm: float, depth_mm: float,
                           thickness_mm: float, load_kg: float,
                           material: str) -> float:
    """
    Calculate maximum bending stress in a simply supported shelf.
    
    Formula: σ = M * c / I
    where:
        σ = bending stress (Pa)
        M = maximum moment (N⋅m) = w * L² / 8
        c = distance from neutral axis to outer fiber (m)
        I = moment of inertia (m⁴)
    
    Returns:
        Maximum stress in Pa
    """
    if bay_width_mm <= 0 or depth_mm <= 0 or thickness_mm <= 0 or load_kg < 0:
        return 1e9  # Very high stress for invalid inputs
    
    L = bay_width_mm / 1000.0  # meters
    b = depth_mm / 1000.0  # meters
    h = thickness_mm / 1000.0  # meters
    
    # Moment of inertia
    I = (b * h**3) / 12.0  # m⁴
    
    # Distributed load
    w = (load_kg * 9.81) / L  # N/m
    
    # Maximum moment for simply supported beam with uniform load
    M = (w * L**2) / 8.0  # N⋅m
    
    # Distance from neutral axis to outer fiber
    c = h / 2.0  # meters
    
    # Bending stress
    sigma = (M * c) / I  # Pa
    
    return min(sigma, 1e9)  # Cap at 1 GPa


def calculate_load_capacity(bay_width_mm: float, depth_mm: float,
                            thickness_mm: float, material: str) -> float:
    """
    Calculate maximum load capacity of a shelf based on stress limit.
    
    From σ = M * c / I and M = w * L² / 8:
        σ_max = (w_max * L² / 8) * (h/2) / I
        w_max = (8 * σ_max * I) / (L² * h/2)
        load_max = (w_max * L) / g
    
    Returns:
        Maximum load capacity in kg
    """
    if bay_width_mm <= 0 or depth_mm <= 0 or thickness_mm <= 0:
        return 0.0
    
    mat = get_material(material)
    
    L = bay_width_mm / 1000.0  # meters
    b = depth_mm / 1000.0  # meters
    h = thickness_mm / 1000.0  # meters
    
    # Moment of inertia
    I = (b * h**3) / 12.0  # m⁴
    
    # Distance from neutral axis
    c = h / 2.0  # meters
    
    # Maximum moment from stress limit
    M_max = (mat.sigma_max * I) / c  # N⋅m
    
    # Maximum distributed load
    w_max = (8.0 * M_max) / (L**2)  # N/m
    
    # Convert to total load
    load_max_kg = (w_max * L) / 9.81  # kg
    
    return max(0.0, min(load_max_kg, 1000.0))  # Cap at 1000 kg

