// viewer.js - Three.js 3D visualization for bookshelf

let scene, camera, renderer, controls;
let bookshelfGroup;
let wireframeMode = false;

// Helper function to create gradient background
function createGradientTexture() {
    const canvas = document.createElement('canvas');
    canvas.width = 256;
    canvas.height = 256;
    const context = canvas.getContext('2d');
    
    const gradient = context.createLinearGradient(0, 0, 0, 256);
    gradient.addColorStop(0, '#1a1f2e');
    gradient.addColorStop(0.5, '#2a2f3e');
    gradient.addColorStop(1, '#1a1f2e');
    
    context.fillStyle = gradient;
    context.fillRect(0, 0, 256, 256);
    
    const texture = new THREE.CanvasTexture(canvas);
    texture.mapping = THREE.EquirectangularReflectionMapping;
    return texture;
}

function initViewer() {
    const container = document.getElementById('threejs-container');
    if (!container) {
        console.error('threejs-container not found');
        return;
    }
    
    // Get container dimensions - wait for layout to be ready
    // Use getBoundingClientRect for accurate dimensions
    const rect = container.getBoundingClientRect();
    let width = rect.width || container.offsetWidth || container.clientWidth || 800;
    let height = rect.height || container.offsetHeight || container.clientHeight || 600;
    
    // Ensure minimum dimensions
    if (width < 100) width = 800;
    if (height < 100) height = 600;
    
    console.log(`Initializing viewer with dimensions: ${width}x${height}`);

    // Scene setup with gradient background
    scene = new THREE.Scene();
    // Create gradient background
    const gradientTexture = createGradientTexture();
    scene.background = gradientTexture;
    
    // Camera setup
    camera = new THREE.PerspectiveCamera(45, width / height, 1, 10000);
    camera.position.set(1500, 1500, 1500);
    
    // Renderer setup with better quality
    renderer = new THREE.WebGLRenderer({ 
        antialias: true,
        preserveDrawingBuffer: true,
        powerPreference: "high-performance"
    });
    renderer.setSize(width, height, false);
    renderer.shadowMap.enabled = true;
    renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    renderer.outputEncoding = THREE.sRGBEncoding;
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.2;
    
    // Set canvas style to fill container without stretching
    renderer.domElement.style.width = '100%';
    renderer.domElement.style.height = '100%';
    renderer.domElement.style.display = 'block';
    
    container.appendChild(renderer.domElement);
    
    // Enhanced controls with smoother interaction
    controls = new THREE.OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.08;
    controls.screenSpacePanning = false;
    controls.minDistance = 500;
    controls.maxDistance = 5000;
    controls.autoRotate = false;
    controls.autoRotateSpeed = 0.5;
    controls.enablePan = true;
    controls.panSpeed = 0.8;
    controls.rotateSpeed = 0.5;
    controls.zoomSpeed = 1.2;
    
    // Enhanced lighting setup
    // Ambient light for overall illumination
    const ambientLight = new THREE.AmbientLight(0xffffff, 0.5);
    scene.add(ambientLight);
    
    // Main directional light (sun)
    const mainLight = new THREE.DirectionalLight(0xffffff, 0.8);
    mainLight.position.set(1500, 2500, 1500);
    mainLight.castShadow = true;
    mainLight.shadow.camera.near = 100;
    mainLight.shadow.camera.far = 5000;
    mainLight.shadow.camera.left = -2500;
    mainLight.shadow.camera.right = 2500;
    mainLight.shadow.camera.top = 2500;
    mainLight.shadow.camera.bottom = -2500;
    mainLight.shadow.mapSize.width = 2048;
    mainLight.shadow.mapSize.height = 2048;
    mainLight.shadow.bias = -0.0001;
    scene.add(mainLight);
    
    // Fill light from opposite side (softer)
    const fillLight = new THREE.DirectionalLight(0xffffff, 0.3);
    fillLight.position.set(-1000, 1000, -1000);
    scene.add(fillLight);
    
    // Rim light for edge definition
    const rimLight = new THREE.DirectionalLight(0xffffff, 0.2);
    rimLight.position.set(-1500, 500, -1500);
    scene.add(rimLight);
    
    // Add subtle hemisphere light for natural look
    const hemiLight = new THREE.HemisphereLight(0xffffff, 0x444444, 0.4);
    hemiLight.position.set(0, 2000, 0);
    scene.add(hemiLight);
    
    // Enhanced grid helper with better colors (positioned below bookshelf)
    const gridHelper = new THREE.GridHelper(3000, 30, 0x555555, 0x333333);
    gridHelper.material.opacity = 0.2;
    gridHelper.material.transparent = true;
    gridHelper.position.y = -100; // Position grid well below bookshelf
    scene.add(gridHelper);
    
    // Add a subtle floor plane positioned well below the bookshelf
    const floorGeometry = new THREE.PlaneGeometry(3000, 3000);
    const floorMaterial = new THREE.MeshStandardMaterial({
        color: 0x2a2a2a,
        roughness: 0.8,
        metalness: 0.1
    });
    const floor = new THREE.Mesh(floorGeometry, floorMaterial);
    floor.rotation.x = -Math.PI / 2;
    floor.position.y = -200; // Position floor well below bookshelf to avoid clipping
    floor.receiveShadow = true;
    scene.add(floor);
    
    // Initial empty bookshelf group
    bookshelfGroup = new THREE.Group();
    scene.add(bookshelfGroup);
    
    // Handle window resize
    window.addEventListener('resize', onWindowResize, false);
    
    // Use ResizeObserver to detect container size changes (more reliable than window resize)
    if (typeof ResizeObserver !== 'undefined') {
        const resizeObserver = new ResizeObserver(entries => {
            for (let entry of entries) {
                const { width, height } = entry.contentRect;
                if (width > 0 && height > 0 && renderer && camera) {
                    // Update camera aspect ratio
                    camera.aspect = width / height;
                    camera.updateProjectionMatrix();
                    // Update renderer size (false = don't update CSS)
                    renderer.setSize(width, height, false);
                    // Ensure canvas fills container
                    renderer.domElement.style.width = '100%';
                    renderer.domElement.style.height = '100%';
                }
            }
        });
        resizeObserver.observe(container);
    }
    
    // Start animation loop
    animate();
}

function onWindowResize() {
    const container = document.getElementById('threejs-container');
    if (!container || !renderer || !camera) return;
    
    // Use getBoundingClientRect for accurate dimensions
    const rect = container.getBoundingClientRect();
    const width = rect.width || container.offsetWidth || container.clientWidth;
    const height = rect.height || container.offsetHeight || container.clientHeight;
    
    if (width > 0 && height > 0) {
        camera.aspect = width / height;
        camera.updateProjectionMatrix();
        renderer.setSize(width, height, false); // false = don't update CSS
        renderer.domElement.style.width = '100%';
        renderer.domElement.style.height = '100%';
    }
}

function animate() {
    requestAnimationFrame(animate);
    controls.update();
    renderer.render(scene, camera);
}

function updateBookshelfGeometry(geometryData) {
    if (!geometryData) {
        console.error('No geometry data provided');
        alert('Error: No geometry data provided');
        return;
    }
    
    // Clear existing geometry
    while(bookshelfGroup.children.length > 0) {
        bookshelfGroup.remove(bookshelfGroup.children[0]);
    }
    
    // REQUIRE mesh data - no panel fallback
    if (!geometryData.mesh_data || !geometryData.mesh_data.vertices || !geometryData.mesh_data.faces) {
        const errorMsg = 'Error: No mesh data available. Geometry extraction failed. Check server logs for details.';
        console.error(errorMsg, geometryData);
        alert(errorMsg);
        return;
    }
    
    const vertices = geometryData.mesh_data.vertices;
    const faces = geometryData.mesh_data.faces;
    
    if (!vertices || vertices.length === 0) {
        const errorMsg = 'Error: Mesh data has no vertices. Tessellation failed.';
        console.error(errorMsg);
        alert(errorMsg);
        return;
    }
    
    // Create geometry from vertices and faces
    const geometry = new THREE.BufferGeometry();
    const positions = new Float32Array(vertices.length * 3);
    const indices = [];
    
    // Flatten vertices
    for (let i = 0; i < vertices.length; i++) {
        positions[i * 3] = vertices[i][0] - (geometryData.dimensions.width / 2);
        positions[i * 3 + 1] = vertices[i][1] - (geometryData.dimensions.height / 2);
        positions[i * 3 + 2] = vertices[i][2] - (geometryData.dimensions.depth / 2);
    }
    
    // Flatten faces
    for (let i = 0; i < faces.length; i++) {
        indices.push(faces[i][0], faces[i][1], faces[i][2]);
    }
    
    geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
    geometry.setIndex(indices);
    geometry.computeVertexNormals();
    
    // Enhanced material with better wood-like appearance
    const material = new THREE.MeshStandardMaterial({ 
        color: 0x8b7355,
        roughness: 0.7,
        metalness: 0.1,
        wireframe: wireframeMode,
        flatShading: false,
        side: THREE.DoubleSide, // Ensure both sides are rendered
        transparent: false, // Ensure no transparency
        opacity: 1.0 // Fully opaque
    });
    
    const mesh = new THREE.Mesh(geometry, material);
    mesh.castShadow = true;
    mesh.receiveShadow = true;
    
    // Add crisp edge overlay so small details (like pin holes) pop
    const edgeGeometry = new THREE.EdgesGeometry(geometry, 25); // 25° threshold highlights subtle insets
    const edgeMaterial = new THREE.LineBasicMaterial({
        color: 0x111111,
        linewidth: 1,
        transparent: true,
        opacity: 0.45
    });
    const edgeLines = new THREE.LineSegments(edgeGeometry, edgeMaterial);
    edgeLines.renderOrder = 1; // draw after mesh to avoid z-fighting
    
    bookshelfGroup.add(mesh);
    bookshelfGroup.add(edgeLines);
    
    // Center the bookshelf in view and position it above the floor
    const box = new THREE.Box3().setFromObject(bookshelfGroup);
    const center = box.getCenter(new THREE.Vector3());
    const minY = box.min.y;
    
    // If bookshelf bottom is below floor level, raise it so it sits on the floor
    if (minY < -100) {
        const offsetY = -100 - minY; // Calculate how much to raise it
        bookshelfGroup.position.y = offsetY;
        center.y += offsetY; // Adjust center point for camera target
    }
    
    controls.target.copy(center);
    controls.update();
    
    console.log(`Geometry loaded: ${vertices.length} vertices, ${faces.length} faces`);
}

function resetView() {
    camera.position.set(1500, 1500, 1500);
    controls.target.set(0, 0, 0);
    controls.update();
}

function toggleWireframe() {
    wireframeMode = !wireframeMode;
    
    bookshelfGroup.traverse((child) => {
        if (child instanceof THREE.Mesh) {
            child.material.wireframe = wireframeMode;
        }
    });
}

// Make functions globally accessible
window.updateBookshelfGeometry = updateBookshelfGeometry;
window.resetView = resetView;
window.toggleWireframe = toggleWireframe;

// Initialize viewer when page loads
document.addEventListener('DOMContentLoaded', function() {
    // Small delay to ensure DOM is fully ready
    setTimeout(initViewer, 100);
});
