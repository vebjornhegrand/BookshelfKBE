# model.py – improved domain model for bookshelf design

from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Dict, Any, Tuple
from math import ceil


@dataclass
class Shelf:
    """Represents a horizontal shelf at a specific height"""
    z: float  # Z position (mm), measured from bottom (z=0)
    
    def __post_init__(self):
        if self.z < 0:
            raise ValueError(f"Shelf z-position must be >= 0, got {self.z}")


@dataclass
class Divider:
    """Represents a vertical divider at a specific x-position"""
    x_center: float  # X coordinate of divider center (mm)
    
    def __post_init__(self):
        if self.x_center < 0:
            raise ValueError(f"Divider x_center must be >= 0, got {self.x_center}")


@dataclass
class Model:
    """Domain model for a bookshelf design with validation and computed properties"""
    W: float           # width (mm)
    D: float           # depth (mm)
    H: float           # height (mm)
    t: float           # material thickness (mm)
    add_top: bool      # include top panel
    shelves: List[Shelf] = field(default_factory=list)
    dividers: List[Divider] = field(default_factory=list)
    
    def __post_init__(self):
        """Validate model constraints on creation"""
        if self.W <= 0 or self.D <= 0 or self.H <= 0:
            raise ValueError(f"Dimensions must be positive: W={self.W}, D={self.D}, H={self.H}")
        if self.t < 6.0:
            raise ValueError(f"Thickness must be >= 6mm, got {self.t}")
        if self.t >= min(self.W, self.D) / 3:
            raise ValueError(f"Thickness {self.t} too large for dimensions W={self.W}, D={self.D}")
    
    @property
    def clear_width(self) -> float:
        """Usable interior width between side panels"""
        return self.W - 2 * self.t
    
    @property
    def clear_height(self) -> float:
        """Usable interior height"""
        return self.H - self.t - (self.t if self.add_top else 0.0)
    
    @property
    def num_bays(self) -> int:
        """Number of horizontal bays (dividers + 1)"""
        return len(self.dividers) + 1
    
    @property
    def bay_width(self) -> float:
        """Width of each bay"""
        return self.clear_width / self.num_bays if self.num_bays > 0 else self.clear_width
    
    @property
    def num_shelves(self) -> int:
        """Total number of shelves"""
        return len(self.shelves)
    
    @property
    def num_dividers(self) -> int:
        """Total number of dividers"""
        return len(self.dividers)
    
    def get_shelf_z_positions(self) -> List[float]:
        """Get list of shelf z-coordinates"""
        return [shelf.z for shelf in self.shelves]
    
    def get_divider_x_positions(self) -> List[float]:
        """Get list of divider x-coordinates"""
        return [div.x_center for div in self.dividers]
    
    def validate_shelf_positions(self) -> List[str]:
        """Check for invalid shelf positions"""
        warnings = []
        for i, shelf in enumerate(self.shelves):
            if shelf.z <= self.t:
                warnings.append(f"Shelf {i} at z={shelf.z:.1f}mm is at or below bottom panel (t={self.t}mm)")
            if self.add_top and shelf.z >= self.H - self.t:
                warnings.append(f"Shelf {i} at z={shelf.z:.1f}mm intersects top panel at {self.H - self.t:.1f}mm")
        return warnings
    
    def validate_divider_positions(self) -> List[str]:
        """Check for invalid divider positions"""
        warnings = []
        for i, div in enumerate(self.dividers):
            if div.x_center <= self.t or div.x_center >= self.W - self.t:
                warnings.append(f"Divider {i} at x={div.x_center:.1f}mm is outside valid range ({self.t:.1f} to {self.W - self.t:.1f}mm)")
        return warnings


# ---------- Helper Functions ----------

def _get_float(cfg: Dict[str, Any], *keys: str, default: float) -> float:
    """Extract float from config with multiple possible keys"""
    for k in keys:
        if k in cfg and cfg[k] is not None:
            try:
                return float(cfg[k])
            except (ValueError, TypeError):
                pass
    return float(default)


def _get_int(cfg: Dict[str, Any], *keys: str, default: int) -> int:
    """Extract int from config with multiple possible keys"""
    for k in keys:
        if k in cfg and cfg[k] is not None:
            try:
                return int(cfg[k])
            except (ValueError, TypeError):
                pass
    return int(default)


def _get_bool(cfg: Dict[str, Any], *keys: str, default: bool) -> bool:
    """Extract bool from config with multiple possible keys"""
    for k in keys:
        if k in cfg and cfg[k] is not None:
            v = cfg[k]
            if isinstance(v, bool):
                return v
            if isinstance(v, (int, float)):
                return bool(v)
            if isinstance(v, str):
                s = v.strip().lower()
                if s in ("true", "yes", "1"):
                    return True
                if s in ("false", "no", "0"):
                    return False
    return bool(default)


# Import unified structural calculations
from materials import calculate_load_capacity
# Note: get_material_spec was removed - use materials.get_material() instead

def _calc_dividers_for_span(span_mm: float, material: str, thickness_mm: float, 
                             target_load_kg: float) -> int:
    """
    Calculate number of dividers needed based on material strength.
    Uses proper load capacity calculation with quadratic thickness scaling.
    
    Returns:
        Number of dividers needed (0 if none needed)
    """
    if span_mm <= 0 or thickness_mm <= 0 or target_load_kg <= 0:
        return 0
    
    # Calculate capacity for the full span with current thickness
    # Use a reference depth (300mm is typical)
    reference_depth = 300.0
    capacity_full_span = calculate_load_capacity(
        bay_width_mm=span_mm,
        depth_mm=reference_depth,
        thickness_mm=thickness_mm,
        material=material
    )
    
    # If capacity is already sufficient, no dividers needed
    if capacity_full_span >= target_load_kg:
        return 0
    
    # Calculate how many bays we need
    # Each bay should have capacity >= target_load
    # Capacity scales inversely with span (shorter span = more capacity)
    # So: capacity_bay = capacity_full * (span_full / span_bay)
    # We need: capacity_bay >= target_load
    # So: capacity_full * (span_full / span_bay) >= target_load
    # Therefore: span_bay <= capacity_full * span_full / target_load
    
    if capacity_full_span <= 0:
        # If capacity is zero or negative, we need many dividers
        # Use a conservative estimate: max 400mm per bay
        max_bay_width = 400.0
    else:
        # Calculate maximum bay width that gives required capacity
        # capacity_bay = capacity_full * (span_full / span_bay)
        # target_load = capacity_full * (span_full / span_bay)
        # span_bay = capacity_full * span_full / target_load
        max_bay_width = (capacity_full_span * span_mm) / target_load_kg
        # Cap at reasonable limits
        max_bay_width = min(max_bay_width, 800.0)  # Max 800mm per bay
        max_bay_width = max(max_bay_width, 200.0)  # Min 200mm per bay
    
    # Calculate number of bays needed
    bays_needed = ceil(span_mm / max_bay_width)
    return max(0, bays_needed - 1)  # dividers = bays - 1


def _calculate_divider_positions(W: float, t: float, n_dividers: int) -> List[Divider]:
    """Calculate evenly-spaced divider positions"""
    if n_dividers <= 0:
        return []
    
    clear_width = W - 2 * t
    bay_width = clear_width / (n_dividers + 1)
    
    return [
        Divider(x_center=t + (i + 1) * bay_width)
        for i in range(n_dividers)
    ]


def _distribute_shelves_evenly(H: float, t: float, add_top: bool, 
                                num_shelves: int) -> List[Shelf]:
    """
    Distribute shelves evenly in available vertical space.
    Returns list of Shelf objects.
    """
    if num_shelves <= 0:
        return []
    
    z_min = t  # Bottom of first shelf sits on top of bottom panel
    z_max = H - (t if add_top else 0.0)  # Available height
    
    available_height = z_max - z_min
    
    # Divide space into equal sections
    spacing = available_height / (num_shelves + 1)
    
    return [
        Shelf(z=z_min + (i + 1) * spacing)
        for i in range(num_shelves)
    ]


def build_model(cfg: Dict[str, Any]) -> Model:
    """
    Build a complete Model from configuration dictionary.
    
    Features:
    - Even shelf distribution or explicit positions
    - Auto-calculate dividers based on material strength or explicit count
    - Full validation
    """
    # --- Dimensions ---
    W = _get_float(cfg, "Width", "width_mm", default=800.0)
    D = _get_float(cfg, "Depth", "depth_mm", default=300.0)
    H = _get_float(cfg, "Height", "height_mm", default=2000.0)
    t = _get_float(cfg, "Thickness", "thickness_mm", default=18.0)
    
    # Clamp to reasonable ranges
    W = max(100.0, W)
    D = max(100.0, D)
    H = max(300.0, H)
    t = max(6.0, min(t, min(W, D) / 3))
    
    add_top = _get_bool(cfg, "AddTopPanel", "add_top_panel", default=True)
    
    # --- Material properties for divider calculation ---
    material = cfg.get("material", "melamine_pb").lower()
    target_load = _get_float(cfg, "target_load_per_bay_kg", "target_load_kg", default=50.0)
    
    # --- Dividers: use explicit positions if provided, otherwise calculate ---
    divider_x_positions = cfg.get("divider_x_positions")
    if divider_x_positions and isinstance(divider_x_positions, list) and len(divider_x_positions) > 0:
        # Use explicit divider positions
        dividers = [Divider(x_center=float(x)) for x in divider_x_positions]
        n_dividers = len(dividers)
    else:
        # Calculate dividers
        n_dividers = _get_int(cfg, "Dividers", "dividers", "num_dividers", default=-1)
        if n_dividers < 0:  # Auto-calculate
            clear_width = W - 2 * t
            n_dividers = _calc_dividers_for_span(clear_width, material, t, target_load)
        
        dividers = _calculate_divider_positions(W, t, n_dividers)
    
    # --- Shelves: use explicit positions if provided, otherwise calculate ---
    shelf_z_positions = cfg.get("shelf_z_positions")
    if shelf_z_positions and isinstance(shelf_z_positions, list) and len(shelf_z_positions) > 0:
        # Use explicit shelf positions
        shelves = [Shelf(z=float(z)) for z in shelf_z_positions]
    else:
        # Calculate shelves
        num_shelves = _get_int(cfg, "num_shelves", "NumShelves", default=-1)
        
        if num_shelves < 0:  # Calculate from spacing hint
            spacing_hint = _get_float(cfg, "ShelfSpacing", "shelf_spacing_hint_mm", default=320.0)
            z_min = t
            z_max = H - (t if add_top else 0.0)
            num_shelves = max(0, int((z_max - z_min) / max(spacing_hint, 100.0)))
        
        shelves = _distribute_shelves_evenly(H, t, add_top, num_shelves)
    
    return Model(
        W=W, D=D, H=H, t=t,
        add_top=add_top,
        shelves=shelves,
        dividers=dividers
    )