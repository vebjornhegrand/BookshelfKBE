// app-demo.js - Main application logic for GitHub Pages demo

let viewer;
let optimizer;
let calculator;
let currentDesign = null;

// Initialize on page load
document.addEventListener('DOMContentLoaded', function() {
    initializeApp();
});

function initializeApp() {
    // Initialize 3D viewer
    viewer = new BookshelfViewer('threejs-container');
    
    // Initialize optimizer and calculator
    optimizer = new GeneticOptimizer({
        populationSize: 20,
        generations: 15,
        mutationRate: 0.25
    });
    
    calculator = new CostCalculator();
    
    // Setup event listeners for sliders
    document.getElementById('width').addEventListener('input', function() {
        document.getElementById('widthValue').textContent = this.value;
    });
    
    document.getElementById('height').addEventListener('input', function() {
        document.getElementById('heightValue').textContent = this.value;
    });
    
    document.getElementById('depth').addEventListener('input', function() {
        document.getElementById('depthValue').textContent = this.value;
    });
    
    console.log('Bookshelf KBE Demo initialized');
}

function optimizeWithGA() {
    // Get requirements from form
    const requirements = {
        width: parseFloat(document.getElementById('width').value),
        height: parseFloat(document.getElementById('height').value),
        depth: parseFloat(document.getElementById('depth').value),
        num_shelves: parseInt(document.getElementById('numShelves').value),
        add_top: document.getElementById('addTop').checked,
        material: document.getElementById('material').value,
        target_load: parseFloat(document.getElementById('targetLoad').value)
    };
    
    // Show loading
    showLoading();
    
    // Run GA optimization (simulated delay for realism)
    setTimeout(() => {
        currentDesign = optimizer.optimize(requirements);
        const report = optimizer.getReport();
        
        // Calculate costs
        const jointMethod = document.getElementById('jointMethod').value;
        const costs = calculator.calculate(currentDesign, jointMethod);
        
        // Display results
        displayCostResults(costs);
        displayGAReport(report);
        
        // Generate 3D visualization
        viewer.generateBookshelf(currentDesign);
        
        // Enable order button
        document.getElementById('placeOrderBtn').disabled = false;
        
        // Switch to cost tab
        showTab('cost');
        
        hideLoading();
        
        console.log('Optimization complete:', currentDesign);
    }, 1000); // 1 second delay for demo effect
}

function generatePreview() {
    // Get current form values
    const design = {
        width: parseFloat(document.getElementById('width').value),
        height: parseFloat(document.getElementById('height').value),
        depth: parseFloat(document.getElementById('depth').value),
        thickness: 18,
        num_shelves: parseInt(document.getElementById('numShelves').value),
        add_top: document.getElementById('addTop').checked,
        material: document.getElementById('material').value,
        shelves: [],
        dividers: []
    };
    
    // Generate evenly spaced shelves
    const numShelves = design.num_shelves;
    if (numShelves > 0) {
        const spacing = design.height / (numShelves + 1);
        for (let i = 1; i <= numShelves; i++) {
            design.shelves.push(spacing * i);
        }
    }
    
    // No dividers by default in preview
    design.dividers = [];
    
    currentDesign = design;
    
    // Generate 3D visualization
    viewer.generateBookshelf(design);
    
    // Calculate and display costs
    const jointMethod = document.getElementById('jointMethod').value;
    const costs = calculator.calculate(design, jointMethod);
    displayCostResults(costs);
    
    console.log('Preview generated:', design);
}

function displayCostResults(costs) {
    const html = `
        <div class="cost-item">
            <span>Material (${costs.material_name}):</span>
            <span>${calculator.formatCurrency(costs.material_cost)}</span>
        </div>
        <div class="cost-item">
            <span>Joints (${costs.joint_name}):</span>
            <span>${calculator.formatCurrency(costs.joint_cost)}</span>
        </div>
        <div class="cost-item">
            <span>Shelf Pins:</span>
            <span>${calculator.formatCurrency(costs.shelf_pin_cost)}</span>
        </div>
        <div class="cost-item">
            <span>Assembly:</span>
            <span>${calculator.formatCurrency(costs.assembly_cost)}</span>
        </div>
        <div class="cost-item">
            <span>Hardware:</span>
            <span>${calculator.formatCurrency(costs.hardware_cost)}</span>
        </div>
        <div class="cost-item">
            <span>Packaging:</span>
            <span>${calculator.formatCurrency(costs.packaging_cost)}</span>
        </div>
        <div class="cost-item">
            <span>Overhead (15%):</span>
            <span>${calculator.formatCurrency(costs.overhead)}</span>
        </div>
        <div class="cost-item" style="margin-top: 10px; padding-top: 10px; border-top: 2px solid #2563eb;">
            <span style="font-size: 16px;"><strong>Total Cost:</strong></span>
            <span style="font-size: 18px; color: #16a34a;"><strong>${calculator.formatCurrency(costs.total)}</strong></span>
        </div>
        <div style="margin-top: 15px; font-size: 12px; color: #6b7280;">
            <p>📊 ${costs.num_panels} panels, ${costs.num_joints} joints</p>
            <p>📐 Total area: ${costs.total_area_m2.toFixed(2)} m²</p>
        </div>
    `;
    
    document.getElementById('costResults').innerHTML = html;
}

function displayGAReport(report) {
    const history = report.convergence_history;
    const lastGen = history[history.length - 1];
    
    const html = `
        <div style="font-size: 13px;">
            <p><strong>Genetic Algorithm Optimization</strong></p>
            <div style="margin-top: 10px;">
                <p>🧬 Generations: ${report.generations}</p>
                <p>👥 Population: ${report.population_size}</p>
                <p>🎯 Best Fitness: ${report.best_fitness.toFixed(2)}</p>
            </div>
            
            <div style="margin-top: 15px; padding: 10px; background: #f3f4f6; border-radius: 6px;">
                <p style="margin-bottom: 5px;"><strong>Final Generation:</strong></p>
                <p>• Best: ${lastGen.best.toFixed(2)}</p>
                <p>• Average: ${lastGen.average.toFixed(2)}</p>
                <p>• Worst: ${lastGen.worst.toFixed(2)}</p>
            </div>
            
            <div style="margin-top: 15px;">
                <p><strong>Convergence Progress:</strong></p>
                <canvas id="gaChart" width="300" height="150"></canvas>
            </div>
        </div>
    `;
    
    document.getElementById('gaResults').innerHTML = html;
    
    // Draw convergence chart
    drawConvergenceChart(history);
}

function drawConvergenceChart(history) {
    const canvas = document.getElementById('gaChart');
    if (!canvas) return;
    
    const ctx = canvas.getContext('2d');
    const width = canvas.width;
    const height = canvas.height;
    const padding = 30;
    
    // Clear canvas
    ctx.fillStyle = '#ffffff';
    ctx.fillRect(0, 0, width, height);
    
    // Find min/max for scaling
    const allValues = history.flatMap(h => [h.best, h.average, h.worst]);
    const minVal = Math.min(...allValues);
    const maxVal = Math.max(...allValues);
    const range = maxVal - minVal || 1;
    
    // Scale function
    const scaleX = (gen) => padding + (gen / (history.length - 1)) * (width - 2 * padding);
    const scaleY = (val) => height - padding - ((val - minVal) / range) * (height - 2 * padding);
    
    // Draw grid
    ctx.strokeStyle = '#e5e7eb';
    ctx.lineWidth = 1;
    for (let i = 0; i <= 4; i++) {
        const y = padding + (i / 4) * (height - 2 * padding);
        ctx.beginPath();
        ctx.moveTo(padding, y);
        ctx.lineTo(width - padding, y);
        ctx.stroke();
    }
    
    // Draw best fitness line
    ctx.strokeStyle = '#16a34a';
    ctx.lineWidth = 2;
    ctx.beginPath();
    history.forEach((h, i) => {
        const x = scaleX(i);
        const y = scaleY(h.best);
        if (i === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
    });
    ctx.stroke();
    
    // Draw average line
    ctx.strokeStyle = '#2563eb';
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    history.forEach((h, i) => {
        const x = scaleX(i);
        const y = scaleY(h.average);
        if (i === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
    });
    ctx.stroke();
    
    // Draw labels
    ctx.fillStyle = '#111827';
    ctx.font = '10px sans-serif';
    ctx.fillText('0', 5, height - padding + 15);
    ctx.fillText(history.length - 1, width - padding - 10, height - padding + 15);
    ctx.fillText(maxVal.toFixed(0), 5, padding);
    ctx.fillText(minVal.toFixed(0), 5, height - padding);
    
    // Legend
    ctx.fillStyle = '#16a34a';
    ctx.fillRect(width - 100, 10, 15, 10);
    ctx.fillStyle = '#111827';
    ctx.fillText('Best', width - 80, 18);
    
    ctx.fillStyle = '#2563eb';
    ctx.fillRect(width - 100, 25, 15, 10);
    ctx.fillStyle = '#111827';
    ctx.fillText('Average', width - 80, 33);
}

function showTab(tabName) {
    // Hide all tabs
    document.querySelectorAll('.tab-content').forEach(tab => {
        tab.classList.remove('active');
    });
    document.querySelectorAll('.tab-button').forEach(btn => {
        btn.classList.remove('active');
    });
    
    // Show selected tab
    const tabs = {
        'cost': 'costTab',
        'ga': 'gaTab',
        'info': 'infoTab'
    };
    
    if (tabs[tabName]) {
        document.getElementById(tabs[tabName]).classList.add('active');
        document.querySelector(`[data-tab="${tabName}"]`).classList.add('active');
    }
}

function resetView() {
    if (viewer) {
        viewer.resetView();
    }
}

function toggleWireframe() {
    if (viewer) {
        viewer.toggleWireframe();
    }
}

function exportSTL() {
    if (viewer) {
        viewer.exportSTL();
    }
}

function showOrderDialog() {
    if (!currentDesign) {
        alert('Please optimize a design first!');
        return;
    }
    
    alert('Order Placement\n\n' +
          'In the full application with Fuseki KB:\n' +
          '• Orders are tracked in RDF triplestore\n' +
          '• Component availability checked\n' +
          '• Design popularity updated\n' +
          '• Customer records maintained\n\n' +
          'This is a demo version for portfolio purposes.\n' +
          'See GitHub for complete implementation.');
}

function showLoading() {
    // Show loading indicators
    document.getElementById('costResults').innerHTML = '<div style="text-align: center; padding: 20px;"><div class="loading"></div><p style="margin-top: 10px;">Optimizing design...</p></div>';
    document.getElementById('gaResults').innerHTML = '<div style="text-align: center; padding: 20px;"><div class="loading"></div><p style="margin-top: 10px;">Running GA...</p></div>';
}

function hideLoading() {
    // Loading is replaced by actual content
}

