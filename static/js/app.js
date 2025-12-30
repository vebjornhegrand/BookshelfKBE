// app.js - Main application logic for Bookshelf KBE Configurator

let currentDesign = null;
let costChart = null;
let gaChart = null;

// Initialize application
document.addEventListener('DOMContentLoaded', function() {
    setupEventListeners();
    checkSystemStatus();
    loadPopularDesigns();
});

function setupEventListeners() {
    // Range input listeners
    document.getElementById('width').addEventListener('input', function() {
        document.getElementById('widthValue').textContent = this.value;
    });
    
    document.getElementById('height').addEventListener('input', function() {
        document.getElementById('heightValue').textContent = this.value;
    });
    
    document.getElementById('depth').addEventListener('input', function() {
        document.getElementById('depthValue').textContent = this.value;
    });
}

async function checkSystemStatus() {
    try {
        const response = await fetch('/api/workflow_status');
        const status = await response.json();
        
        document.getElementById('kbStatus').textContent = status.kb_available ? 'OK' : 'X';
        document.getElementById('gaStatus').textContent = status.ga_available ? 'OK' : 'X';
        document.getElementById('cadStatus').textContent = status.freecad_available ? 'OK' : 'X';
        
        if (!status.kb_available) {
            console.warn('Knowledge Base not available - some features disabled');
        }
    } catch (error) {
        console.error('Failed to check system status:', error);
    }
}

async function searchKB() {
    const searchParams = {
        width: parseFloat(document.getElementById('width').value),
        height: parseFloat(document.getElementById('height').value),
        depth: parseFloat(document.getElementById('depth').value),
        tolerance: 0.15
    };
    
    try {
        showLoading('kbResults');
        
        const response = await fetch('/api/search_designs', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(searchParams)
        });
        
        const result = await response.json();
        
        if (result.success) {
            displayKBResults(result.designs);
        } else {
            showError('kbResults', 'Knowledge Base search failed');
        }
    } catch (error) {
        showError('kbResults', 'Error: ' + error.message);
    }
    
    showTab('kb');
}

async function optimizeWithGA() {
    // Send exact customer dimensions (fixed constraints)
    // GA will optimize only structural parameters (thickness, spacing, etc.)
    const requirements = {
        width: parseFloat(document.getElementById('width').value),
        height: parseFloat(document.getElementById('height').value),
        depth: parseFloat(document.getElementById('depth').value),
        num_shelves: parseInt(document.getElementById('numShelves').value),
        add_top: document.getElementById('addTop').checked,
        material: document.getElementById('material').value,
        target_load: parseFloat(document.getElementById('targetLoad').value),
        // Include joint preferences for cost calculation
        joint_method: document.getElementById('jointMethod').value,
        shelf_pins_mode: document.getElementById('shelfPinsMode').value
    };
    
    try {
        showLoading('gaResults');
        
        const response = await fetch('/api/optimize_design', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(requirements)
        });
        
        const result = await response.json();
        
        if (result.success) {
            currentDesign = result.design;
            displayGAResults(result.design, result.cost_breakdown);
            displayCostBreakdown(result.cost_breakdown);
            const planPayload = result.component_plan || (result.design && result.design.component_plan);
            displayComponentPlan(planPayload);
            
            // Update form values to match optimized design
            document.getElementById('width').value = Math.round(result.design.width);
            document.getElementById('widthValue').textContent = Math.round(result.design.width);
            document.getElementById('height').value = Math.round(result.design.height);
            document.getElementById('heightValue').textContent = Math.round(result.design.height);
            document.getElementById('depth').value = Math.round(result.design.depth);
            document.getElementById('depthValue').textContent = Math.round(result.design.depth);
            document.getElementById('numShelves').value = result.design.shelves ? result.design.shelves.length : 4;
            document.getElementById('addTop').checked = result.design.add_top;
            
            // Generate 3D preview with joints and pin holes after GA optimization
            await generate3DPreview(result.design);
            
            // Enable order button
            document.getElementById('orderBtn').disabled = false;
        } else {
            showError('gaResults', 'Optimization failed');
        }
    } catch (error) {
        showError('gaResults', 'Error: ' + error.message);
    }
    
    showTab('ga');
}

async function generatePreview() {
    // If we have a current optimized design, use its exact values (including shelf/divider positions)
    // Otherwise, use form values and let the backend calculate positions
    let shelf_z_positions = null;
    let divider_x_positions = null;
    let optimized_thickness = null;
    
    if (currentDesign) {
        // Use exact positions from optimized design to ensure consistency
        if (currentDesign.shelves && currentDesign.dividers) {
            shelf_z_positions = currentDesign.shelves.map(s => typeof s === 'object' ? s.z : s);
            divider_x_positions = currentDesign.dividers.map(d => typeof d === 'object' ? d.x_center : d);
            console.log('Using optimized design positions:', { shelf_z_positions, divider_x_positions });
        }
        
        // Use optimized thickness if available
        if (currentDesign.thickness) {
            optimized_thickness = currentDesign.thickness;
            console.log('Using optimized thickness:', optimized_thickness);
        }
    }
    
    const config = {
        width_mm: parseFloat(document.getElementById('width').value),
        height_mm: parseFloat(document.getElementById('height').value),
        depth_mm: parseFloat(document.getElementById('depth').value),
        thickness_mm: optimized_thickness || 18,  // Use optimized thickness if available, otherwise default to 18
        num_shelves: parseInt(document.getElementById('numShelves').value),
        add_top_panel: document.getElementById('addTop').checked,
        material: document.getElementById('material').value,
        target_load_kg: parseFloat(document.getElementById('targetLoad').value),
        // Get joint method and shelf pins mode from user selection
        joint_method: document.getElementById('jointMethod').value,
        shelf_pins_mode: document.getElementById('shelfPinsMode').value
    };
    
    // Add explicit positions if we have them (from optimized design)
    if (shelf_z_positions && shelf_z_positions.length > 0) {
        config.shelf_z_positions = shelf_z_positions;
    }
    if (divider_x_positions && divider_x_positions.length > 0) {
        config.divider_x_positions = divider_x_positions;
    }
    
    try {
        console.log('Generating 3D preview with config:', config);
        const response = await fetch('/api/generate_3d_data', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(config)
        });
        
        // Check if response is OK before parsing JSON
        if (!response.ok) {
            // Try to get error message from response
            let errorMsg = `HTTP error! status: ${response.status}`;
            try {
                const errorData = await response.json();
                if (errorData.error) {
                    errorMsg = errorData.error;
                } else if (errorData.message) {
                    errorMsg = errorData.message;
                }
            } catch (e) {
                // If JSON parsing fails, use status text
                errorMsg = `${response.status} ${response.statusText}`;
            }
            console.error('3D generation failed:', errorMsg);
            alert('3D Preview Error:\n\n' + errorMsg + '\n\nCheck the browser console and server logs for more details.');
            return;
        }
        
        const result = await response.json();
        console.log('3D data response:', result);
        
        if (result.success && result.geometry) {
            console.log('Updating geometry, source:', result.source);
            if (typeof updateBookshelfGeometry === 'function') {
                updateBookshelfGeometry(result.geometry);
            } else {
                console.error('updateBookshelfGeometry function not found');
                alert('Error: updateBookshelfGeometry function not found');
            }
        } else {
            const errorMsg = result.error || 'Failed to generate 3D preview. Check server logs for details.';
            console.error('3D generation failed:', errorMsg);
            alert('3D Preview Error:\n\n' + errorMsg + '\n\nCheck the browser console and server logs for more details.');
        }
    } catch (error) {
        console.error('Failed to generate preview:', error);
        alert('Failed to generate 3D preview: ' + error.message + '\n\nFreeCAD is required for 3D visualization.');
    }
}

async function generate3DPreview(design) {
    // Use the exact optimized design values to ensure consistency
    const config = {
        width_mm: design.width,
        height_mm: design.height,
        depth_mm: design.depth,
        thickness_mm: design.thickness,
        add_top_panel: design.add_top,
        shelf_z_positions: design.shelves,
        divider_x_positions: design.dividers,
        joint_method: document.getElementById('jointMethod') ? 
            document.getElementById('jointMethod').value : 'camlock_dowels',
        shelf_pins_mode: document.getElementById('shelfPinsMode') ? 
            document.getElementById('shelfPinsMode').value : 'modular_grid'
    };
    
    try {
        console.log('Generating 3D preview for design:', design.design_id, 'with config:', config);
        const response = await fetch('/api/generate_3d_data', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(config)
        });
        
        // Check if response is OK before parsing JSON
        if (!response.ok) {
            // Try to get error message from response
            let errorMsg = `HTTP error! status: ${response.status}`;
            try {
                const errorData = await response.json();
                if (errorData.error) {
                    errorMsg = errorData.error;
                } else if (errorData.message) {
                    errorMsg = errorData.message;
                }
            } catch (e) {
                // If JSON parsing fails, use status text
                errorMsg = `${response.status} ${response.statusText}`;
            }
            console.error('3D generation failed:', errorMsg);
            alert('3D Preview Error:\n\n' + errorMsg + '\n\nCheck the browser console and server logs for more details.');
            return;
        }
        
        const result = await response.json();
        console.log('3D data response:', result);
        
        if (result.success && result.geometry) {
            console.log('Updating geometry, source:', result.source);
            if (typeof updateBookshelfGeometry === 'function') {
                updateBookshelfGeometry(result.geometry);
            } else {
                console.error('updateBookshelfGeometry function not found');
                alert('Error: updateBookshelfGeometry function not found');
            }
        } else {
            const errorMsg = result.error || 'Failed to generate 3D preview. Check server logs for details.';
            console.error('3D generation failed:', errorMsg);
            alert('3D Preview Error:\n\n' + errorMsg + '\n\nCheck the browser console and server logs for more details.');
        }
    } catch (error) {
        console.error('Failed to generate 3D preview:', error);
        alert('Failed to generate 3D preview: ' + error.message + '\n\nFreeCAD is required for 3D visualization.');
    }
}

function displayKBResults(designs) {
    const container = document.getElementById('kbResults');
    
    if (designs.length === 0) {
        container.innerHTML = '<p>No similar designs found in Knowledge Base</p>';
        return;
    }
    
    let html = `<p>Found ${designs.length} similar design(s):</p>`;
    
    designs.forEach(design => {
        html += `
            <div class="design-card" onclick="loadDesign('${design.design_id}')">
                <h4>Design ${design.design_id}</h4>
                <p>Dimensions: ${design.width}×${design.height}×${design.depth}mm</p>
                <p>Cost: $${design.cost.toFixed(2)} | Load: ${design.max_load}kg</p>
                <p>Popularity: ${design.popularity} orders | Source: ${design.generated_by}</p>
            </div>
        `;
    });
    
    container.innerHTML = html;
}

function displayGAResults(design, costBreakdown) {
    const container = document.getElementById('gaResults');
    const report = design.optimization_report || {};
    const bestDesign = report.best_design || {};
    const structural = bestDesign.structural_metrics || {};
    const componentPlan = design.component_plan || report.component_plan;
    
    let html = `
        <h4>Optimized Design ${design.design_id || 'N/A'}</h4>
        <div class="design-details">
            <p><strong>Dimensions:</strong> ${design.width?.toFixed(0) || 'N/A'}×${design.height?.toFixed(0) || 'N/A'}×${design.depth?.toFixed(0) || 'N/A'}mm</p>
            <p><strong>Panel Thickness:</strong> ${design.thickness || 'N/A'}mm</p>
            <p><strong>Shelf Spacing:</strong> ${typeof bestDesign.shelf_spacing === 'number' ? bestDesign.shelf_spacing.toFixed(0) + 'mm' : (bestDesign.shelf_spacing || 'even distribution')}</p>
            <p><strong>Shelves:</strong> ${design.shelves?.length || 0}</p>
            <p><strong>Dividers:</strong> ${design.dividers?.length || 0}</p>
            <p><strong>Total Cost:</strong> $${design.cost?.toFixed(2) || '0.00'}</p>
    `;
    
    if (bestDesign.fitness !== undefined) {
        html += `<p><strong>Fitness Score:</strong> ${bestDesign.fitness.toFixed(2)}</p>`;
    }

    if (componentPlan) {
        const reusedCount = (componentPlan.reused || []).length;
        const missingCount = (componentPlan.missing || []).length;
        if (componentPlan.kb_available) {
            html += `<p><strong>Components Reused:</strong> ${reusedCount}</p>`;
            html += `<p><strong>Components to Fabricate:</strong> ${missingCount}</p>`;
        } else if (componentPlan.note) {
            html += `<p><strong>Components:</strong> ${componentPlan.note}</p>`;
        }
    }
    
    // Structural performance metrics
    if (structural.max_deflection_mm !== undefined) {
        html += `<h5>Structural Performance:</h5>`;
        html += `<p><strong>Max Deflection:</strong> ${structural.max_deflection_mm.toFixed(2)}mm</p>`;
        html += `<p><strong>Max Stress:</strong> ${(structural.max_stress_pa / 1e6).toFixed(2)}MPa</p>`;
        html += `<p><strong>Load Capacity:</strong> ${structural.load_capacity_kg.toFixed(1)}kg</p>`;
    }
    
    html += `</div>`;
    
    if (bestDesign.warnings && Array.isArray(bestDesign.warnings) && bestDesign.warnings.length > 0) {
        html += '<h5>Warnings:</h5><ul>';
        bestDesign.warnings.forEach(warning => {
            html += `<li style="font-size: 12px; color: #dc2626;">${warning}</li>`;
        });
        html += '</ul>';
    }
    
    container.innerHTML = html;
    
    // Display evolution chart
    if (report.evolution_history && Array.isArray(report.evolution_history)) {
        displayEvolutionChart(report.evolution_history);
    }
    displayComponentPlan(componentPlan);
}

function displayCostBreakdown(breakdown) {
    const container = document.getElementById('costResults');
    const costs = breakdown.cost;
    
    let html = `
        <div class="cost-item">
            <span>Material:</span>
            <span>$${costs.material.toFixed(2)}</span>
        </div>
        <div class="cost-item">
            <span>Machine Time:</span>
            <span>$${costs.machine.toFixed(2)}</span>
        </div>
        <div class="cost-item">
            <span>Hardware:</span>
            <span>$${costs.hardware.toFixed(2)}</span>
        </div>
        <div class="cost-item">
            <span>Assembly:</span>
            <span>$${costs.assembly.toFixed(2)}</span>
        </div>
        <div class="cost-item">
            <span>Total:</span>
            <span>$${costs.total.toFixed(2)}</span>
        </div>
    `;
    
    container.innerHTML = html;
    
    // Display cost chart
    displayCostChart(costs);
    showTab('cost');
}

function displayComponentPlan(plan) {
    const container = document.getElementById('componentPlan');
    if (!container) return;

    if (!plan) {
        container.innerHTML = '<p>No component plan available.</p>';
        return;
    }

    if (!plan.kb_available) {
        container.innerHTML = `<p>${plan.note || 'Knowledge Base unavailable – component inventory not checked.'}</p>`;
        return;
    }

    const reused = plan.reused || [];
    const missing = plan.missing || [];
    let html = '<h5>Component Availability</h5>';

    if (reused.length > 0) {
        html += '<strong>Reused from Stock</strong><ul>';
        reused.forEach(item => {
            html += `<li>${item.description || item.component_type} · ${Number(item.width || 0).toFixed(0)}×${Number(item.height || 0).toFixed(0)}×${Number(item.depth || 0).toFixed(0)}mm · ${item.material} (ID: ${item.component_id})</li>`;
        });
        html += '</ul>';
    } else {
        html += '<p>No stocked components matched this design.</p>';
    }

    if (missing.length > 0) {
        html += '<strong>To Fabricate</strong><ul>';
        missing.forEach(item => {
            html += `<li>${item.description || item.component_type} · ${Number(item.width || 0).toFixed(0)}×${Number(item.height || 0).toFixed(0)}×${Number(item.depth || 0).toFixed(0)}mm · ${item.material}</li>`;
        });
        html += '</ul>';
    } else {
        html += '<p>All required components were sourced from existing inventory.</p>';
    }

    container.innerHTML = html;
}

function displayCostChart(costs) {
    const canvas = document.getElementById('costChart');
    canvas.style.display = 'block';
    
    if (costChart) {
        costChart.destroy();
    }
    
    costChart = new Chart(canvas, {
        type: 'doughnut',
        data: {
            labels: ['Material', 'Machine', 'Hardware', 'Assembly'],
            datasets: [{
                data: [costs.material, costs.machine, costs.hardware, costs.assembly],
                backgroundColor: ['#2563eb', '#16a34a', '#eab308', '#dc2626']
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'bottom'
                }
            }
        }
    });
}

function displayEvolutionChart(history) {
    const container = document.getElementById('gaChartContainer');
    const canvas = document.getElementById('gaChart');
    container.style.display = 'block';
    canvas.style.width = '100%';
    canvas.style.height = '100%';
    
    if (gaChart) {
        gaChart.destroy();
    }
    
    const generations = history.map(h => h.generation);
    const bestFitness = history.map(h => h.best_fitness);
    const avgFitness = history.map(h => h.avg_fitness);
    const bestCost = history.map(h => h.best_cost);
    
    gaChart = new Chart(canvas, {
        type: 'line',
        data: {
            labels: generations,
            datasets: [
                {
                    label: 'Best Fitness',
                    data: bestFitness,
                    borderColor: '#2563eb',
                    backgroundColor: 'rgba(37, 99, 235, 0.1)',
                    tension: 0.4
                },
                {
                    label: 'Avg Fitness',
                    data: avgFitness,
                    borderColor: '#16a34a',
                    backgroundColor: 'rgba(22, 163, 74, 0.1)',
                    tension: 0.4
                },
                {
                    label: 'Best Cost ($)',
                    data: bestCost,
                    borderColor: '#dc2626',
                    backgroundColor: 'rgba(220, 38, 38, 0.1)',
                    tension: 0.4,
                    yAxisID: 'y1'
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                y: {
                    type: 'linear',
                    display: true,
                    position: 'left',
                    title: {
                        display: true,
                        text: 'Fitness Score'
                    }
                },
                y1: {
                    type: 'linear',
                    display: true,
                    position: 'right',
                    title: {
                        display: true,
                        text: 'Cost ($)'
                    },
                    grid: {
                        drawOnChartArea: false
                    }
                }
            },
            plugins: {
                legend: {
                    position: 'bottom'
                }
            }
        }
    });
}

async function loadDesign(designId) {
    try {
        const response = await fetch(`/api/get_design/${designId}`);
        const result = await response.json();
        
        if (result.success) {
            currentDesign = result.design;
            await generate3DPreview(result.design);
            document.getElementById('orderBtn').disabled = false;
        }
    } catch (error) {
        console.error('Failed to load design:', error);
    }
}

async function loadPopularDesigns() {
    try {
        const response = await fetch('/api/popular_designs');
        const result = await response.json();
        
        if (result.success && result.designs) {
            const container = document.getElementById('popularDesigns');
            let html = '';
            
            result.designs.forEach(design => {
                html += `
                    <div class="popular-item" onclick="loadDesign('${design.design_id}')">
                        <h4>${design.design_id}</h4>
                        <div class="dimensions">${design.width}×${design.height}×${design.depth}mm</div>
                        <div class="cost">$${design.cost.toFixed(2)}</div>
                        <div class="popularity">Orders: ${design.popularity}</div>
                    </div>
                `;
            });
            
            container.innerHTML = html || '<p>No popular designs yet</p>';
        }
    } catch (error) {
        console.error('Failed to load popular designs:', error);
    }
}

async function placeOrder() {
    if (!currentDesign) {
        alert('Please select or generate a design first');
        return;
    }
    
    const customerName = prompt('Enter your name:');
    if (!customerName) return;
    
    const quantity = parseInt(prompt('Enter quantity:', '1'));
    if (!quantity || quantity < 1) return;
    
    try {
        const response = await fetch('/api/record_order', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                customer_name: customerName,
                design_id: currentDesign.design_id,
                quantity: quantity
            })
        });
        
        const result = await response.json();
        
        if (result.success) {
            alert(`Order placed successfully!\nCustomer ID: ${result.customer_id}\nDesign: ${currentDesign.design_id}\nQuantity: ${quantity}`);
            loadPopularDesigns(); // Refresh popular designs
        }
    } catch (error) {
        alert('Failed to place order: ' + error.message);
    }
}

function showTab(tabName, clickedButton) {
    // Hide all tabs
    document.querySelectorAll('.tab-content').forEach(tab => {
        tab.classList.remove('active');
    });
    document.querySelectorAll('.tab-button').forEach(button => {
        button.classList.remove('active');
    });
    
    // Show selected tab
    document.getElementById(`${tabName}-tab`).classList.add('active');
    
    // Activate the clicked button if provided
    if (clickedButton) {
        clickedButton.classList.add('active');
    } else {
        // Find and activate the button for this tab
        const buttons = document.querySelectorAll('.tab-button');
        buttons.forEach(button => {
            if (button.textContent.toLowerCase().includes(tabName.toLowerCase())) {
                button.classList.add('active');
            }
        });
    }
}

function showLoading(elementId) {
    document.getElementById(elementId).innerHTML = '<div class="loading"></div> Loading...';
}

function showError(elementId, message) {
    document.getElementById(elementId).innerHTML = `<p style="color: #dc2626;">${message}</p>`;
}
