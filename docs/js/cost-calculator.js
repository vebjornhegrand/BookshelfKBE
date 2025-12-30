// cost-calculator.js - Cost estimation for bookshelf designs

class CostCalculator {
    constructor() {
        this.materialPrices = {
            'melamine_pb': { name: 'Melamine Particleboard', price_per_m2: 30, density: 700 },
            'plywood': { name: 'Plywood', price_per_m2: 45, density: 550 },
            'mdf': { name: 'MDF', price_per_m2: 28, density: 750 },
            'solid_wood': { name: 'Solid Wood', price_per_m2: 80, density: 600 }
        };
        
        this.jointCosts = {
            'camlock_dowels': { name: 'Cam-locks + Dowels', cost_per_joint: 0.75 },
            'glue_dowels': { name: 'Glue + Dowels', cost_per_joint: 0.35 }
        };
    }
    
    calculate(design, jointMethod = 'camlock_dowels') {
        const material = this.materialPrices[design.material] || this.materialPrices['melamine_pb'];
        const joint = this.jointCosts[jointMethod] || this.jointCosts['camlock_dowels'];
        
        // Calculate panel areas
        const panels = this.calculatePanels(design);
        
        // Material cost
        const totalArea = panels.reduce((sum, panel) => sum + panel.area, 0);
        const materialCost = totalArea * material.price_per_m2;
        
        // Joint costs
        const numPanels = panels.length;
        const numJoints = (design.shelves.length + 2) * 4 + design.dividers.length * 4;
        const jointCost = numJoints * joint.cost_per_joint;
        
        // Shelf pin costs (if shelves present)
        const shelfPinCost = design.shelves.length > 0 ? design.shelves.length * 4 * 0.15 : 0;
        
        // Assembly cost (time-based estimate)
        const assemblyCost = 25 + numPanels * 2;
        
        // Hardware (hinges, handles, etc. - optional)
        const hardwareCost = 15;
        
        // Packaging & overhead
        const packagingCost = 10;
        const overhead = (materialCost + jointCost + assemblyCost) * 0.15; // 15% overhead
        
        const subtotal = materialCost + jointCost + shelfPinCost + assemblyCost + hardwareCost + packagingCost;
        const total = subtotal + overhead;
        
        return {
            material_cost: materialCost,
            joint_cost: jointCost,
            shelf_pin_cost: shelfPinCost,
            assembly_cost: assemblyCost,
            hardware_cost: hardwareCost,
            packaging_cost: packagingCost,
            overhead: overhead,
            subtotal: subtotal,
            total: total,
            material_name: material.name,
            joint_name: joint.name,
            total_area_m2: totalArea,
            num_joints: numJoints,
            num_panels: numPanels
        };
    }
    
    calculatePanels(design) {
        const panels = [];
        const { width, height, depth, thickness, add_top, shelves, dividers } = design;
        
        // Side panels (2)
        panels.push({
            name: 'Side Panel (Left)',
            width: thickness,
            height: height,
            area: (thickness * height) / 1000000,
            quantity: 1
        });
        panels.push({
            name: 'Side Panel (Right)',
            width: thickness,
            height: height,
            area: (thickness * height) / 1000000,
            quantity: 1
        });
        
        // Bottom panel
        panels.push({
            name: 'Bottom Panel',
            width: width,
            depth: depth,
            area: (width * depth) / 1000000,
            quantity: 1
        });
        
        // Top panel (optional)
        if (add_top) {
            panels.push({
                name: 'Top Panel',
                width: width,
                depth: depth,
                area: (width * depth) / 1000000,
                quantity: 1
            });
        }
        
        // Shelves
        shelves.forEach((pos, idx) => {
            panels.push({
                name: `Shelf ${idx + 1}`,
                width: width - thickness * 2,
                depth: depth,
                area: ((width - thickness * 2) * depth) / 1000000,
                quantity: 1
            });
        });
        
        // Dividers
        dividers.forEach((pos, idx) => {
            panels.push({
                name: `Divider ${idx + 1}`,
                width: thickness,
                height: height,
                area: (thickness * height) / 1000000,
                quantity: 1
            });
        });
        
        return panels;
    }
    
    formatCurrency(amount) {
        return '$' + amount.toFixed(2);
    }
}

