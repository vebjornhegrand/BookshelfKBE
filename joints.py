# bs_freecad/joints.py
# Phase-2: blind-dowel joinery (and optional cam-locks) for the outer carcass.
#
# - X-axis blind dowels along side↔bottom and side↔top edges.
# - Z-axis blind dowels at bottom↔dividers and top↔dividers interfaces.
# - Holes are BLIND (half dowel length in each part) drilled from INSIDE faces.
# - Warn if blind depth risks going through the material.
# - Robust booleans: overshoot, per-solid bbox-filtered, fused tools, refined results.

from __future__ import annotations
from typing import List
import FreeCAD as App
import Part

# Try to import FreeCADGui (optional - may not be available in headless mode)
try:
    import FreeCADGui as Gui
    GUI_AVAILABLE = True
except (ImportError, AttributeError):
    Gui = None
    GUI_AVAILABLE = False

def _clamp(v, lo, hi): return max(lo, min(hi, v))

class JointsFP:
    def __init__(self, obj):
        obj.Proxy = self

        # Source bookshelf (Phase-1 FeaturePython)
        obj.addProperty("App::PropertyString", "BookshelfName", "Source",
                        "Name of the Bookshelf FP object to reference").BookshelfName = ""

        # Method: carcass joinery
        obj.addProperty("App::PropertyEnumeration", "Method", "Jointing",
                        "Fastening method for the outer carcass")
        obj.Method = ["glue_dowels", "camlock_dowels"]
        obj.Method = "glue_dowels"

        # Output behaviour
        obj.addProperty("App::PropertyBool", "CreateNewDocument", "Output",
                        "Clone parts into a new document").CreateNewDocument = True
        obj.addProperty("App::PropertyBool", "PerformCuts", "Output",
                        "Cut holes into parts (if False, keep guide solids only)").PerformCuts = True
        obj.addProperty("App::PropertyInteger", "Transparency", "Display",
                        "Guide solids transparency").Transparency = 70
        obj.addProperty("App::PropertyBool", "RefineResult", "Output",
                        "Post-refine resulting solids to clean splitters").RefineResult = True

        # ------------ Dowel params (blind; half per part) ------------
        obj.addProperty("App::PropertyFloat", "DowelDiameter", "Dowels",
                        "Dowel diameter (mm)").DowelDiameter = 8.0
        obj.addProperty("App::PropertyFloat", "DowelLength", "Dowels",
                        "Total dowel length (mm)").DowelLength = 30.0
        obj.addProperty("App::PropertyFloat", "MinThicknessDowels", "Validation",
                        "Minimum recommended thickness for dowels (mm)").MinThicknessDowels = 12.0
        obj.addProperty("App::PropertyFloat", "DepthClearance", "Validation",
                        "Safety margin to avoid through holes (mm)").DepthClearance = 0.5

        # ------------ Rows (Y-pattern) for carcass & dividers --------
        obj.addProperty("App::PropertyFloat", "EdgeFrontOffset", "CarcassRows",
                        "Front row center offset from front face (mm)").EdgeFrontOffset = 37.0
        obj.addProperty("App::PropertyFloat", "EdgeBackOffset", "CarcassRows",
                        "Back row center offset from back face (mm)").EdgeBackOffset = 37.0
        obj.addProperty("App::PropertyFloat", "EdgePitchY", "CarcassRows",
                        "Pitch along depth for carcass rows (mm)").EdgePitchY = 128.0

        obj.addProperty("App::PropertyFloat", "DivFrontOffset", "DividerRows",
                        "Front row offset for divider joints (mm)").DivFrontOffset = 37.0
        obj.addProperty("App::PropertyFloat", "DivBackOffset", "DividerRows",
                        "Back row offset for divider joints (mm)").DivBackOffset = 37.0
        obj.addProperty("App::PropertyFloat", "DivPitchY", "DividerRows",
                        "Pitch along depth for divider joints (mm)").DivPitchY = 128.0

        # ------------ Cam-lock specifics (outer carcass) -------------
        obj.addProperty("App::PropertyFloat", "CamBoltDiameter", "CamLock",
                        "Cam bolt hole diameter (mm)").CamBoltDiameter = 7.0
        obj.addProperty("App::PropertyFloat", "CamPocketDiameter", "CamLock",
                        "Cam pocket diameter (mm)").CamPocketDiameter = 15.0
        obj.addProperty("App::PropertyFloat", "CamPocketDepth", "CamLock",
                        "Cam pocket depth (mm)").CamPocketDepth = 12.0
        obj.addProperty("App::PropertyFloat", "CamPocketOffsetX", "CamLock",
                        "Pocket center offset from side inside face (mm)").CamPocketOffsetX = 19.0
        obj.addProperty("App::PropertyFloat", "CamBoltDeltaY", "CamLock",
                        "Bolt lane offset from the dowel lane (mm)").CamBoltDeltaY = 16.0
                # ------------ Shelf pin holes -------------
        obj.addProperty("App::PropertyEnumeration", "ShelfPinsMode", "ShelfPins",
                        "How to drill shelf pin holes")
        obj.ShelfPinsMode = ["none", "fixed_at_shelves", "modular_grid"]
        obj.ShelfPinsMode = "none"

        obj.addProperty("App::PropertyFloat", "ShelfPinDiameter", "ShelfPins",
                        "Pin hole diameter (mm)").ShelfPinDiameter = 5.0
        obj.addProperty("App::PropertyFloat", "ShelfPinDepth", "ShelfPins",
                        "Blind hole depth from inside face (mm)").ShelfPinDepth = 12.0
        obj.addProperty("App::PropertyBool", "ShelfPinsOnDividers", "ShelfPins",
                        "Also drill pin holes into vertical dividers").ShelfPinsOnDividers = True

        # Row layout on Y (front/back lanes)
        obj.addProperty("App::PropertyFloat", "RowFrontOffset", "ShelfPins",
                        "Front row center offset from front face (mm)").RowFrontOffset = 37.0
        obj.addProperty("App::PropertyFloat", "RowBackOffset", "ShelfPins",
                        "Back row center offset from back face (mm)").RowBackOffset = 37.0

        # Modular grid parameters (Z direction)
        obj.addProperty("App::PropertyFloat", "GridPitchZ", "ShelfPins",
                        "Vertical pitch for modular holes (mm)").GridPitchZ = 32.0
        obj.addProperty("App::PropertyFloat", "GridBottomMargin", "ShelfPins",
                        "No holes within this distance above the bottom inside (mm)").GridBottomMargin = 64.0
        obj.addProperty("App::PropertyFloat", "GridTopMargin", "ShelfPins",
                        "No holes within this distance below the underside of top (mm)").GridTopMargin = 96.0

        # Read-only outputs
        for p in ["Warnings", "GuideCount", "CutCount"]:
            obj.addProperty("App::PropertyString", p, "Computed", p)
            obj.setEditorMode(p, 1)

    # ------------------------------------------
    def execute(self, obj):
        doc = App.ActiveDocument
        if not doc:
            return

        # Source
        bs = doc.getObject(obj.BookshelfName) if obj.BookshelfName else None
        if not bs or not hasattr(bs, "Proxy"):
            App.Console.PrintError("[Joints] Set 'BookshelfName' to your Bookshelf FP object.\n")
            return

        # Read geometry
        try:
            H = float(bs.Height); W = float(bs.Width); D = float(bs.Depth)
            t = float(bs.Thickness)
            num_bays = int(getattr(bs, "NumBays", 1))
            bay_w = float(getattr(bs, "BayWidth", max(1.0, W - 2.0 * t)))
            add_top = bool(getattr(bs, "AddTopPanel", True))
        except Exception as e:
            App.Console.PrintError(f"[Joints] Could not read bookshelf parameters: {e}\n")
            return

        method = str(obj.Method)
        warnings = []
        if t < obj.MinThicknessDowels:
            warnings.append(f"Material thickness {t:.1f} mm < recommended {obj.MinThicknessDowels:.1f} mm for dowels.")

        # Blind depth (half dowel length) + safety
        total_len = max(5.0, float(obj.DowelLength))
        blind_depth = 0.5 * total_len
        clr = max(0.0, float(obj.DepthClearance))
        if blind_depth + clr >= t:
            warnings.append(
                f"Dowel blind depth {blind_depth:.1f} + clearance {clr:.1f} ≥ thickness {t:.1f} → risk of through holes."
            )

        # Target doc & clone
        target_doc = doc
        if bool(obj.CreateNewDocument):
            target_doc = App.newDocument("Bookshelf_Joinery")
            if GUI_AVAILABLE and Gui:
                try:
                    Gui.ActiveDocument = Gui.getDocument(target_doc.Name)
                except Exception:
                    pass

        if not hasattr(bs, "Shape") or bs.Shape.isNull():
            App.Console.PrintError("[Joints] Source bookshelf has no shape. Recompute it first.\n")
            return

        clone = target_doc.addObject("Part::Feature", "BookshelfClone")
        clone.Shape = bs.Shape.copy()

        # ---------- helpers ----------
        def y_rows(front_off, back_off, pitch_y):
            front = _clamp(float(front_off), 0.0, D)
            backC = _clamp(float(back_off), 0.0, D)
            y_max = D - backC
            ys, y = [], front
            step = max(1.0, float(pitch_y))
            while y <= y_max + 1e-6:
                ys.append(y)
                y += step
            return ys

        EPS = 1e-3  # nudge inward to avoid plane z-fighting

        # Blind cylinders that start on the mating plane (inside faces)
        def cyl_x_from_plane(x_plane, y, z, dia, depth, sign):
            r = 0.5 * float(dia); L = float(depth)
            if sign > 0:
                base = App.Vector(x_plane + EPS, y, z); dirv = App.Vector(1, 0, 0)
            else:
                base = App.Vector(x_plane - EPS, y, z); dirv = App.Vector(-1, 0, 0)
            return Part.makeCylinder(r, L, base, dirv)

        def cyl_z_from_plane(x, y, z_plane, dia, depth, sign):
            r = 0.5 * float(dia); L = float(depth)
            if sign > 0:
                base = App.Vector(x, y, z_plane + EPS); dirv = App.Vector(0, 0, 1)
            else:
                base = App.Vector(x, y, z_plane - EPS); dirv = App.Vector(0, 0, -1)
            return Part.makeCylinder(r, L, base, dirv)

        # Through hole from OUTSIDE face of the side panel toward the joint (bolt)
        def cyl_x_from_outside(x_outside, y, z, dia, length, sign):
            r = 0.5 * float(dia); L = float(length)
            if sign > 0:  # left side: +X
                base = App.Vector(x_outside + EPS, y, z); dirv = App.Vector(1, 0, 0)
            else:        # right side: -X
                base = App.Vector(x_outside - EPS, y, z); dirv = App.Vector(-1, 0, 0)
            return Part.makeCylinder(r, L, base, dirv)

        # Cam pocket along Z into top/bottom where the bolt tip lands
        def pocket_z(x, y, z_plane, dia, depth, up):
            r = 0.5 * float(dia)
            d = min(float(depth), t - 1.0)
            if up:   # drill +Z from inside plane
                base = App.Vector(x, y, z_plane + EPS); dirv = App.Vector(0, 0, 1)
            else:    # drill -Z from inside plane
                base = App.Vector(x, y, z_plane - EPS); dirv = App.Vector(0, 0, -1)
            return Part.makeCylinder(r, d, base, dirv)

        # Carcass planes (inside faces)
        x_left_inside   = t
        x_right_inside  = W - t
        x_left_outside  = 0.0
        x_right_outside = W
        z_bottom_top = t              # inside top of bottom
        z_bottom_mid = 0.5 * t
        z_top_under = H - t if add_top else None
        z_top_mid   = H - 0.5 * t if add_top else None

        # Divider X centers (divider panel centers)
        divider_xc = []
        # Try DividerXPositions (FloatList) first (new format)
        if hasattr(bs, "DividerXPositions") and bs.DividerXPositions:
            try:
                divider_xc = [float(x) for x in bs.DividerXPositions]
            except Exception:
                pass
        
        # Fallback: try DividerCenters (string) for legacy compatibility
        if not divider_xc and hasattr(bs, "DividerCenters") and bs.DividerCenters:
            try:
                divider_xc = [float(x.strip()) for x in bs.DividerCenters.split(",")]
            except Exception:
                pass
        
        # Fallback: calculate from bays
        if not divider_xc and num_bays > 1:
            clear_width = W - 2*t
            bay_w_calc = clear_width / num_bays
            for i in range(1, num_bays):
                x_center = t + i * bay_w_calc
                divider_xc.append(x_center)

        guides: List[Part.Shape] = []

        # Slight overshoot to make booleans robust (only when we cut)
        CUT_OVERSHOOT = 0.2  # mm
        hole_depth = blind_depth + (CUT_OVERSHOOT if bool(obj.PerformCuts) else 0.0)

        # ----------------- 1) Carcass: common blind dowels -----------------
        ys_edge = y_rows(obj.EdgeFrontOffset, obj.EdgeBackOffset, obj.EdgePitchY)
        for y in ys_edge:
            # bottom joint
            guides.append(cyl_x_from_plane(x_left_inside,  y, z_bottom_mid, obj.DowelDiameter, hole_depth, sign=-1))  # into left SIDE
            guides.append(cyl_x_from_plane(x_left_inside,  y, z_bottom_mid, obj.DowelDiameter, hole_depth, sign=+1))  # into BOTTOM
            guides.append(cyl_x_from_plane(x_right_inside, y, z_bottom_mid, obj.DowelDiameter, hole_depth, sign=+1))  # into right SIDE
            guides.append(cyl_x_from_plane(x_right_inside, y, z_bottom_mid, obj.DowelDiameter, hole_depth, sign=-1))  # into BOTTOM

            # top joint
            if z_top_mid is not None:
                guides.append(cyl_x_from_plane(x_left_inside,  y, z_top_mid, obj.DowelDiameter, hole_depth, sign=-1))  # into left SIDE
                guides.append(cyl_x_from_plane(x_left_inside,  y, z_top_mid, obj.DowelDiameter, hole_depth, sign=+1))  # into TOP
                guides.append(cyl_x_from_plane(x_right_inside, y, z_top_mid, obj.DowelDiameter, hole_depth, sign=+1))  # into right SIDE
                guides.append(cyl_x_from_plane(x_right_inside, y, z_top_mid, obj.DowelDiameter, hole_depth, sign=-1))  # into TOP

        # ----------------- 2) Carcass: optional cam-locks -----------------
        if method == "camlock_dowels":
            bolt_d  = float(obj.CamBoltDiameter)
            cam_d   = float(obj.CamPocketDiameter)
            cam_dep = float(obj.CamPocketDepth)
            cam_offX = float(obj.CamPocketOffsetX)
            lane_dy  = float(obj.CamBoltDeltaY)

            # Pocket X centers measured from the side panel's INSIDE face into top/bottom
            x_cam_left  = x_left_inside  + cam_offX
            x_cam_right = x_right_inside - cam_offX

            for y in ys_edge:
                y_bolt = y + lane_dy

                # bottom joint — bolts from outside toward pocket centers
                L_bolt_left  = max(5.0, x_cam_left  - x_left_outside)
                L_bolt_right = max(5.0, x_right_outside - x_cam_right)
                guides.append(cyl_x_from_outside(x_left_outside,  y_bolt, z_bottom_mid, bolt_d, L_bolt_left,  sign=+1))
                guides.append(cyl_x_from_outside(x_right_outside, y_bolt, z_bottom_mid, bolt_d, L_bolt_right, sign=-1))
                # pockets into bottom panel (drill -Z from inside plane)
                guides.append(pocket_z(x_cam_left,  y_bolt, z_bottom_top, cam_d, cam_dep, up=False))
                guides.append(pocket_z(x_cam_right, y_bolt, z_bottom_top, cam_d, cam_dep, up=False))

                # top joint (if present)
                if z_top_mid is not None and z_top_under is not None:
                    L_bolt_left  = max(5.0, x_cam_left  - x_left_outside)
                    L_bolt_right = max(5.0, x_right_outside - x_cam_right)
                    guides.append(cyl_x_from_outside(x_left_outside,  y_bolt, z_top_mid, bolt_d, L_bolt_left,  sign=+1))
                    guides.append(cyl_x_from_outside(x_right_outside, y_bolt, z_top_mid, bolt_d, L_bolt_right, sign=-1))
                    # pockets into top panel (drill +Z from inside plane)
                    guides.append(pocket_z(x_cam_left,  y_bolt, z_top_under, cam_d, cam_dep, up=True))
                    guides.append(pocket_z(x_cam_right, y_bolt, z_top_under, cam_d, cam_dep, up=True))

        # ----------------- 3) Divider: Z-axis blind dowels -----------------
        ys_div = y_rows(obj.DivFrontOffset, obj.DivBackOffset, obj.DivPitchY)
        for xc in divider_xc:
            for y in ys_div:
                guides.append(cyl_z_from_plane(xc, y, z_bottom_top, obj.DowelDiameter, hole_depth, sign=-1))  # into BOTTOM
                guides.append(cyl_z_from_plane(xc, y, z_bottom_top, obj.DowelDiameter, hole_depth, sign=+1))  # into DIVIDER
                if z_top_under is not None:
                    guides.append(cyl_z_from_plane(xc, y, z_top_under, obj.DowelDiameter, hole_depth, sign=+1))  # into TOP
                    guides.append(cyl_z_from_plane(xc, y, z_top_under, obj.DowelDiameter, hole_depth, sign=-1))  # into DIVIDER
                # ----------------- 4) Shelf pin holes (optional) -----------------
        sp_mode = str(getattr(obj, "ShelfPinsMode", "none"))
        if sp_mode != "none":
            # Validity / safety checks
            pin_d   = max(1.0, float(obj.ShelfPinDiameter))
            pin_dep = max(1.0, float(obj.ShelfPinDepth))
            if pin_dep + clr >= t:
                warnings.append(
                    f"Shelf pin blind depth {pin_dep:.1f} + clearance {clr:.1f} ≥ thickness {t:.1f} → risk of through holes."
                )

            # Helper: shelf Z levels
            def _shelf_z_levels():
                zs = []

                # Try ShelfZPositions (FloatList) first (new format)
                if hasattr(bs, "ShelfZPositions") and bs.ShelfZPositions:
                    try:
                        for z in bs.ShelfZPositions:
                            z_val = float(z)
                            # Skip bottom shelf at z=0
                            if abs(z_val) < 1e-6:
                                continue
                            # Skip explicit top plate if present
                            if add_top and abs(z_val - (H - t)) < 1e-6:
                                continue
                            zs.append(z_val)
                    except Exception:
                        pass

                # Fallback: try domain result held by the Bookshelf FP (adapter stores it on the Proxy)
                if not zs:
                    try:
                        if hasattr(bs, "Proxy") and hasattr(bs.Proxy, "_result"):
                            res = bs.Proxy._result
                            if hasattr(res, "shelves") and res.shelves:
                                for s in res.shelves:
                                    z = float(getattr(s, "z", getattr(s, "position_z", None)))
                                    if z is None:
                                        continue
                                    # Skip bottom shelf at z=0
                                    if abs(z) < 1e-6:
                                        continue
                                    # Skip explicit top plate if present
                                    if add_top and abs(z - (H - t)) < 1e-6:
                                        continue
                                    zs.append(z)
                    except Exception:
                        pass

                # Fallback: make a single mid shelf if nothing came through
                if not zs:
                    z_min = t
                    z_max = H - (t if add_top else 0.0)
                    if z_max - z_min > 40.0:
                        zs = [z_min + 0.5 * (z_max - z_min)]
                # Normalize & dedupe
                return sorted({round(z, 3) for z in zs})

            # Helper: two Y lanes (front/back) for shelf pins
            def _pin_rows_y():
                ys = []
                f = float(obj.RowFrontOffset)
                b = float(obj.RowBackOffset)
                if f > 0.0: ys.append(f)
                if b > 0.0 and abs(D - b - f) > 1e-6: ys.append(D - b)
                return ys

            pin_hole_depth = pin_dep + (CUT_OVERSHOOT if bool(obj.PerformCuts) else 0.0)

            # Decide Z positions according to mode
            z_list = []
            if sp_mode == "fixed_at_shelves":
                # Pin centers at the shelf *bottom* z (domain shelves are created with z = bottom of shelf)
                z_list = _shelf_z_levels()
            elif sp_mode == "modular_grid":
                z0 = t + max(0.0, float(obj.GridBottomMargin))
                z1 = H - (t if add_top else 0.0) - max(0.0, float(obj.GridTopMargin))
                pitch = max(5.0, float(obj.GridPitchZ))
                # Simple start-from-bottom stepping
                z = z0
                while z <= z1 + 1e-6:
                    z_list.append(z)
                    z += pitch
                # If domain had fixed shelves, make sure *those* levels appear too (for customer choice)
                for zf in _shelf_z_levels():
                    z_list.append(zf)
                z_list = sorted({round(z, 3) for z in z_list})

            if z_list:
                ys_pin = _pin_rows_y()

                # Sides: drill from inside faces (+X for left, -X for right)
                for y in ys_pin:
                    for z in z_list:
                        guides.append(cyl_x_from_plane(x_left_inside,  y, z, pin_d, pin_hole_depth, sign=-1))  # into left SIDE
                        guides.append(cyl_x_from_plane(x_right_inside, y, z, pin_d, pin_hole_depth, sign=+1))  # into right SIDE

                # Optional: also into vertical dividers
                if bool(getattr(obj, "ShelfPinsOnDividers", True)) and divider_xc:
                    for y in ys_pin:
                        for xc in divider_xc:
                            for z in z_list:
                                # Drill from both divider faces toward the core to keep them blind from each face
                                guides.append(cyl_x_from_plane(xc - 0.5 * t, y, z, pin_d, pin_hole_depth, sign=+1))
                                guides.append(cyl_x_from_plane(xc + 0.5 * t, y, z, pin_d, pin_hole_depth, sign=-1))
        # ---- collect guides as a single feature for visualization ----
        guide_count = len(guides)
        cut_count = 0
        guide_feat = None
        if guide_count:
            guide_feat = target_doc.addObject("Part::Feature", "JointGuides")
            guide_feat.Shape = Part.Compound(guides)
            try:
                guide_feat.ViewObject.ShapeColor = (0.2, 0.6, 1.0)
                guide_feat.ViewObject.Transparency = int(obj.Transparency)
            except Exception:
                pass

        # ---- robust cutting: per-solid with bbox tool filtering & fused tools ----
        if bool(obj.PerformCuts) and guide_count:
            try:
                base_solids = list(clone.Shape.Solids)
                if not base_solids:
                    raise ValueError("Clone has no solids to cut.")

                # Precompute guide bounding boxes
                g_bbs = [g.BoundBox for g in guides]

                def grow(bb, m=0.5):
                    bb2 = App.BoundBox(bb)
                    bb2.XMin -= m; bb2.YMin -= m; bb2.ZMin -= m
                    bb2.XMax += m; bb2.YMax += m; bb2.ZMax += m
                    return bb2

                result_shapes = []
                print(f"[Joints] Processing {len(base_solids)} solids for cutting")
                App.Console.PrintMessage(f"[Joints] Processing {len(base_solids)} solids for cutting\n")
                
                # Track statistics
                uncut_count = 0
                cut_success_count = 0
                cut_failed_count = 0
                lost_solids = []
                
                for idx, solid in enumerate(base_solids):
                    # Identify solid type based on bounding box
                    solid_type = "unknown"
                    try:
                        solid_bb = solid.BoundBox
                        bb_x = solid_bb.XLength
                        bb_y = solid_bb.YLength
                        bb_z = solid_bb.ZLength
                        bb_min_x = solid_bb.XMin
                        bb_min_z = solid_bb.ZMin
                        
                        # Classify based on dimensions and position
                        if abs(bb_x - t) < 1.0 and bb_y > 200 and bb_z > 200:
                            # Thin panel, tall and deep = side panel or divider
                            if bb_min_x < 1.0:
                                solid_type = "LEFT_SIDE"
                            elif bb_min_x > W - t - 1.0:
                                solid_type = "RIGHT_SIDE"
                            else:
                                solid_type = "DIVIDER"
                        elif bb_z < 30 and bb_y > 200:
                            # Thin in Z, wide in Y = shelf or top/bottom
                            if bb_min_z < 1.0:
                                solid_type = "BOTTOM"
                            elif bb_min_z > H - t - 1.0:
                                solid_type = "TOP"
                            else:
                                solid_type = "SHELF"
                        else:
                            solid_type = f"OTHER({bb_x:.0f}x{bb_y:.0f}x{bb_z:.0f})"
                        
                        print(f"[Joints] Solid {idx} ({solid_type}): bbox {bb_x:.1f}x{bb_y:.1f}x{bb_z:.1f} at ({bb_min_x:.1f}, {solid_bb.YMin:.1f}, {bb_min_z:.1f})")
                        App.Console.PrintMessage(f"[Joints] Solid {idx} ({solid_type}): {bb_x:.1f}x{bb_y:.1f}x{bb_z:.1f}\n")
                    except Exception as e:
                        print(f"[Joints] Solid {idx}: (cannot get bbox: {e})")
                        solid_type = "UNKNOWN"
                    
                    sbb = grow(solid.BoundBox, 0.5)
                    local_tools = [g for g, bb in zip(guides, g_bbs) if sbb.intersect(bb)]
                    
                    if not local_tools:
                        print(f"[Joints] Solid {idx} ({solid_type}): No cutting tools intersect, keeping uncut")
                        App.Console.PrintMessage(f"[Joints] Solid {idx} ({solid_type}): No tools, keeping uncut\n")
                        result_shapes.append(Part.Shape(solid))
                        uncut_count += 1
                        continue
                    
                    print(f"[Joints] Solid {idx} ({solid_type}): {len(local_tools)} cutting tools intersect")
                    App.Console.PrintMessage(f"[Joints] Solid {idx} ({solid_type}): {len(local_tools)} tools, attempting cut\n")

                    # Fuse local tools to remove overlaps → more stable cut
                    try:
                        fused = Part.makeCompound(local_tools)
                        # Try MultiFuse if available
                        try:
                            fused = Part.makeMultiFuse(local_tools)
                        except Exception:
                            pass
                    except Exception:
                        fused = Part.makeCompound(local_tools)

                    # Precompute the cut as a Shape (safer than parametric Cut)
                    try:
                        cut_shape = Part.Shape(solid).cut(fused)
                        
                        # Validate the cut result before refining
                        if cut_shape.isNull():
                            warning_msg = f"[Joints] WARNING: Solid {idx} ({solid_type}) cut produced null shape, using uncut"
                            print(warning_msg)
                            App.Console.PrintWarning(f"{warning_msg}\n")
                            result_shapes.append(Part.Shape(solid))  # fall back to uncut
                            cut_failed_count += 1
                            continue
                        
                        # Check if cut_shape has any solids
                        cut_solids = cut_shape.Solids if hasattr(cut_shape, 'Solids') else []
                        if not cut_solids or len(cut_solids) == 0:
                            warning_msg = f"[Joints] WARNING: Solid {idx} ({solid_type}) cut produced empty shape, using uncut"
                            print(warning_msg)
                            App.Console.PrintWarning(f"{warning_msg}\n")
                            result_shapes.append(Part.Shape(solid))  # fall back to uncut
                            cut_failed_count += 1
                            continue
                        
                        num_solids_before_refine = len(cut_solids)
                        
                        # optional refine passes
                        if bool(obj.RefineResult):
                            try:
                                cut_shape = cut_shape.removeSplitter()
                                # Re-check after removeSplitter
                                if cut_shape.isNull() or (hasattr(cut_shape, 'Solids') and len(cut_shape.Solids) == 0):
                                    warning_msg = f"[Joints] WARNING: Solid {idx} ({solid_type}) refine removed all geometry, using uncut"
                                    print(warning_msg)
                                    App.Console.PrintWarning(f"{warning_msg}\n")
                                    result_shapes.append(Part.Shape(solid))
                                    cut_failed_count += 1
                                    continue
                            except Exception as e:
                                print(f"[Joints] Solid {idx} ({solid_type}): removeSplitter failed: {e}")
                            try:
                                cut_shape = cut_shape.refine()
                                # Re-check after refine
                                if cut_shape.isNull() or (hasattr(cut_shape, 'Solids') and len(cut_shape.Solids) == 0):
                                    warning_msg = f"[Joints] WARNING: Solid {idx} ({solid_type}) refine removed all geometry, using uncut"
                                    print(warning_msg)
                                    App.Console.PrintWarning(f"{warning_msg}\n")
                                    result_shapes.append(Part.Shape(solid))
                                    cut_failed_count += 1
                                    continue
                            except Exception as e:
                                print(f"[Joints] Solid {idx} ({solid_type}): refine failed: {e}")
                        
                        # Final validation before adding
                        if cut_shape.isNull():
                            warning_msg = f"[Joints] WARNING: Solid {idx} ({solid_type}) final cut shape is null, using uncut"
                            print(warning_msg)
                            App.Console.PrintWarning(f"{warning_msg}\n")
                            result_shapes.append(Part.Shape(solid))
                            cut_failed_count += 1
                        else:
                            final_solids = cut_shape.Solids if hasattr(cut_shape, 'Solids') else []
                            print(f"[Joints] Solid {idx} ({solid_type}): Cut successful, {len(final_solids)} solids in result")
                            App.Console.PrintMessage(f"[Joints] Solid {idx} ({solid_type}): Cut OK, {len(final_solids)} solids\n")
                            result_shapes.append(cut_shape)
                            cut_count += len(local_tools)
                            cut_success_count += 1
                    except Exception as e:
                        error_msg = f"[Joints] ERROR: Solid {idx} ({solid_type}) cut failed: {e}"
                        print(error_msg)
                        App.Console.PrintError(f"{error_msg}\n")
                        result_shapes.append(Part.Shape(solid))  # fall back to uncut
                        cut_failed_count += 1
                
                # Summary logging
                print(f"[Joints] Cutting summary: {uncut_count} uncut, {cut_success_count} cut successfully, {cut_failed_count} cut failed")
                print(f"[Joints] Total result_shapes: {len(result_shapes)} (expected {len(base_solids)})")
                App.Console.PrintMessage(f"[Joints] Summary: {uncut_count} uncut, {cut_success_count} cut OK, {cut_failed_count} failed\n")
                App.Console.PrintMessage(f"[Joints] Result shapes: {len(result_shapes)}/{len(base_solids)}\n")
                
                if len(result_shapes) < len(base_solids):
                    warning_msg = f"[Joints] WARNING: Lost {len(base_solids) - len(result_shapes)} solids during cutting!"
                    print(warning_msg)
                    App.Console.PrintWarning(f"{warning_msg}\n")
                
                # Present final as a single Feature with a compound of per-body results
                if not result_shapes:
                    error_msg = "[Joints] ERROR: No result shapes to create Bookshelf_With_Joints"
                    App.Console.PrintError(f"{error_msg}\n")
                    print(error_msg)
                    raise RuntimeError(error_msg)
                
                print(f"[Joints] Creating Bookshelf_With_Joints from {len(result_shapes)} result shapes")
                App.Console.PrintMessage(f"[Joints] Creating final compound from {len(result_shapes)} shapes\n")
                
                final = target_doc.addObject("Part::Feature", "Bookshelf_With_Joints")
                
                try:
                    final.Shape = Part.Compound(result_shapes)
                    
                    # Log what we got
                    final_solids = final.Shape.Solids if hasattr(final.Shape, 'Solids') else []
                    print(f"[Joints] Bookshelf_With_Joints created with {len(final_solids)} solids")
                    App.Console.PrintMessage(f"[Joints] Final compound has {len(final_solids)} solids\n")
                    
                    if len(final_solids) != len(result_shapes):
                        warning_msg = f"[Joints] WARNING: Compound has {len(final_solids)} solids but we added {len(result_shapes)} shapes!"
                        print(warning_msg)
                        App.Console.PrintWarning(f"{warning_msg}\n")
                    
                    # Validate the shape was created correctly
                    if final.Shape.isNull():
                        error_msg = "[Joints] ERROR: Bookshelf_With_Joints Shape is null after creation"
                        App.Console.PrintError(f"{error_msg}\n")
                        print(error_msg)
                        raise RuntimeError(error_msg)
                    
                    if not final.Shape.isValid():
                        # Log but don't fail - we'll try tessellation anyway
                        warning_msg = "[Joints] WARNING: Bookshelf_With_Joints Shape is invalid after creation (but has solids, will try tessellation)"
                        print(warning_msg)
                        App.Console.PrintWarning(f"{warning_msg}\n")
                    
                    # Log success
                    App.Console.PrintMessage(f"[Joints] ✓ Bookshelf_With_Joints created with {len(final_solids)} solids\n")
                    print(f"[Joints] ✓ Bookshelf_With_Joints created with {len(final_solids)} solids")
                    
                except RuntimeError:
                    # Re-raise RuntimeErrors
                    raise
                except Exception as e:
                    error_msg = f"[Joints] ERROR: Failed to set Bookshelf_With_Joints Shape: {e}"
                    App.Console.PrintError(f"{error_msg}\n")
                    print(error_msg)
                    import traceback
                    print(traceback.format_exc())
                    raise RuntimeError(error_msg) from e
                
                target_doc.recompute()

            except Exception as e:
                App.Console.PrintError(f"[Joints] Robust cut failed: {e}\n")

        # outputs & messages
        obj.GuideCount = str(guide_count)
        obj.CutCount = str(cut_count)
        obj.Warnings = "; ".join(warnings) if warnings else ""
        for w in warnings:
            App.Console.PrintMessage(f"[Joints] Warning: {w}\n")

        if GUI_AVAILABLE and Gui:
            try:
                Gui.ActiveDocument.ActiveView.viewAxometric()
                Gui.SendMsgToActiveView("ViewFit")
            except Exception:
                pass


class JointsVP:
    def __init__(self, vobj): vobj.Proxy = self
    def getDisplayModes(self, vobj): return ["Shaded","Wireframe"]
    def getDefaultDisplayMode(self): return "Shaded"
    def setDisplayMode(self, vobj, mode=None, subelements=None): return mode or "Shaded"
    def onDelete(self, vobj, subelements): return True


def make_joints(name: str = "Joints"):
    doc = App.ActiveDocument or App.newDocument("BookshelfDoc")
    obj = doc.addObject("Part::FeaturePython", name)
    JointsFP(obj); JointsVP(obj.ViewObject)
    doc.recompute()
    return obj


# ------------------------------------------------------------
# Demo / quick toggle
# ------------------------------------------------------------
if __name__ == "__main__":
    # Choose one: "glue_dowels" or "camlock_dowels"
    METHOD = "camlock_dowels"   # <- change here to "glue_dowels" if you want

    j = make_joints("Joints")
    j.BookshelfName = "Bookshelf"     # name of your Phase-1 object
    j.Method = METHOD
    j.CreateNewDocument = True        # put result in a fresh doc (nice for inspection)
    j.PerformCuts = True              # set True to actually cut the clone
    j.RefineResult = True

    # Optional: typical cam-lock settings
    if METHOD == "camlock_dowels":
        j.CamBoltDiameter    = 7.0
        j.CamPocketDiameter  = 15.0
        j.CamPocketDepth     = 12.0
        j.CamPocketOffsetX   = 19.0  # pocket center inside top/bottom from the side's INSIDE
        j.CamBoltDeltaY      = 16.0  # bolt lane offset from the dowel lane

    # Optional: dowel settings (used by both methods)
    j.DowelDiameter   = 8.0
    j.DowelLength     = 30.0          # blind hole = half of this
    j.EdgeFrontOffset = 37.0
    j.EdgeBackOffset  = 37.0
    j.EdgePitchY      = 128.0
    
    # Optional: shelf pins configuration
    j.ShelfPinsMode = "modular_grid"        # or "fixed_at_shelves" or "none"
    j.ShelfPinDiameter = 5.0
    j.ShelfPinDepth = 12.0
    j.RowFrontOffset = 37.0
    j.RowBackOffset = 37.0
    j.ShelfPinsOnDividers = True
    j.GridPitchZ = 32.0
    j.GridBottomMargin = 64.0
    j.GridTopMargin = 96.0

    App.ActiveDocument.recompute()
    if GUI_AVAILABLE and Gui:
        try:
            Gui.ActiveDocument.ActiveView.viewAxometric()
            Gui.SendMsgToActiveView("ViewFit")
        except Exception:
            pass
    print(f"[Joints] Created with method={METHOD}. Set properties and recompute as needed.")